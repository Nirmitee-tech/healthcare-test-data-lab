"""Load bundles into a FHIR server and check the server holds what the manifest says it should.

Order matters: Synthea patient bundles point at practitioners and facilities through conditional
references (Practitioner?identifier=...), so the hospital and practitioner bundles go first.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from lab.fhirutil import read_bundles
from lab.messify import LOCAL_LAB_SYSTEM


def _req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _order(path):
    name = path.name
    return 0 if name.startswith("hospital") else 1 if name.startswith("practitioner") else 2


def load_folder(base, folder):
    results = {"loaded": 0, "rejected": []}
    for path, bundle in sorted(read_bundles(folder), key=lambda pb: (_order(pb[0]), pb[0].name)):
        status, body = _req("POST", base, bundle)
        if status >= 300:
            msg = "; ".join(i.get("diagnostics", "") for i in body.get("issue", []))[:300]
            results["rejected"].append({"bundle": path.name, "status": status, "message": msg})
        else:
            results["loaded"] += 1
    return results


def count(base, query):
    sep = "&" if "?" in query else "?"
    status, body = _req("GET", f"{base}/{query}{sep}_summary=count")
    if status != 200:
        raise RuntimeError(f"GET {query} -> {status}")
    return body.get("total", 0)


def check_against_manifest(base, folder):
    """Compare server counts with the defect manifest. Returns (checks, all_ok)."""
    manifest_path = Path(folder) / "defects.manifest.jsonl"
    manifest = [json.loads(x) for x in manifest_path.read_text().splitlines()] if manifest_path.exists() else []
    expected = {}
    for m in manifest:
        expected[m["defect"]] = expected.get(m["defect"], 0) + 1
    patients_in_files = sum(1 for _, b in read_bundles(folder) for e in b.get("entry", [])
                            if e["resource"].get("resourceType") == "Patient")
    checks = [
        ("Patient total (incl. injected duplicates)", patients_in_files, count(base, "Patient")),
        ("Observations with local lab code", expected.get("lab_local_code", 0),
         count(base, "Observation?code=" + urllib.parse.quote(LOCAL_LAB_SYSTEM + "|", safe=""))),
        ("Body weights in [lb_av]", expected.get("weight_in_lbs", 0),
         count(base, "Observation?code=http://loinc.org|29463-7&value-quantity=" +
               urllib.parse.quote("gt0|http://unitsofmeasure.org|[lb_av]", safe=""))),
    ]
    rows = [{"check": c, "expected": e, "server": s, "ok": e == s} for c, e, s in checks]
    return rows, all(r["ok"] for r in rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder")
    ap.add_argument("--base", default="http://localhost:8090/fhir")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args(argv)
    if not args.check_only:
        res = load_folder(args.base, args.folder)
        print(json.dumps(res, indent=2))
        if res["rejected"]:
            return 1
    rows, ok = check_against_manifest(args.base, args.folder)
    print(json.dumps(rows, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
