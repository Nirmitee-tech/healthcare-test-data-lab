"""Build and deploy two MLLP channels on Open Integration Engine 4.5.2.

  exp-v2-strict   port 6661  HL7v2 inbound, strict parser (HAPI) + strict validation ON
  exp-v2-lenient  port 6662  HL7v2 inbound, default Mirth ER7 parser, validation OFF

Both run the same filter and transformer. The transformer reads PID-3, PID-3.4, PID-5, PID-7,
OBX-3 and OBX-5 from the engine's parsed message tree (not the raw text), flags the injected
defects, and a File Writer appends one JSON line per message to
/opt/engine/appdata/out/<channel>.jsonl. ACK is auto-generated after the source transformer.

The XML shapes come from templates/ (serialized by the engine's own classes, dump_templates.sh).
"""
import sys
import uuid
from xml.sax.saxutils import escape

from oie_api import BASE, session

V = "4.5.2"

TRANSFORMER_JS = r"""
// Field access that works for both parsers. Mirth's ER7 parser names components PID.3.4,
// the strict HAPI parser names them CX.4 and drops empty ones, so match on the numeric suffix.
function comp(el, n) {
  if (el == null || el.length() == 0) return null;
  var kids = el[0].children();
  for (var i = 0; i < kids.length(); i++) {
    var ln = kids[i].localName();
    if (ln != null && ln.match(new RegExp('\\.' + n + '$'))) return kids[i];
  }
  return null;
}
function leaf(el) {
  if (el == null) return '';
  var e = el;
  while (e.hasComplexContent() && e.children().length() > 0) e = e.children()[0];
  return String(e.text());
}
var pid = msg..PID;
var pid3 = comp(pid, 3);
var mrn = leaf(comp(pid3, 1));
var authority = leaf(comp(pid3, 4));
var pid5 = comp(pid, 5);
var family = leaf(comp(pid5, 1));
var given = leaf(comp(pid5, 2));
if (family == '' && pid5 != null) family = leaf(pid5);
var dob = leaf(comp(pid, 7));
var obx = [];
var localCodes = 0;
var allObx = msg..OBX;
for (var i = 0; i < allObx.length(); i++) {
  var o = allObx.(true)[i];
  var o3 = comp(new XMLList(o), 3);
  var code = leaf(comp(o3, 1));
  var codeSys = leaf(comp(o3, 3));
  var o5 = comp(new XMLList(o), 5);
  var value = leaf(o5);
  if (codeSys == 'L') localCodes++;
  obx.push({code: code, system: codeSys, value: value});
}
var msh9 = comp(msg..MSH, 9);
var out = {
  control_id: leaf(comp(msg..MSH, 10)),
  type: leaf(comp(msh9, 1)) + '^' + leaf(comp(msh9, 2)),
  pid3_mrn: mrn, pid3_4_authority: authority, pid5_family: family, pid5_given: given, pid7_dob: dob,
  obx_count: obx.length, obx: obx,
  flag_missing_authority: authority == '',
  flag_partial_dob: dob.length > 0 && dob.length < 8,
  flag_local_lab_codes: localCodes
};
channelMap.put('summary', JSON.stringify(out));
logger.info('[' + channelName + '] ' + JSON.stringify(out).substring(0, 300));
"""

FILTER_JS = r"""
// Reject only when the engine finds no MRN in PID-3.1. Rejected messages get an AR ACK.
// Component names differ by parser (PID.3.1 vs CX.1), so match on the numeric suffix.
function comp(el, n) {
  if (el == null || el.length() == 0) return null;
  var kids = el[0].children();
  for (var i = 0; i < kids.length(); i++) {
    var ln = kids[i].localName();
    if (ln != null && ln.match(new RegExp('\\.' + n + '$'))) return kids[i];
  }
  return null;
}
var c = comp(comp(msg..PID, 3), 1);
var mrn = '';
if (c != null) { var e = c; while (e.hasComplexContent() && e.children().length() > 0) e = e.children()[0]; mrn = String(e.text()); }
return mrn != '';
"""


def hl7_props(strict):
    s = "true" if strict else "false"
    return f"""
  <serializationProperties class="com.mirth.connect.plugins.datatypes.hl7v2.HL7v2SerializationProperties" version="{V}">
    <handleRepetitions>true</handleRepetitions>
    <handleSubcomponents>true</handleSubcomponents>
    <useStrictParser>{s}</useStrictParser>
    <useStrictValidation>{s}</useStrictValidation>
    <stripNamespaces>true</stripNamespaces>
    <segmentDelimiter>\\r</segmentDelimiter>
    <convertLineBreaks>true</convertLineBreaks>
  </serializationProperties>
  <deserializationProperties class="com.mirth.connect.plugins.datatypes.hl7v2.HL7v2DeserializationProperties" version="{V}">
    <useStrictParser>{s}</useStrictParser>
    <useStrictValidation>false</useStrictValidation>
    <segmentDelimiter>\\r</segmentDelimiter>
  </deserializationProperties>
  <batchProperties class="com.mirth.connect.plugins.datatypes.hl7v2.HL7v2BatchProperties" version="{V}">
    <splitType>MSH_Segment</splitType>
    <batchScript></batchScript>
  </batchProperties>
  <responseGenerationProperties class="com.mirth.connect.plugins.datatypes.hl7v2.HL7v2ResponseGenerationProperties" version="{V}">
    <segmentDelimiter>\\r</segmentDelimiter>
    <successfulACKCode>AA</successfulACKCode>
    <successfulACKMessage></successfulACKMessage>
    <errorACKCode>AE</errorACKCode>
    <errorACKMessage>An Error Occurred Processing Message.</errorACKMessage>
    <rejectedACKCode>AR</rejectedACKCode>
    <rejectedACKMessage>Message Rejected.</rejectedACKMessage>
    <msh15ACKAccept>false</msh15ACKAccept>
    <dateFormat>yyyyMMddHHmmss.SSS</dateFormat>
  </responseGenerationProperties>
  <responseValidationProperties class="com.mirth.connect.plugins.datatypes.hl7v2.HL7v2ResponseValidationProperties" version="{V}">
    <successfulACKCode>AA,CA</successfulACKCode>
    <errorACKCode>AE,CE</errorACKCode>
    <rejectedACKCode>AR,CR</rejectedACKCode>
    <validateMessageControlId>true</validateMessageControlId>
    <originalMessageControlId>Destination_Encoded</originalMessageControlId>
    <originalIdMapVariable></originalIdMapVariable>
  </responseValidationProperties>"""


def transformer(tag, strict, js=None):
    elements = "<elements/>"
    if js:
        elements = f"""<elements>
      <com.mirth.connect.plugins.javascriptstep.JavaScriptStep version="{V}">
        <name>extract fields</name>
        <sequenceNumber>0</sequenceNumber>
        <enabled>true</enabled>
        <script>{escape(js)}</script>
      </com.mirth.connect.plugins.javascriptstep.JavaScriptStep>
    </elements>"""
    p = hl7_props(strict)
    return f"""<{tag} version="{V}">
    {elements}
    <inboundDataType>HL7V2</inboundDataType>
    <outboundDataType>HL7V2</outboundDataType>
    <inboundProperties class="com.mirth.connect.plugins.datatypes.hl7v2.HL7v2DataTypeProperties" version="{V}">{p}
    </inboundProperties>
    <outboundProperties class="com.mirth.connect.plugins.datatypes.hl7v2.HL7v2DataTypeProperties" version="{V}">{p}
    </outboundProperties>
  </{tag}>"""


def filter_xml(js=None):
    if not js:
        return f'<filter version="{V}"><elements/></filter>'
    return f"""<filter version="{V}">
    <elements>
      <com.mirth.connect.plugins.javascriptrule.JavaScriptRule version="{V}">
        <name>has MRN</name>
        <sequenceNumber>0</sequenceNumber>
        <enabled>true</enabled>
        <script>{escape(js)}</script>
      </com.mirth.connect.plugins.javascriptrule.JavaScriptRule>
    </elements>
  </filter>"""


RESOURCES = """<resourceIds class="linked-hash-map"><entry><string>Default Resource</string><string>[Default Resource]</string></entry></resourceIds>"""


def tcp_source(port):
    return f"""    <properties class="com.mirth.connect.connectors.tcp.TcpReceiverProperties" version="{V}">
      <pluginProperties/>
      <listenerConnectorProperties version="{V}"><host>0.0.0.0</host><port>{port}</port></listenerConnectorProperties>
      <sourceConnectorProperties version="{V}">
        <responseVariable>Auto-generate (After source transformer)</responseVariable>
        <respondAfterProcessing>true</respondAfterProcessing>
        <processBatch>false</processBatch>
        <firstResponse>false</firstResponse>
        <processingThreads>1</processingThreads>
        {RESOURCES}
        <queueBufferSize>1000</queueBufferSize>
      </sourceConnectorProperties>
      <transmissionModeProperties class="com.mirth.connect.plugins.mllpmode.MLLPModeProperties">
        <pluginPointName>MLLP</pluginPointName>
        <startOfMessageBytes>0B</startOfMessageBytes>
        <endOfMessageBytes>1C0D</endOfMessageBytes>
        <useMLLPv2>false</useMLLPv2>
        <ackBytes>06</ackBytes>
        <nackBytes>15</nackBytes>
        <maxRetries>2</maxRetries>
      </transmissionModeProperties>
      <serverMode>true</serverMode>
      <remoteAddress></remoteAddress>
      <remotePort></remotePort>
      <overrideLocalBinding>false</overrideLocalBinding>
      <reconnectInterval>5000</reconnectInterval>
      <receiveTimeout>0</receiveTimeout>
      <bufferSize>65536</bufferSize>
      <maxConnections>10</maxConnections>
      <keepConnectionOpen>true</keepConnectionOpen>
      <dataTypeBinary>false</dataTypeBinary>
      <charsetEncoding>DEFAULT_ENCODING</charsetEncoding>
      <respondOnNewConnection>0</respondOnNewConnection>
      <responseAddress></responseAddress>
      <responsePort></responsePort>
    </properties>
"""


def file_source(directory):
    """File Reader with batch on: the engine splits each .hl7 file into messages on MSH."""
    return f"""    <properties class="com.mirth.connect.connectors.file.FileReceiverProperties" version="{V}">
      <pluginProperties/>
      <pollConnectorProperties version="{V}">
        <pollingType>INTERVAL</pollingType><pollOnStart>true</pollOnStart><pollingFrequency>3000</pollingFrequency>
        <pollingHour>0</pollingHour><pollingMinute>0</pollingMinute><cronJobs/>
        <pollConnectorPropertiesAdvanced><weekly>true</weekly><inactiveDays><boolean>false</boolean><boolean>false</boolean><boolean>false</boolean><boolean>false</boolean><boolean>false</boolean><boolean>false</boolean><boolean>false</boolean><boolean>false</boolean></inactiveDays><dayOfMonth>1</dayOfMonth><allDay>true</allDay><startingHour>8</startingHour><startingMinute>0</startingMinute><endingHour>17</endingHour><endingMinute>0</endingMinute></pollConnectorPropertiesAdvanced>
      </pollConnectorProperties>
      <sourceConnectorProperties version="{V}">
        <responseVariable>None</responseVariable><respondAfterProcessing>true</respondAfterProcessing>
        <processBatch>true</processBatch><firstResponse>false</firstResponse><processingThreads>1</processingThreads>
        {RESOURCES}
        <queueBufferSize>0</queueBufferSize>
      </sourceConnectorProperties>
      <scheme>FILE</scheme><host>{directory}</host><fileFilter>*.hl7</fileFilter><regex>false</regex>
      <directoryRecursion>false</directoryRecursion><ignoreDot>true</ignoreDot><anonymous>true</anonymous>
      <username>anonymous</username><password>anonymous</password><timeout>10000</timeout><secure>true</secure>
      <passive>true</passive><validateConnection>true</validateConnection><afterProcessingAction>DELETE</afterProcessingAction>
      <moveToDirectory></moveToDirectory><moveToFileName></moveToFileName><errorReadingAction>NONE</errorReadingAction>
      <errorResponseAction>AFTER_PROCESSING</errorResponseAction><errorMoveToDirectory></errorMoveToDirectory>
      <errorMoveToFileName></errorMoveToFileName><checkFileAge>true</checkFileAge><fileAge>1000</fileAge>
      <fileSizeMinimum>0</fileSizeMinimum><fileSizeMaximum></fileSizeMaximum><ignoreFileSizeMaximum>true</ignoreFileSizeMaximum>
      <sortBy>name</sortBy><binary>false</binary><charsetEncoding>DEFAULT_ENCODING</charsetEncoding>
    </properties>
"""


def channel_xml(cid, name, port, strict, source="tcp"):
    source_props = tcp_source(port) if source == "tcp" else file_source(port)
    transport = "TCP Listener" if source == "tcp" else "File Reader"
    return f"""<channel version="{V}">
  <id>{cid}</id>
  <nextMetaDataId>2</nextMetaDataId>
  <name>{name}</name>
  <description>healthcare-test-data-lab experiment: {transport} in, strict={strict}</description>
  <revision>0</revision>
  <sourceConnector version="{V}">
    <metaDataId>0</metaDataId>
    <name>sourceConnector</name>
{source_props}
    {transformer("transformer", strict, TRANSFORMER_JS)}
    {filter_xml(FILTER_JS)}
    <transportName>{transport}</transportName>
    <mode>SOURCE</mode>
    <enabled>true</enabled>
    <waitForPrevious>true</waitForPrevious>
  </sourceConnector>
  <destinationConnectors>
    <connector version="{V}">
      <metaDataId>1</metaDataId>
      <name>write summary</name>
      <properties class="com.mirth.connect.connectors.file.FileDispatcherProperties" version="{V}">
        <pluginProperties/>
        <destinationConnectorProperties version="{V}">
          <queueEnabled>false</queueEnabled>
          <sendFirst>false</sendFirst>
          <retryIntervalMillis>10000</retryIntervalMillis>
          <regenerateTemplate>false</regenerateTemplate>
          <retryCount>0</retryCount>
          <rotate>false</rotate>
          <includeFilterTransformer>false</includeFilterTransformer>
          <threadCount>1</threadCount>
          <threadAssignmentVariable></threadAssignmentVariable>
          <validateResponse>false</validateResponse>
          {RESOURCES}
          <queueBufferSize>0</queueBufferSize>
          <reattachAttachments>true</reattachAttachments>
        </destinationConnectorProperties>
        <scheme>FILE</scheme>
        <host>/opt/engine/appdata/out</host>
        <outputPattern>{name}.jsonl</outputPattern>
        <anonymous>true</anonymous>
        <username>anonymous</username>
        <password>anonymous</password>
        <timeout>10000</timeout>
        <keepConnectionOpen>true</keepConnectionOpen>
        <maxIdleTime>0</maxIdleTime>
        <secure>true</secure>
        <passive>true</passive>
        <validateConnection>true</validateConnection>
        <outputAppend>true</outputAppend>
        <errorOnExists>false</errorOnExists>
        <temporary>false</temporary>
        <binary>false</binary>
        <charsetEncoding>DEFAULT_ENCODING</charsetEncoding>
        <template>${{summary}}
</template>
      </properties>
      {transformer("transformer", strict)}
      {transformer("responseTransformer", strict)}
      {filter_xml()}
      <transportName>File Writer</transportName>
      <mode>DESTINATION</mode>
      <enabled>true</enabled>
      <waitForPrevious>true</waitForPrevious>
    </connector>
  </destinationConnectors>
  <preprocessingScript>return message;</preprocessingScript>
  <postprocessingScript>return;</postprocessingScript>
  <deployScript>return;</deployScript>
  <undeployScript>return;</undeployScript>
  <properties version="{V}">
    <clearGlobalChannelMap>true</clearGlobalChannelMap>
    <messageStorageMode>DEVELOPMENT</messageStorageMode>
    <encryptData>false</encryptData>
    <encryptAttachments>false</encryptAttachments>
    <encryptCustomMetaData>false</encryptCustomMetaData>
    <removeContentOnCompletion>false</removeContentOnCompletion>
    <removeOnlyFilteredOnCompletion>false</removeOnlyFilteredOnCompletion>
    <removeAttachmentsOnCompletion>false</removeAttachmentsOnCompletion>
    <initialState>STARTED</initialState>
    <storeAttachments>true</storeAttachments>
    <metaDataColumns/>
    <attachmentProperties version="{V}"><type>None</type><properties/></attachmentProperties>
    {RESOURCES}
  </properties>
</channel>"""


CHANNELS = [
    ("b1a1c0de-0000-4000-8000-000000006661", "exp-v2-strict", 6661, True),
    ("b1a1c0de-0000-4000-8000-000000006662", "exp-v2-lenient", 6662, False),
    # File Reader on the raw .hl7 files, to test the to_hl7v2 docstring claim that a file reader
    # can split them on MSH. "port" holds the directory here.
    ("b1a1c0de-0000-4000-8000-0000000f11e5", "exp-v2-file", "/opt/engine/appdata/in", True),
]


def main():
    s = session()
    for cid, name, port, strict in CHANNELS:
        xml = channel_xml(cid, name, port, strict, "file" if str(port).startswith("/") else "tcp")
        with open(f"channel-{name}.xml", "w") as f:
            f.write(xml)
        # POST creates; it returns false when the id exists, so update with PUT in that case.
        r = s.post(f"{BASE}/channels", data=xml.encode(), headers={"Content-Type": "application/xml"})
        if "false" in r.text:
            r = s.put(f"{BASE}/channels/{cid}", params={"override": "true"}, data=xml.encode(),
                      headers={"Content-Type": "application/xml"})
        print(name, "import", r.status_code, r.text[:300])
        r = s.post(f"{BASE}/channels/{cid}/_deploy", params={"returnErrors": "true"})
        print(name, "deploy", r.status_code, r.text[:500])
    st = s.get(f"{BASE}/channels/statuses", headers={"Accept": "application/json"})
    for d in st.json()["list"]["dashboardStatus"]:
        print(d["name"], d["state"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
