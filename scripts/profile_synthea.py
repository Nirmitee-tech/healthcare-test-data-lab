"""Profile Synthea FHIR output: resource mix, identifier systems and value patterns.

Read-only. Usage: python3 scripts/profile_synthea.py out/synthea/fhir > out/profile.json
Scope: every *.json bundle in the folder. Unit: FHIR resource (unless stated).
"""
import collections
import json
import re
import sys
from pathlib import Path


def load_bundles(folder):
    for p in sorted(Path(folder).glob("*.json")):
        yield p.name, json.loads(p.read_text())


def profile(folder):
    types = collections.Counter()
    id_systems = collections.Counter()
    npi_values = {"Practitioner": set(), "Organization": set()}
    ssn = []
    phones = []
    names_with_digits = 0
    patients = 0
    profiles = collections.Counter()
    for fname, b in load_bundles(folder):
        for e in b.get("entry", []):
            r = e["resource"]
            rt = r["resourceType"]
            types[rt] += 1
            for prof in r.get("meta", {}).get("profile", []):
                profiles[(rt, prof)] += 1
            for ident in r.get("identifier", []):
                sysname = ident.get("system", "(none)")
                id_systems[(rt, sysname)] += 1
                if sysname.endswith("us-npi") and rt in npi_values:
                    npi_values[rt].add(ident.get("value"))
                if sysname.endswith("us-ssn"):
                    ssn.append(ident.get("value"))
            if rt == "Patient":
                patients += 1
                for t in r.get("telecom", []):
                    if t.get("system") == "phone":
                        phones.append(t.get("value"))
                for n in r.get("name", []):
                    parts = n.get("given", []) + [n.get("family", "")]
                    if any(re.search(r"\d", x) for x in parts):
                        names_with_digits += 1
                        break
    return {
        "scope": f"all bundles in {folder}",
        "patients": patients,
        "resource_types": dict(types.most_common()),
        "identifier_systems": {f"{k[0]} | {k[1]}": v for k, v in id_systems.most_common()},
        "meta_profiles": {f"{k[0]} | {k[1]}": v for k, v in profiles.most_common()},
        "npi_distinct": {k: len(v) for k, v in npi_values.items()},
        "npi_samples": {k: sorted(v)[:5] for k, v in npi_values.items()},
        "npi_prefixes": {k: dict(collections.Counter(x[:4] for x in v)) for k, v in npi_values.items()},
        "ssn_count": len(ssn),
        "ssn_area_prefixes": dict(collections.Counter(s[:3] for s in ssn)),
        "phone_samples": phones[:5],
        "phones_with_555_exchange": sum(1 for p in phones if re.match(r"^\D*\d{3}\D*555", p or "")),
        "phone_count": len(phones),
        "patients_with_digits_in_name": names_with_digits,
    }


if __name__ == "__main__":
    print(json.dumps(profile(sys.argv[1]), indent=2))
