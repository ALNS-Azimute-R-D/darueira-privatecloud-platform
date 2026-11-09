// =============================================================================
// NiFi ExecuteScript body: "6. Convert GeoJSON to XML"
// Process group: "BookAnything - GeoLocation Ingestion Pipeline"
//
// Turns the GADM GeoJSON flowfile into a plain XML document stored by step 7 under xml/gadm41_<ISO3>_<level>.xml
// (only when the import asked for shouldConvertToXML). Reconstructed on 2026-11-09 after the original step was
// lost with the NiFi state: nothing in the platform reads this file, it is an archive format.
//
//   <featureCollection>
//     <feature>
//       <properties><GID_1>..</GID_1><NAME_1>..</NAME_1>...</properties>
//       <geometry type="MultiPolygon"><coordinates>[[[..]]]</coordinates></geometry>
//     </feature>
//   </featureCollection>
// =============================================================================
import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import groovy.xml.XmlUtil

def flowFile = session.get()
if (!flowFile) return

def esc = { Object v -> XmlUtil.escapeXml(String.valueOf(v)) }
def tag = { String name -> name.replaceAll(/[^A-Za-z0-9_.-]/, '_').replaceAll(/^([^A-Za-z_])/, '_$1') }

try {
    def json = null
    session.read(flowFile, { inputStream ->
        json = new JsonSlurper().parse(inputStream)
    } as org.apache.nifi.processor.io.InputStreamCallback)

    flowFile = session.write(flowFile, { outputStream ->
        def w = new BufferedWriter(new OutputStreamWriter(outputStream, "UTF-8"))
        w.write('<?xml version="1.0" encoding="UTF-8"?>\n<featureCollection>\n')
        (json.get('features') ?: []).each { feature ->
            w.write('  <feature>\n    <properties>')
            (feature.get('properties') ?: [:]).each { k, v ->
                def t = tag(String.valueOf(k))
                w.write("<${t}>${v == null ? '' : esc(v)}</${t}>")
            }
            w.write('</properties>\n')
            def geometry = feature.get('geometry')
            if (geometry != null) {
                w.write("    <geometry type=\"${esc(geometry.get('type') ?: '')}\"><coordinates>")
                w.write(esc(JsonOutput.toJson(geometry.get('coordinates'))))
                w.write('</coordinates></geometry>\n')
            }
            w.write('  </feature>\n')
        }
        w.write('</featureCollection>\n')
        w.flush()
    } as org.apache.nifi.processor.io.OutputStreamCallback)
    flowFile = session.putAttribute(flowFile, "mime.type", "application/xml")
    session.transfer(flowFile, REL_SUCCESS)
} catch (Exception e) {
    log.error("GeoJSON to XML conversion failed: ${e.class.simpleName}: ${e.message}", e)
    session.transfer(flowFile, REL_FAILURE)
}
