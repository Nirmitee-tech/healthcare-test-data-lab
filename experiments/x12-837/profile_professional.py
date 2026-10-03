"""Professional claims only (Claim.type = professional), unit = Claim: how many have >=1 diagnosis,
and how many items carry a SNOMED procedure vs something else. Scope: folder of FHIR bundles."""
import collections, json, sys
from pathlib import Path
c = collections.Counter()
for p in sorted(Path(sys.argv[1]).glob("*.json")):
    for e in json.loads(p.read_text()).get("entry", []):
        r = e["resource"]
        if r["resourceType"] != "Claim" or (r.get("type", {}).get("coding") or [{}])[0].get("code") != "professional":
            continue
        c["professional claims"] += 1
        c["with >=1 diagnosis"] += bool(r.get("diagnosis"))
        c["with Claim.provider NPI"] += "us-npi" in r.get("provider", {}).get("reference", "")
        c["with insurance coverage reference (member id reachable)"] += any("reference" in i.get("coverage", {}) for i in r.get("insurance", []))
        c["payer NO_INSURANCE"] += any(i.get("coverage", {}).get("display") == "NO_INSURANCE" for i in r.get("insurance", []))
print(json.dumps(c, indent=1))
