// =============================================================================
// NiFi ExecuteScript body: "7. Summarize Cleanup"
// Process group: "BookAnything - GeoLocation Cleanup Pipeline" (ADR-0015)
//
// Source of truth for the live processor's "Script Body". Apply the whole flow with:
//   scripts/apply_nifi_cleanup_flow.py --apply
//
// Turns the attributes of the request into the summary JSON that step 8 publishes to
// geolocation.nifi-cleanup.completed (consumed by the Temporal activity deleteGeoDataFilesViaNiFi).
//
// Attributes (from "2. Extract Cleanup Attributes" and the delete steps):
//   jobId, countrySlug, locationLevel, shouldDeleteJsonFile, shouldDeleteXmlFile
//   jsonError / xmlError: set by the "Mark ... Delete Failure" steps when a DeleteS3Object failed
//
// Like step 8 of the import, it ALWAYS answers: an exception still produces a summary (with errorMessage)
// on "success", so the workflow never waits for a reply that will not come.
// =============================================================================
import groovy.json.JsonOutput
import org.apache.nifi.processor.io.OutputStreamCallback

def flowFile = session.get()
if (flowFile == null) {
    return
}

def attr = { String name -> flowFile.getAttribute(name) ?: "" }
def summary

try {
    boolean wantJson = attr("shouldDeleteJsonFile").toLowerCase() == "true"
    boolean wantXml = attr("shouldDeleteXmlFile").toLowerCase() == "true"
    String jsonError = attr("jsonError")
    String xmlError = attr("xmlError")
    def errors = []
    if (jsonError) errors << "raw JSON: ${jsonError}".toString()
    if (xmlError) errors << "XML: ${xmlError}".toString()

    long entered = flowFile.getEntryDate() ?: System.currentTimeMillis()
    summary = [
        jobId        : attr("jobId"),
        countrySlug  : attr("countrySlug"),
        locationLevel: (attr("locationLevel") ?: "0") as int,
        deletedJson  : wantJson && !jsonError,
        deletedXml   : wantXml && !xmlError,
        failedCount  : errors.size(),
        durationMs   : System.currentTimeMillis() - entered
    ]
    if (errors) {
        summary.errorMessage = errors.join(" | ")
    }
    log.info("Cleanup ${summary.countrySlug} level ${summary.locationLevel}: json=${summary.deletedJson} xml=${summary.deletedXml} failed=${summary.failedCount}".toString())
} catch (Exception e) {
    log.error("Could not summarize the cleanup: ${e.message}".toString())
    summary = [
        jobId        : attr("jobId"),
        countrySlug  : attr("countrySlug"),
        locationLevel: (attr("locationLevel")?.isInteger() ? attr("locationLevel") as int : 0),
        deletedJson  : false,
        deletedXml   : false,
        failedCount  : 1,
        durationMs   : 0,
        errorMessage : "Could not summarize the cleanup: ${e.message}".toString()
    ]
}

flowFile = session.write(flowFile, { OutputStream out ->
    out.write(JsonOutput.toJson(summary).getBytes("UTF-8"))
} as OutputStreamCallback)
flowFile = session.putAttribute(flowFile, "mime.type", "application/json")
session.transfer(flowFile, REL_SUCCESS)
