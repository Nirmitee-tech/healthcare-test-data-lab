"""Check Synthea NPIs: Luhn check digit and whether NPPES knows the number.

Read-only (GET to the public NPPES API). Usage:
  python3 scripts/check_npis.py out/synthea/csv [max_lookups]
Scope: NPI column of providers.csv and organizations.csv. Unit: distinct NPI value.
A NPPES hit means the number belongs to a real, registered provider or organization.
"""
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path


def npi_luhn_ok(npi: str) -> bool:
    # NPI check digit = Luhn over "80840" + first 9 digits.
    if not (len(npi) == 10 and npi.isdigit()):
        return False
    digits = [int(c) for c in "80840" + npi[:9]]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == int(npi[9])


def nppes_lookup(npi: str):
    url = f"https://npiregistry.cms.hhs.gov/api/?version=2.1&number={npi}"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    if not data.get("result_count"):
        return None
    res = data["results"][0]
    basic = res.get("basic", {})
    return basic.get("organization_name") or f"{basic.get('first_name','')} {basic.get('last_name','')}".strip()


def main(csv_dir, max_lookups=400):
    rows = []
    for fname, kind in (("organizations.csv", "Organization"), ("providers.csv", "Practitioner")):
        with open(Path(csv_dir) / fname, newline="") as f:
            for r in csv.DictReader(f):
                rows.append((kind, r["NAME"], r["NPI"]))
    seen = {}
    report = []
    for kind, name, npi in rows:
        if npi in seen:
            continue
        hit = None
        if npi[:1] in "12" and len(seen) < max_lookups:
            hit = nppes_lookup(npi)
            time.sleep(0.2)
        seen[npi] = hit
        report.append({"kind": kind, "synthea_name": name, "npi": npi,
                       "luhn_ok": npi_luhn_ok(npi), "nppes_match": hit})
    summary = {}
    for r in report:
        k = r["kind"]
        s = summary.setdefault(k, {"distinct_npis": 0, "luhn_ok": 0, "starts_1_or_2": 0, "found_in_nppes": 0})
        s["distinct_npis"] += 1
        s["luhn_ok"] += r["luhn_ok"]
        s["starts_1_or_2"] += r["npi"][:1] in "12"
        s["found_in_nppes"] += r["nppes_match"] is not None
    print(json.dumps({"summary": summary,
                      "nppes_hits_sample": [r for r in report if r["nppes_match"]][:10]}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 400)
