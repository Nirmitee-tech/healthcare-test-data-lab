// Run with the engine's own jars (see dump_templates.sh). Serializes default 4.5.2 objects to XML.
var S = com.mirth.connect.model.converters.ObjectXMLSerializer.getInstance();
S.init('4.5.2');
var dir = new java.io.File('/tmp/templates'); dir.mkdirs();
function dump(name, obj) {
  org.apache.commons.io.FileUtils.writeStringToFile(new java.io.File(dir, name + '.xml'), S.serialize(obj), 'UTF-8');
  print('ok ' + name);
}
dump('TcpReceiverProperties', new com.mirth.connect.connectors.tcp.TcpReceiverProperties());
dump('FileDispatcherProperties', new com.mirth.connect.connectors.file.FileDispatcherProperties());
dump('HL7v2DataTypeProperties', new com.mirth.connect.plugins.datatypes.hl7v2.HL7v2DataTypeProperties());
dump('Transformer', new com.mirth.connect.model.Transformer());
dump('Filter', new com.mirth.connect.model.Filter());
dump('JavaScriptStep', new com.mirth.connect.plugins.javascriptstep.JavaScriptStep());
dump('JavaScriptRule', new com.mirth.connect.plugins.javascriptrule.JavaScriptRule());
dump('Channel', new com.mirth.connect.model.Channel());
dump('Connector', new com.mirth.connect.model.Connector());
dump('MLLPModeProperties', new com.mirth.connect.plugins.mllpmode.MLLPModeProperties());
dump('ChannelProperties', new com.mirth.connect.model.ChannelProperties());
dump('FileReceiverProperties', new com.mirth.connect.connectors.file.FileReceiverProperties());
