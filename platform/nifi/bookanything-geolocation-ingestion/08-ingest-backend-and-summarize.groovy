// =============================================================================
// NiFi ExecuteScript body: "8. Ingest Backend & Summarize"
// Process group: "BookAnything - GeoLocation Ingestion Pipeline"
//
// Source of truth for the live processor's "Script Body". Apply with:
//   scripts/apply_nifi_script_body.py "8. Ingest Backend & Summarize" \
//     platform/nifi/bookanything-geolocation-ingestion/08-ingest-backend-and-summarize.groovy
//
// Reads a GADM GeoJSON flowfile, creates/updates GeoLocations in the tenant
// backend and replaces the content with a summary JSON that step 9 publishes to
// geolocation.nifi-import.completed (consumed by the Temporal activity).
//
// Failure handling (2026-09-24): non-2xx responses used to be dropped silently,
// so a broken import reported createdCount=0 as a success; and any exception went
// to the auto-terminated "failure" relationship, leaving the Temporal activity
// waiting 25 minutes for a reply that never came. Now:
//   - every HTTP call has connect/read timeouts;
//   - non-2xx responses are counted (failedCount), logged, and sampled into
//     errorMessage;
//   - a missing parent (e.g. no REGION for a country) aborts early with a clear
//     errorMessage instead of issuing hundreds of doomed POSTs;
//   - exceptions still produce a summary (with errorMessage) on "success", so
//     the workflow always gets an answer.
//
// Parent resolution (2026-09-25): no more hardcoded country->region map or
// country names. The parent of every record is looked up in the backend data:
//   - country  -> REGION: flowfile attribute "parentFriendlyId" if set, else the
//     REGION whose additionalDetailsMap.memberCountriesIso3 contains the ISO3
//     code (seeded from platform/data/geolocation/continents-regions-un-m49.json
//     by scripts/seed_geolocation_reference_data.py), else the parent the
//     country already has;
//   - province -> COUNTRY by exact friendlyId (created on the fly, named from
//     the GADM "COUNTRY" property, if it does not exist yet);
//   - city / district -> the province / city of THIS country that matches the
//     feature's GID_1/GID_2 (stored as "gid" since this version), else its HASC
//     prefix, else its accent/space-insensitive NAME_1/NAME_2.
// A feature whose parent cannot be resolved is counted as failed instead of
// being created without a parent.
// =============================================================================
import groovy.json.JsonSlurper
import groovy.json.JsonOutput
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.Normalizer
import java.util.concurrent.Executors
import java.util.concurrent.Callable
import java.util.concurrent.TimeUnit
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicInteger

def flowFile = session.get()
if (!flowFile) return

def startTime = System.currentTimeMillis()
def jobId = flowFile.getAttribute('jobId') ?: 'unknown-job'
def countrySlug = flowFile.getAttribute('countrySlug') ?: 'UNKNOWN'
def locationLevel = (flowFile.getAttribute('locationLevel') ?: '0') as Integer
def shouldConvertToXML = Boolean.parseBoolean(flowFile.getAttribute('shouldConvertToXML') ?: 'false')

def backendBaseUrl = "http://bookanything-monolith-backend-01.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8060"
def CONNECT_TIMEOUT_MS = 10000
def READ_TIMEOUT_MS = 30000
def MAX_ERROR_SAMPLES = 5
def MAX_LOGGED_ERRORS = 20

def type = "country"
if (locationLevel == 1) type = "province"
else if (locationLevel == 2) type = "city"
else if (locationLevel >= 3) type = "district"

def createdCounter = new AtomicInteger(0)
def updatedCounter = new AtomicInteger(0)
def failedCounter = new AtomicInteger(0)
def errorSamples = new ConcurrentLinkedQueue<String>()

def logPrefix = "[GeoIngest job=${jobId} ${countrySlug} L${locationLevel}]"

// Single HTTP helper: always sets timeouts, always reads the body (success or
// error stream) and always disconnects. Returns [code: Int, body: String].
def http = { String method, String url, Object payload = null ->
    def conn = (HttpURLConnection) new URL(url).openConnection()
    try {
        conn.setRequestMethod(method)
        conn.setConnectTimeout(CONNECT_TIMEOUT_MS)
        conn.setReadTimeout(READ_TIMEOUT_MS)
        conn.setRequestProperty("Accept", "application/json")
        if (payload != null) {
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setDoOutput(true)
            conn.getOutputStream().withCloseable { it.write(JsonOutput.toJson(payload).getBytes("UTF-8")) }
        }
        def code = conn.getResponseCode()
        def stream = (code >= 200 && code < 300) ? conn.getInputStream() : conn.getErrorStream()
        def body = stream != null ? stream.getText("UTF-8") : ""
        return [code: code, body: body]
    } finally {
        conn.disconnect()
    }
}

def recordFailure = { String what, Integer code, String body ->
    def n = failedCounter.incrementAndGet()
    def msg = "${what} -> HTTP ${code}: ${(body ?: '').take(300)}"
    if (errorSamples.size() < MAX_ERROR_SAMPLES) errorSamples.add(msg)
    if (n <= MAX_LOGGED_ERRORS) log.warn("${logPrefix} ${msg}")
}

def getJson = { String url ->
    def r = http("GET", url)
    if (r.code == 200) return new JsonSlurper().parseText(r.body)
    recordFailure("GET ${url}", r.code, r.body)
    return null
}

def enc = { String v -> URLEncoder.encode(v ?: '', 'UTF-8') }

// All pages of a GET list endpoint (Spring Page JSON: content + page.totalPages).
def getAllPages = { String baseUrl ->
    def sep = baseUrl.contains('?') ? '&' : '?'
    def all = []
    int pageIdx = 0
    int totalPages = 1
    while (pageIdx < totalPages) {
        def res = getJson("${baseUrl}${sep}page=${pageIdx}&size=1000")
        if (res == null) return null
        all.addAll(res.content ?: [])
        totalPages = res.page?.totalPages ?: 0
        pageIdx++
    }
    return all
}

// Accent-, case- and whitespace-insensitive key: "São Paulo" / "SaoPaulo" -> "saopaulo".
def normalizeName = { String v ->
    v == null ? null : Normalizer.normalize(v, Normalizer.Form.NFD).replaceAll("\\p{M}", "").toLowerCase().replaceAll("[^a-z0-9]", "")
}
def present = { v -> v != null && v.toString() && v.toString() != "NA" }

// Exact friendlyId match within a type (never "first result" fallbacks).
def findByFriendlyId = { String geoType, String friendlyId ->
    def res = getJson("${backendBaseUrl}/api/v1/geolocations/${geoType}/search-by-friendlyid?friendlyId=${enc(friendlyId)}&size=10")
    return res?.content?.find { it.friendlyId == friendlyId }
}

// Parent REGION of a country: explicit override, then reference-data membership,
// then the region the country already has. Returns [id:, via:] or null.
def resolveRegionForCountry = { String iso3 ->
    def regions = getAllPages("${backendBaseUrl}/api/v1/geolocations/region") ?: []
    def override = flowFile.getAttribute('parentFriendlyId')
    if (override) {
        def r = regions.find { it.friendlyId == override }
        if (r == null) throw new IllegalStateException("parentFriendlyId '${override}' is not an existing REGION.")
        return [id: r.id, via: "attribute parentFriendlyId=${override}"]
    }
    def member = regions.find { (it.additionalDetailsMap?.memberCountriesIso3 ?: []).contains(iso3) }
    if (member != null) return [id: member.id, via: "region ${member.friendlyId} (memberCountriesIso3)"]
    def existingCountry = findByFriendlyId("country", iso3)
    if (existingCountry?.parentId != null) return [id: existingCountry.parentId, via: "existing parent of country ${iso3}"]
    return null
}

def noRegionMessage = { String iso3 ->
    "No REGION lists '${iso3}' in additionalDetailsMap.memberCountriesIso3. Add it to " +
    "platform/data/geolocation/continents-regions-un-m49.json and run scripts/seed_geolocation_reference_data.py, " +
    "or set the flowfile attribute parentFriendlyId."
}

// Lookup index over candidate parent records: gid, hasc, iso and
// normalized name/alias -> id. Keys that map to more than one record are dropped
// so an ambiguous name never picks an arbitrary parent.
def buildParentIndex = { List records ->
    def index = [:]
    def ambiguous = [] as Set
    def put = { String prefix, value, id ->
        if (!present(value)) return
        def key = prefix + value
        if (index.containsKey(key) && index[key] != id) ambiguous << key else index[key] = id
    }
    records.each { r ->
        def d = r.additionalDetailsMap ?: [:]
        put("gid:", d.gid, r.id)
        put("hasc:", d.hasc, r.id)
        put("iso:", d.iso, r.id)
        put("name:", normalizeName(r.name), r.id)
        if (normalizeName(r.alias) != normalizeName(r.name)) put("name:", normalizeName(r.alias), r.id)
    }
    ambiguous.each { index.remove(it) }
    return index
}

// HASC of the parent level: "BR.SP.SA" -> "BR.SP".
def parentHasc = { String hasc ->
    if (!present(hasc)) return null
    def parts = hasc.split("\\.")
    return parts.size() > 1 ? parts[0..-2].join(".") : null
}

def resolveFeatureParent = { Map index, Map props, int level ->
    def gid = level == 2 ? props.GID_1 : props.GID_2
    def hasc = parentHasc(level == 2 ? props.HASC_2 : props.HASC_3)
    def name = level == 2 ? props.NAME_1 : props.NAME_2
    return (present(gid) ? index["gid:" + gid] : null) ?:
           (present(hasc) ? index["hasc:" + hasc] : null) ?:
           (level == 2 && present(props.ISO_1) ? index["iso:" + props.ISO_1] : null) ?:
           (present(name) ? index["name:" + normalizeName(name)] : null)
}

def buildSummary = { String errorMessage ->
    def failed = failedCounter.get()
    def message = errorMessage
    if (message == null && failed > 0) {
        message = "${failed} record(s) failed. First errors: " + errorSamples.join(" | ")
    }
    def summary = [
        jobId          : jobId,
        countrySlug    : countrySlug,
        locationLevel  : locationLevel,
        rawGeoJsonUrl  : "s3://darueira-geodata/raw/gadm41_${countrySlug}_${locationLevel}.json",
        convertedXmlUrl: shouldConvertToXML ? "s3://darueira-geodata/xml/gadm41_${countrySlug}_${locationLevel}.xml" : null,
        createdCount   : createdCounter.get(),
        updatedCount   : updatedCounter.get(),
        failedCount    : failed,
        durationMs     : System.currentTimeMillis() - startTime
    ]
    if (message != null) summary.errorMessage = message
    return summary
}

def emitSummary = { Map summary ->
    def summaryJson = JsonOutput.toJson(summary)
    flowFile = session.write(flowFile, { outputStream ->
        outputStream.write(summaryJson.getBytes("UTF-8"))
    } as org.apache.nifi.processor.io.OutputStreamCallback)
    flowFile = session.putAttribute(flowFile, "mime.type", "application/json")
    if (summary.errorMessage) flowFile = session.putAttribute(flowFile, "error.message", summary.errorMessage.take(1000))
    session.transfer(flowFile, REL_SUCCESS)
}

try {
    def json = null
    session.read(flowFile, { inputStream ->
        json = new JsonSlurper().parse(inputStream)
    } as org.apache.nifi.processor.io.InputStreamCallback)

    def features = json?.features ?: []

    // 1. Resolve parents
    def resolvedParentId = null
    def parentIndex = [:]

    if (type == "country") {
        def region = resolveRegionForCountry(countrySlug)
        if (region == null) throw new IllegalStateException(noRegionMessage(countrySlug))
        resolvedParentId = region.id
        log.info("${logPrefix} parent region id=${region.id} via ${region.via}")
    } else {
        def country = findByFriendlyId("country", countrySlug)
        if (country == null && type == "province") {
            // Country not imported yet: create a minimal one under its region,
            // named from the GADM features themselves.
            def region = resolveRegionForCountry(countrySlug)
            if (region == null) throw new IllegalStateException("Country '${countrySlug}' does not exist yet and: " + noRegionMessage(countrySlug))
            def countryName = features.collect { it.get('properties')?.COUNTRY }.find { present(it) } ?: countrySlug
            def r = http("POST", "${backendBaseUrl}/api/v1/geolocations/country", [
                name                : countryName,
                alias               : countrySlug,
                friendlyId          : countrySlug,
                parentId            : region.id,
                additionalDetailsMap: [source: "GADM-4.1-AutoParent", importedAt: new Date().toString(), level: 0, gid: countrySlug]
            ])
            if (r.code in 200..299) {
                country = new JsonSlurper().parseText(r.body)
                log.info("${logPrefix} auto-created parent country '${countrySlug}' (${countryName}) id=${country?.id} via ${region.via}")
            } else {
                recordFailure("POST country ${countrySlug} (auto-parent)", r.code, r.body)
            }
        }
        if (country?.id == null) {
            throw new IllegalStateException("Country '${countrySlug}' not found in backend; import level 0 (or level 1) before level ${locationLevel}.")
        }

        if (type == "province") {
            resolvedParentId = country.id
        } else {
            // Candidate parents are limited to THIS country, so equal province or
            // city names in other countries can never be picked.
            def provinces = getAllPages("${backendBaseUrl}/api/v1/geolocations/province/search-by-name?parentId=${country.id}&namePrefix=") ?: []
            if (provinces.isEmpty()) throw new IllegalStateException("Country '${countrySlug}' has no provinces; import level 1 before level ${locationLevel}.")
            def candidates = provinces
            if (type == "district") {
                candidates = provinces.collectMany { p -> getAllPages("${backendBaseUrl}/api/v1/geolocations/city/search-by-name?parentId=${p.id}&namePrefix=") ?: [] }
                if (candidates.isEmpty()) throw new IllegalStateException("Country '${countrySlug}' has no cities; import level 2 before level ${locationLevel}.")
            }
            parentIndex = buildParentIndex(candidates)
            log.info("${logPrefix} indexed ${candidates.size()} candidate parent(s) for ${type} records")
        }
    }

    // 2. Load existing records for idempotency (page-based bulk load)
    def existingMap = [:]
    def firstPage = getJson("${backendBaseUrl}/api/v1/geolocations/${type}?page=0&size=2000")
    firstPage?.content?.each { if (it.friendlyId) existingMap[it.friendlyId] = it.id }
    def totalPages = firstPage?.page?.totalPages ?: 0
    for (int pIdx = 1; pIdx < totalPages; pIdx++) {
        getJson("${backendBaseUrl}/api/v1/geolocations/${type}?page=${pIdx}&size=2000")?.content?.each {
            if (it.friendlyId) existingMap[it.friendlyId] = it.id
        }
    }

    // 3. Process features with a thread pool
    def threadPoolSize = (features.size() > 50) ? 15 : 1
    def executor = Executors.newFixedThreadPool(threadPoolSize)

    def tasks = features.collect { feature ->
        return { ->
            def props = feature.get('properties') ?: [:]   // not .properties / ['properties']: newer Groovy resolves those to Object.getProperties()
            def name = countrySlug
            def alias = countrySlug
            def friendlyId = countrySlug
            def featureParentId = resolvedParentId

            def gid = null
            if (locationLevel == 0) {
                name = props.COUNTRY ?: countrySlug
                alias = props.GID_0 ?: countrySlug
                friendlyId = alias
                gid = props.GID_0
            } else if (locationLevel == 1) {
                name = props.NAME_1 ?: props.COUNTRY ?: countrySlug
                alias = present(props.ISO_1) ? props.ISO_1 : (present(props.HASC_1) ? props.HASC_1 : (props.GID_1 ?: countrySlug))
                friendlyId = alias
                gid = props.GID_1
            } else if (locationLevel == 2) {
                name = props.NAME_2 ?: props.NAME_1 ?: countrySlug
                alias = props.GID_2 ?: props.NAME_2 ?: countrySlug
                friendlyId = props.GID_2 ?: alias
                gid = props.GID_2
                featureParentId = resolveFeatureParent(parentIndex, props, 2)
            } else {
                name = props.NAME_3 ?: props.NAME_2 ?: countrySlug
                alias = props.GID_3 ?: props.NAME_3 ?: countrySlug
                friendlyId = props.GID_3 ?: alias
                gid = props.GID_3
                featureParentId = resolveFeatureParent(parentIndex, props, 3)
            }

            if (featureParentId == null) {
                def parentRef = locationLevel == 2 ? "${props.GID_1} / ${props.NAME_1}" : "${props.GID_2} / ${props.NAME_2}"
                recordFailure("${type} ${friendlyId}", -1, "no parent found for ${parentRef}")
                return null
            }

            def payload = [
                name                  : name,
                alias                 : alias,
                friendlyId            : friendlyId,
                parentId              : featureParentId,
                boundaryRepresentation: (feature.geometry != null) ? JsonOutput.toJson(feature.geometry) : null,
                additionalDetailsMap  : [
                    source    : "GADM-4.1",
                    importedAt: new Date().toString(),
                    level     : locationLevel,
                    gid       : gid,
                    hasc      : [props.HASC_3, props.HASC_2, props.HASC_1].find { present(it) },
                    iso       : props.ISO_1 ?: null,
                    ibge      : props.CC_2 ?: null,
                    engtype   : props.ENGTYPE_2 ?: props.ENGTYPE_1 ?: null,
                    stateType : props.TYPE_2 ?: props.TYPE_1 ?: null
                ]
            ]

            def existingId = existingMap[friendlyId]
            try {
                if (existingId != null) {
                    def r = http("PUT", "${backendBaseUrl}/api/v1/geolocations/${type}/${existingId}", payload)
                    if (r.code in 200..299) updatedCounter.incrementAndGet()
                    else recordFailure("PUT ${type} ${friendlyId}", r.code, r.body)
                } else {
                    def r = http("POST", "${backendBaseUrl}/api/v1/geolocations/${type}", payload)
                    if (r.code in 200..299) createdCounter.incrementAndGet()
                    else recordFailure("POST ${type} ${friendlyId}", r.code, r.body)
                }
            } catch (Exception e) {
                // Connection refused/timeouts: count them instead of losing them inside invokeAll.
                recordFailure("${existingId != null ? 'PUT' : 'POST'} ${type} ${friendlyId}", -1, "${e.class.simpleName}: ${e.message}")
            }
            return null
        } as Callable<Void>
    }

    try {
        executor.invokeAll(tasks)
    } finally {
        executor.shutdown()
        executor.awaitTermination(5, TimeUnit.MINUTES)
    }

    def summary = buildSummary(null)
    if (summary.failedCount > 0) {
        log.warn("${logPrefix} finished with ${summary.failedCount} failure(s): created=${summary.createdCount} updated=${summary.updatedCount}")
    } else {
        log.info("${logPrefix} finished: created=${summary.createdCount} updated=${summary.updatedCount} in ${summary.durationMs}ms")
    }
    emitSummary(summary)
} catch (Exception e) {
    // Still answer the workflow (via step 9) instead of dropping the flowfile on
    // the auto-terminated failure relationship.
    def message = "${e.class.simpleName}: ${e.message ?: 'Ingestion failed'}"
    log.error("${logPrefix} ingestion aborted: ${message}", e)
    emitSummary(buildSummary(message))
}
