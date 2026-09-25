// Offline test harness for 08-ingest-backend-and-summarize.groovy: runs the script
// against an in-memory stub of the backend GeoLocation API. Run: make test-nifi-scripts
import com.sun.net.httpserver.HttpServer
import groovy.json.JsonOutput
import groovy.json.JsonSlurper

def scriptPath = args[0]
def store = []
def nextId = 1000
def requests = []

def server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0)
server.createContext("/") { ex ->
    def uri = ex.requestURI
    def path = uri.path
    def q = [:]
    (uri.rawQuery ?: "").split("&").findAll { it }.each { kv ->
        def (k, v) = (kv.split("=", 2) as List) + [""]
        q[k] = URLDecoder.decode(v, "UTF-8")
    }
    def m = path =~ /\/api\/v1\/geolocations\/([a-z]+)(?:\/(.+))?/
    m.find()
    def type = m.group(1).toUpperCase()
    def rest = m.group(2)
    def body = ex.requestBody.text
    requests << "${ex.requestMethod} ${path}"
    def page = { List items -> [content: items, page: [size: 1000, number: 0, totalElements: items.size(), totalPages: items ? 1 : 0]] }
    def out
    int code = 200
    if (ex.requestMethod == "GET" && rest == null) {
        out = page(store.findAll { it.type == type })
    } else if (ex.requestMethod == "GET" && rest == "search-by-friendlyid") {
        out = page(store.findAll { it.type == type && it.friendlyId == q.friendlyId })
    } else if (ex.requestMethod == "GET" && rest == "search-by-name") {
        out = page(store.findAll { it.type == type && it.parentId == (q.parentId as Long) && it.name.toLowerCase().startsWith(q.namePrefix.toLowerCase()) })
    } else if (ex.requestMethod == "POST") {
        def rec = new JsonSlurper().parseText(body) + [type: type, id: nextId++]
        rec.remove("boundaryRepresentation")
        store << rec
        out = rec
    } else if (ex.requestMethod == "PUT") {
        def rec = store.find { it.id == (rest as Long) }
        rec.putAll(new JsonSlurper().parseText(body)); rec.remove("boundaryRepresentation")
        out = rec
    } else { code = 404; out = [error: "nope"] }
    def bytes = JsonOutput.toJson(out).getBytes("UTF-8")
    ex.sendResponseHeaders(code, bytes.length)
    ex.responseBody.withCloseable { it.write(bytes) }
}
server.start()
def base = "http://127.0.0.1:${server.address.port}"
def source = new File(scriptPath).text.replace("http://bookanything-monolith-backend-01.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8060", base)

def run = { Map attrs, Map geojson ->
    def result = [:]
    def ff = new Expando(attrs: attrs)
    ff.getAttribute = { String k -> attrs[k] }
    def session = new Expando()
    session.get = { -> ff }
    session.read = { f, cb -> cb.process(new ByteArrayInputStream(JsonOutput.toJson(geojson).getBytes("UTF-8"))) }
    session.write = { f, cb -> def bos = new ByteArrayOutputStream(); cb.process(bos); result.summary = new JsonSlurper().parseText(bos.toString("UTF-8")); f }
    session.putAttribute = { f, k, v -> f }
    session.transfer = { f, rel -> result.rel = rel }
    def logs = []
    def log = new Expando()
    ["info", "warn", "error"].each { lvl -> log."$lvl" = { String msg, Object... ignored -> logs << "${lvl.toUpperCase()} ${msg}" } }
    def binding = new Binding(session: session, log: log, REL_SUCCESS: "success")
    new GroovyShell(binding).evaluate(source)
    result.logs = logs
    return result
}

def failures = 0
def check = { String name, boolean ok, detail = "" ->
    println "${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : ' -> ' + detail}"
    if (!ok) failures++
}
def feature = { Map props -> [type: "Feature", properties: props, geometry: null] }

// Reference data
store << [type: "CONTINENT", id: 1, friendlyId: "AME", name: "Americas"]
store << [type: "REGION", id: 11, friendlyId: "SAM", name: "South America", parentId: 1, additionalDetailsMap: [memberCountriesIso3: ["BRA", "ARG"]]]
store << [type: "REGION", id: 12, friendlyId: "NAR", name: "Northern America", parentId: 1, additionalDetailsMap: [memberCountriesIso3: ["USA", "CAN"]]]

// 1. Country: parent from memberCountriesIso3, name from GADM
def r1 = run([jobId: "j1", countrySlug: "USA", locationLevel: "0"], [features: [feature([GID_0: "USA", COUNTRY: "United States"])]])
def usa = store.find { it.type == "COUNTRY" && it.friendlyId == "USA" }
check("country parent resolved via memberCountriesIso3", usa?.parentId == 12, "usa=${usa} summary=${r1.summary}")
check("country name taken from GADM COUNTRY", usa?.name == "United States", usa?.name)
check("country summary createdCount=1 failed=0", r1.summary.createdCount == 1 && r1.summary.failedCount == 0, r1.summary)

// 2. Unknown country: clear error, no POST
def before = store.size()
def r2 = run([jobId: "j2", countrySlug: "ZZZ", locationLevel: "0"], [features: [feature([GID_0: "ZZZ", COUNTRY: "Nowhere"])]])
check("unknown country aborts with a clear message", r2.summary.errorMessage?.contains("No REGION lists 'ZZZ'") && store.size() == before, r2.summary)
check("unknown country still answers on success", r2.rel == "success", r2.rel)

// 3. parentFriendlyId override
def r3 = run([jobId: "j3", countrySlug: "ZZZ", locationLevel: "0", parentFriendlyId: "SAM"], [features: [feature([GID_0: "ZZZ", COUNTRY: "Nowhere"])]])
check("parentFriendlyId override is used", store.find { it.friendlyId == "ZZZ" }?.parentId == 11, r3.summary)

// 4. Province of a country not imported yet: auto-create country under its region, named from GADM
def r4 = run([jobId: "j4", countrySlug: "BRA", locationLevel: "1"], [features: [
    feature([GID_0: "BRA", COUNTRY: "Brazil", GID_1: "BRA.25_1", NAME_1: "SãoPaulo", ISO_1: "BR-SP", HASC_1: "BR.SP"]),
    feature([GID_0: "BRA", COUNTRY: "Brazil", GID_1: "BRA.19_1", NAME_1: "RiodeJaneiro", ISO_1: "BR-RJ", HASC_1: "BR.RJ"])]])
def bra = store.find { it.type == "COUNTRY" && it.friendlyId == "BRA" }
check("auto-created country under SAM named Brazil", bra?.parentId == 11 && bra?.name == "Brazil", bra)
def sp = store.find { it.type == "PROVINCE" && it.friendlyId == "BR-SP" }
check("provinces created under the country with gid", sp?.parentId == bra?.id && sp?.additionalDetailsMap?.gid == "BRA.25_1", sp)

// A same-named province in another country must never be picked
store << [type: "PROVINCE", id: 900, friendlyId: "XX-SP", name: "SãoPaulo", parentId: usa.id, additionalDetailsMap: [:]]
// Legacy province without gid (as imported before this version): matched by HASC / name
store << [type: "PROVINCE", id: 901, friendlyId: "BR-MG", name: "MinasGerais", parentId: bra.id, additionalDetailsMap: [hasc: "BR.MG", iso: "BR-MG"]]

// 5. Cities: gid match, HASC match, accent-insensitive name match, unmatched -> failed
def r5 = run([jobId: "j5", countrySlug: "BRA", locationLevel: "2"], [features: [
    feature([GID_1: "BRA.25_1", NAME_1: "whatever", GID_2: "BRA.25.1_1", NAME_2: "Campinas"]),
    feature([GID_1: "BRA.13_1", NAME_1: "Minas", HASC_2: "BR.MG.BH", GID_2: "BRA.13.1_1", NAME_2: "BeloHorizonte"]),
    feature([GID_1: "BRA.99_1", NAME_1: "Rio de Janeiro", GID_2: "BRA.19.1_1", NAME_2: "Niteroi"]),
    feature([GID_1: "BRA.77_1", NAME_1: "Atlantis", GID_2: "BRA.77.1_1", NAME_2: "Nowhere"])]])
def city = { fid -> store.find { it.type == "CITY" && it.friendlyId == fid } }
check("city parent via gid", city("BRA.25.1_1")?.parentId == sp.id, city("BRA.25.1_1"))
check("city parent via HASC prefix (legacy province)", city("BRA.13.1_1")?.parentId == 901, city("BRA.13.1_1"))
def rj = store.find { it.type == "PROVINCE" && it.friendlyId == "BR-RJ" }
check("city parent via accent/space-insensitive name", city("BRA.19.1_1")?.parentId == rj.id, city("BRA.19.1_1"))
check("unmatched city is failed, not created parentless", city("BRA.77.1_1") == null && r5.summary.failedCount == 1 && r5.summary.errorMessage?.contains("no parent found"), r5.summary)
check("city summary created=3", r5.summary.createdCount == 3, r5.summary)

// 6. Re-running the country import updates instead of creating
def r6 = run([jobId: "j6", countrySlug: "USA", locationLevel: "0"], [features: [feature([GID_0: "USA", COUNTRY: "United States"])]])
check("re-import updates existing country", r6.summary.updatedCount == 1 && r6.summary.createdCount == 0, r6.summary)

server.stop(0)
println(failures == 0 ? "ALL PASSED" : "${failures} FAILED")
System.exit(failures == 0 ? 0 : 1)
