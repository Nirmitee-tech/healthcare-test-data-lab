"""Which manifest defects can reach the v2 feed at all? Unit stated per row.

Reads fhir-messy bundles + manifest and applies the same selection rule as lab/to_hl7v2.py
(first Patient only; Observations referenced by a DiagnosticReport with category LAB).
"""
import collections
import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "../../out/run/fhir-messy")
man = [json.loads(l) for l in open(root / "defects.manifest.jsonl")]
in_lab_report, first_patient = set(), set()
for p in root.glob("*.json"):
    b = json.loads(p.read_text())
    if b.get("type") != "transaction":
        continue
    pats = [e["resource"]["id"] for e in b["entry"] if e["resource"]["resourceType"] == "Patient"]
    if pats:
        first_patient.add(pats[0])
    full = {e.get("fullUrl"): e["resource"] for e in b["entry"]}
    for e in b["entry"]:
        r = e["resource"]
        if r["resourceType"] == "DiagnosticReport" and any(
                c.get("code") == "LAB" for cat in r.get("category", []) for c in cat.get("coding", [])):
            for x in r.get("result", []):
                o = full.get(x.get("reference"))
                if o:
                    in_lab_report.add(o["id"])
rows = collections.Counter()
for m in man:
    d = m["defect"]
    if m["resourceType"] == "Observation":
        rows[(d, "unit=Observation", "in LAB report" if m["id"] in in_lab_report else "NOT in LAB report")] += 1
    else:
        rows[(d, "unit=Patient", "first Patient (written to PID)" if m["id"] in first_patient else "not first Patient (dropped)")] += 1
for k, v in sorted(rows.items()):
    print(f"{k[0]:24} {k[1]:18} {k[2]:32} {v}")
