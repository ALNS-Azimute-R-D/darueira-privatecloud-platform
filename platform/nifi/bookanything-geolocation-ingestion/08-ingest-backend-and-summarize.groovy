// =============================================================================
// NiFi ExecuteScript body: "8. Ingest Backend & Summarize"
// Process group: "BookAnything - GeoLocation Ingestion Pipeline"
//
// Source of truth for the live processor's "Script Body". Apply with:
//   scripts/apply_nifi_script_body.sh "8. Ingest Backend & Summarize" \
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
// =============================================================================
import groovy.json.JsonSlurper
import groovy.json.JsonOutput
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
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

def regionFriendlyIdFor = { String slug ->
    (slug in ["DEU", "DE", "AUT", "CHE", "FRA", "NLD", "BEL", "ITA", "ESP", "PRT", "GBR"]) ? "WEU" : "SAM"
}

def findRegionId = {
    def target = regionFriendlyIdFor(countrySlug)
    def resp = getJson("${backendBaseUrl}/api/v1/geolocations/region?size=50")
    def match = resp?.content?.find { it.friendlyId == target || it.alias == target }
    if (match == null && resp?.content) {
        log.warn("${logPrefix} region '${target}' not found, falling back to first region '${resp.content[0]?.friendlyId}'")
    }
    return match?.id ?: (resp?.content ? resp.content[0]?.id : null)
}

def buildSummary = { String errorMessage ->
    def failed = failedCounter.get()
    def message = errorMessage
    if (message == null && failed > 0) {
        message = "${failed} backend call(s) failed. First errors: " + errorSamples.join(" | ")
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

    // 1. Resolve parents and hierarchy caches
    def resolvedParentId = null
    def provincesMap = [:]

    if (type == "country") {
        resolvedParentId = findRegionId()
        if (resolvedParentId == null) {
            throw new IllegalStateException("No REGION found in backend (expected friendlyId '${regionFriendlyIdFor(countrySlug)}'). Create the continent/region hierarchy before importing countries.")
        }
    } else if (type == "province") {
        def cResp = getJson("${backendBaseUrl}/api/v1/geolocations/country/search-by-friendlyid?friendlyId=${URLEncoder.encode(countrySlug, 'UTF-8')}")
        def match = cResp?.content?.find { it.friendlyId == countrySlug || it.alias == countrySlug }
        resolvedParentId = match?.id ?: (cResp?.content ? cResp.content[0]?.id : null)

        if (resolvedParentId == null) {
            // Country not imported yet: create a minimal one under its region.
            def regId = findRegionId()
            if (regId == null) {
                throw new IllegalStateException("Country '${countrySlug}' not found and no REGION exists to create it under. Create the continent/region hierarchy first.")
            }
            def countryName = countrySlug == "BRA" ? "Brazil" : (countrySlug == "DEU" ? "Germany" : countrySlug)
            def r = http("POST", "${backendBaseUrl}/api/v1/geolocations/country", [
                name                : countryName,
                alias               : countrySlug,
                friendlyId          : countrySlug,
                parentId            : regId,
                additionalDetailsMap: [source: "GADM-4.1-AutoParent", importedAt: new Date().toString(), level: 0]
            ])
            if (r.code in 200..299) {
                resolvedParentId = new JsonSlurper().parseText(r.body)?.id
                log.info("${logPrefix} auto-created parent country '${countrySlug}' id=${resolvedParentId}")
            } else {
                recordFailure("POST country ${countrySlug} (auto-parent)", r.code, r.body)
            }
        }
        if (resolvedParentId == null) {
            throw new IllegalStateException("Could not resolve parent country '${countrySlug}' for provinces.")
        }
    } else if (type == "city") {
        def pResp = getJson("${backendBaseUrl}/api/v1/geolocations/province?size=200")
        pResp?.content?.each { p ->
            if (p.name) {
                provincesMap[p.name.replaceAll("\\s+", "")] = p.id
                provincesMap[p.name.toLowerCase()] = p.id
                provincesMap[p.name] = p.id
            }
            if (p.alias) provincesMap[p.alias] = p.id
            if (p.friendlyId) provincesMap[p.friendlyId] = p.id
        }
        if (provincesMap.isEmpty()) {
            throw new IllegalStateException("No provinces found in backend; import level 1 before level 2.")
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
            def props = feature.properties ?: [:]
            def name = countrySlug
            def alias = countrySlug
            def friendlyId = countrySlug
            def featureParentId = resolvedParentId

            if (locationLevel == 0) {
                name = props.COUNTRY ?: (countrySlug == "DEU" ? "Germany" : (countrySlug == "BRA" ? "Brazil" : countrySlug))
                alias = props.GID_0 ?: countrySlug
                friendlyId = alias
            } else if (locationLevel == 1) {
                name = props.NAME_1 ?: props.COUNTRY ?: countrySlug
                alias = (props.ISO_1 && props.ISO_1 != "NA") ? props.ISO_1 : ((props.HASC_1 && props.HASC_1 != "NA") ? props.HASC_1 : (props.GID_1 ?: countrySlug))
                friendlyId = (props.ISO_1 && props.ISO_1 != "NA") ? props.ISO_1 : ((props.HASC_1 && props.HASC_1 != "NA") ? props.HASC_1 : (props.GID_1 ?: alias))
            } else if (locationLevel == 2) {
                name = props.NAME_2 ?: props.NAME_1 ?: countrySlug
                alias = props.GID_2 ?: props.NAME_2 ?: countrySlug
                friendlyId = props.GID_2 ?: alias
                def provClean = (props.NAME_1 ?: '').replaceAll("\\s+", "")
                featureParentId = provincesMap[provClean] ?: provincesMap[props.ISO_1] ?: provincesMap[props.HASC_1]
            } else {
                name = props.NAME_3 ?: props.NAME_2 ?: countrySlug
                alias = props.GID_3 ?: props.NAME_3 ?: countrySlug
                friendlyId = props.GID_3 ?: alias
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
                    hasc      : props.HASC_2 ?: props.HASC_1 ?: null,
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
