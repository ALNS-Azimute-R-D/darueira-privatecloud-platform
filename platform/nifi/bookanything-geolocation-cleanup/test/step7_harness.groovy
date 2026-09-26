// Offline test harness for 07-summarize-cleanup.groovy. Run: make test-nifi-cleanup-script
import groovy.json.JsonSlurper

def scriptPath = args[0]
def source = new File(scriptPath).text

def run = { Map attrs, Long entryDate = System.currentTimeMillis() - 1500 ->
    def result = [:]
    def ff = new Expando(attrs: attrs)
    ff.getAttribute = { String k -> attrs[k] }
    ff.getEntryDate = { -> entryDate }
    def session = new Expando()
    session.get = { -> ff }
    session.write = { f, cb -> def bos = new ByteArrayOutputStream(); cb.process(bos); result.summary = new JsonSlurper().parseText(bos.toString("UTF-8")); f }
    session.putAttribute = { f, k, v -> result[k] = v; f }
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

def base = [jobId: "geo-cleanup-1", countrySlug: "BRA", locationLevel: "1"]

def r1 = run(base + [shouldDeleteJsonFile: "true", shouldDeleteXmlFile: "true"])
check("both files deleted", r1.summary.deletedJson == true && r1.summary.deletedXml == true && r1.summary.failedCount == 0, r1.summary)
check("echoes job, country and level", r1.summary.jobId == "geo-cleanup-1" && r1.summary.countrySlug == "BRA" && r1.summary.locationLevel == 1, r1.summary)
check("no errorMessage on success", !r1.summary.containsKey("errorMessage"), r1.summary)
check("duration measured from the entry date", r1.summary.durationMs >= 1000, r1.summary.durationMs)
check("answers on success with a JSON mime type", r1.rel == "success" && r1["mime.type"] == "application/json", r1)

def r2 = run(base + [shouldDeleteJsonFile: "true", shouldDeleteXmlFile: "false"])
check("only the requested file counts as deleted", r2.summary.deletedJson == true && r2.summary.deletedXml == false, r2.summary)

def r3 = run(base + [shouldDeleteJsonFile: "false", shouldDeleteXmlFile: "false"])
check("nothing requested, nothing deleted", r3.summary.deletedJson == false && r3.summary.deletedXml == false && r3.summary.failedCount == 0, r3.summary)

def r4 = run(base + [shouldDeleteJsonFile: "TRUE", shouldDeleteXmlFile: "true", jsonError: "Access Denied"])
check("flag is case-insensitive", r4.summary.deletedXml == true, r4.summary)
check("a JSON failure is reported and not counted as deleted", r4.summary.deletedJson == false && r4.summary.failedCount == 1 && r4.summary.errorMessage.contains("raw JSON: Access Denied"), r4.summary)

def r5 = run(base + [shouldDeleteJsonFile: "true", shouldDeleteXmlFile: "true", jsonError: "timeout", xmlError: "no such bucket"])
check("both failures are reported", r5.summary.failedCount == 2 && r5.summary.errorMessage.contains("XML: no such bucket") && r5.summary.deletedJson == false && r5.summary.deletedXml == false, r5.summary)

def r6 = run([jobId: "j", countrySlug: "PRT", locationLevel: "not-a-number", shouldDeleteJsonFile: "true"])
check("an exception still answers, with an errorMessage", r6.rel == "success" && r6.summary.errorMessage?.startsWith("Could not summarize") && r6.summary.failedCount == 1, r6)
check("the fallback keeps job and country", r6.summary.jobId == "j" && r6.summary.countrySlug == "PRT", r6.summary)

println(failures == 0 ? "ALL PASSED" : "${failures} FAILED")
System.exit(failures == 0 ? 0 : 1)
