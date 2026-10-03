// HAPI v2 2.3 (the library inside OIE 4.5.2) checks on every message, run with Rhino in the container.
//  1. parse with PipeParser + DefaultValidation (primitive formats: TS/DT/NM/SI etc.)
//  2. required segments and required fields per HAPI's v2.5.1 structure classes (optionality R)
//  3. field length over the v2.5.1 maximum HAPI carries for that field
// Output: one JSON line per message to stdout.
var ctx = new Packages.ca.uhn.hl7v2.DefaultHapiContext();
ctx.setValidationContext(Packages.ca.uhn.hl7v2.validation.impl.ValidationContextFactory.defaultValidation());
var parser = ctx.getPipeParser();
var encChars = null;

function walkGroup(g, path, issues) {
  var names = g.getNames();
  for (var i = 0; i < names.length; i++) {
    var n = names[i];
    var reps = g.getAll(n);
    if (g.isRequired(n) && reps.length == 0) issues.push('missing required ' + (g.isGroup(n) ? 'group ' : 'segment ') + path + n);
    for (var r = 0; r < reps.length; r++) {
      var s = reps[r];
      if (s instanceof Packages.ca.uhn.hl7v2.model.Group) { walkGroup(s, path + n + '/', issues); continue; }
      if (s.isEmpty()) { if (g.isRequired(n)) issues.push('empty required segment ' + n); continue; }
      for (var f = 1; f <= s.numFields(); f++) {
        var fld = s.getField(f);
        var segName = s.getName();
        if (segName == 'MSH' && f <= 2) continue;
        if (s.isRequired(f) && fld.length == 0) issues.push('missing required field ' + segName + '-' + f);
        var max = s.getLength(f);
        for (var k = 0; k < fld.length; k++) {
          var enc = String(fld[k].encode());
          if (max > 0 && enc.length > max) issues.push('too long ' + segName + '-' + f + ' (' + enc.length + '>' + max + ')');
        }
      }
    }
  }
}

function check(text) {
  var out = {};
  try {
    var m = parser.parse(text);
    out.structure = String(m.getName());
    var issues = [];
    walkGroup(m, '', issues);
    out.issues = issues;
  } catch (e) {
    out.parse_error = String(e.javaException ? e.javaException : e).substring(0, 300);
  }
  return out;
}

var dir = new java.io.File(arguments[0]);
var files = dir.listFiles();
java.util.Arrays.sort(files);
for (var i = 0; i < files.length; i++) {
  var name = String(files[i].getName());
  if (!name.match(/\.(hl7|txt)$/)) continue;
  var txt = String(org.apache.commons.io.FileUtils.readFileToString(files[i], 'UTF-8'));
  var segs = txt.split(/\r\n|\r|\n/).filter(function (s) { return s.trim().length > 0; });
  var msgs = [], cur = [];
  segs.forEach(function (s) { if (s.indexOf('MSH|') == 0 && cur.length) { msgs.push(cur.join('\r') + '\r'); cur = []; } cur.push(s); });
  if (cur.length) msgs.push(cur.join('\r') + '\r');
  msgs.forEach(function (m) {
    var r = check(m);
    var msh = m.split('\r')[0].split('|');
    r.file = name; r.type = msh[8] || ''; r.control_id = msh[9] || '';
    print(JSON.stringify(r));
  });
}
