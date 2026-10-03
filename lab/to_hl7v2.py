"""Turn FHIR patient bundles into HL7 v2.5.1 messages for interface-engine testing.

Per patient: one ADT^A04 (registration) and one ORU^R01 per lab DiagnosticReport, built from the
same resources as the FHIR feed, so a v2 channel and a FHIR endpoint see the same people. Only
defects on the Patient or on lab results reach v2 (local codes, partial birth date, MRN without a
system, padded names); duplicates, vitals in pounds and missing encounter links stay FHIR-only.
Output is one .hl7 file per patient, segments joined by CR, messages separated by CRLF, which an
interface engine file reader can split on MSH.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from lab.fhirutil import read_bundles

SENDING_APP = "SYNTHLAB"
SENDING_FAC = "SYNTHETIC-FACILITY"


def esc(value):
    """Escape HL7 v2 delimiters inside a field value."""
    s = "" if value is None else str(value)
    return (s.replace("\\", "\\E\\").replace("|", "\\F\\").replace("^", "\\S\\")
             .replace("&", "\\T\\").replace("~", "\\R\\").replace("\r", " ").replace("\n", " "))


def v2_ts(fhir_dt):
    """FHIR date or dateTime -> HL7 v2 TS (YYYYMMDD[HHMMSS][+ZZZZ])."""
    if not fhir_dt:
        return ""
    date, _, rest = fhir_dt.partition("T")
    out = date.replace("-", "")
    if rest:
        time = rest[:8].replace(":", "")
        tz = rest[8:].replace(":", "")
        tz = "+0000" if tz == "Z" else tz
        out += time + tz
    return out


def _mrn(patient):
    for i in patient.get("identifier", []):
        if any(c.get("code") == "MR" for c in i.get("type", {}).get("coding", [])):
            return i.get("value", ""), i.get("system")
    return patient.get("id", ""), None


def pid_segment(patient):
    mrn, system = _mrn(patient)
    # PID-3.4 (assigning authority) is left empty when the MRN carries no system.
    authority = "SYNTHEA" if system else ""
    name = (patient.get("name") or [{}])[0]
    given = (name.get("given") or [""])
    addr = (patient.get("address") or [{}])[0]
    phone = next((t.get("value") for t in patient.get("telecom", []) if t.get("system") == "phone"), "")
    sex = {"male": "M", "female": "F", "other": "O", "unknown": "U"}.get(patient.get("gender"), "U")
    fields = [
        "PID", "1", "",
        f"{esc(mrn)}^^^{authority}^MR",
        "",
        f"{esc(name.get('family'))}^{esc(given[0])}^{esc(given[1] if len(given) > 1 else '')}",
        "",
        v2_ts(patient.get("birthDate")),
        sex, "", "",
        "^".join([esc(" ".join(addr.get("line", []))), "", esc(addr.get("city")), esc(addr.get("state")),
                  esc(addr.get("postalCode")), esc(addr.get("country"))]),
        "",
        esc(phone),
    ]
    return "|".join(fields)


def control_id(prefix, resource_id):
    # MSH-10 allows 20 characters. Synthea ids share a per-patient prefix, so truncating them
    # collides; a hash of the full id does not (checked over all messages in the unit tests).
    return prefix + hashlib.sha1(resource_id.encode()).hexdigest()[:16]


def filler_order_number(resource_id):
    # OBR-3 allows 22 characters in v2.5.1; a 36-character UUID was flagged by the HAPI validator,
    # and truncating it collides (18 of 1,008 reports shared a 22-character prefix).
    return "R" + hashlib.sha1(resource_id.encode()).hexdigest()[:21]


def msh_segment(msg_type, control_id, ts):
    return "|".join(["MSH", "^~\\&", SENDING_APP, SENDING_FAC, "RECEIVER", "RECEIVER", ts, "",
                     msg_type, control_id, "P", "2.5.1"])


def adt_a04(patient, encounter=None):
    ts = v2_ts((encounter or {}).get("period", {}).get("start")) or v2_ts(patient.get("birthDate"))
    segs = [msh_segment("ADT^A04^ADT_A01", control_id("ADT-", patient["id"]), ts),
            "|".join(["EVN", "A04", ts]),
            pid_segment(patient)]
    pv1_class = "O"
    if encounter:
        pv1_class = {"IMP": "I", "EMER": "E", "AMB": "O"}.get(encounter.get("class", {}).get("code"), "O")
    segs.append("|".join(["PV1", "1", pv1_class]))
    return "\r".join(segs)


def _coding(cc):
    c = (cc or {}).get("coding", [{}])[0]
    system = c.get("system", "")
    sys_name = "LN" if system == "http://loinc.org" else ("SCT" if "snomed" in system else "L")
    return f"{esc(c.get('code'))}^{esc(c.get('display') or cc.get('text'))}^{sys_name}"


def obx_segment(i, obs):
    if "valueQuantity" in obs:
        vq = obs["valueQuantity"]
        vtype, value, units = "NM", vq.get("value"), f"{esc(vq.get('code'))}^{esc(vq.get('unit'))}^UCUM"
    elif "valueCodeableConcept" in obs:
        # CE, not CWE: the HAPI v2.5.1 validator allows 2 characters in OBX-2 and flagged CWE.
        vtype, value, units = "CE", _coding(obs["valueCodeableConcept"]), ""
    else:
        vtype, value, units = "ST", esc(obs.get("valueString", "")), ""
    status = {"final": "F", "preliminary": "P", "amended": "C", "corrected": "C"}.get(obs.get("status"), "F")
    return "|".join(["OBX", str(i), vtype, _coding(obs.get("code")), "", str(value) if vtype == "NM" else value,
                     units, "", "", "", "", status, "", "", v2_ts(obs.get("effectiveDateTime"))])


def oru_r01(patient, report, observations):
    ts = v2_ts(report.get("effectiveDateTime") or report.get("issued"))
    segs = [msh_segment("ORU^R01^ORU_R01", control_id("ORU-", report["id"]), ts),
            pid_segment(patient),
            "|".join(["OBR", "1", "", filler_order_number(report["id"]), _coding(report.get("code")), "", "", ts])]
    for i, obs in enumerate(observations, start=1):
        segs.append(obx_segment(i, obs))
    return "\r".join(segs)


def bundle_to_messages(bundle):
    by_ref = {}
    patient = None
    encounters = []
    reports = []
    for e in bundle.get("entry", []):
        r = e["resource"]
        by_ref[e.get("fullUrl", "")] = r
        rt = r.get("resourceType")
        if rt == "Patient" and patient is None:
            patient = r  # the first Patient is the subject; injected duplicates are ignored here
        elif rt == "Encounter":
            encounters.append(r)
        elif rt == "DiagnosticReport" and any(
                c.get("code") == "LAB" for cat in r.get("category", []) for c in cat.get("coding", [])):
            reports.append(r)
    if patient is None:
        return []
    msgs = [adt_a04(patient, encounters[0] if encounters else None)]
    for rep in reports:
        obs = [by_ref[x["reference"]] for x in rep.get("result", []) if x.get("reference") in by_ref]
        if obs:
            msgs.append(oru_r01(patient, rep, obs))
    return msgs


def convert_folder(src, dst):
    Path(dst).mkdir(parents=True, exist_ok=True)
    counts = {"files": 0, "ADT^A04": 0, "ORU^R01": 0}
    for path, bundle in read_bundles(src):
        msgs = bundle_to_messages(bundle)
        if not msgs:
            continue
        (Path(dst) / (path.stem + ".hl7")).write_text("\r\n".join(msgs) + "\r")
        counts["files"] += 1
        counts["ADT^A04"] += 1
        counts["ORU^R01"] += len(msgs) - 1
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src")
    ap.add_argument("dst")
    args = ap.parse_args(argv)
    print(json.dumps(convert_folder(args.src, args.dst), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
