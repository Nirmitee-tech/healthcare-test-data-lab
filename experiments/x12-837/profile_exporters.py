"""Code systems and NPI formats in Synthea's CSV and CPCDS exports (run_synthea.sh output).
Unit: CSV row (claim line for CPCDS, claim for claims.csv, transaction for claims_transactions.csv)."""
import collections
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "synthea-out/synthea-false")
out = {}
rows = list(csv.DictReader(open(root / "cpcds/CPCDS_Claims.csv")))
c = lambda k: dict(collections.Counter(r[k] or "(empty)" for r in rows).most_common(12))
out["cpcds"] = {"rows": len(rows), "Diagnosis code type": c("Diagnosis code type"),
                "Procedure code type": c("Procedure code type"), "Place of service code": c("Place of service code"),
                "Claim type": c("Claim type"),
                "billing NPI length": dict(collections.Counter(len(r["Claim billing provider NPI"]) for r in rows)),
                "Modifier Code-1 filled": sum(bool(r["Modifier Code-1"]) for r in rows)}
cl = list(csv.DictReader(open(root / "csv/claims.csv")))
out["csv_claims"] = {"rows": len(cl), "DIAGNOSIS1 filled": sum(bool(r["DIAGNOSIS1"]) for r in cl),
                     "DIAGNOSIS1 all digits (SNOMED-shaped, ICD-10-CM starts with a letter)":
                         sum(r["DIAGNOSIS1"].isdigit() for r in cl if r["DIAGNOSIS1"])}
tx = [r for r in csv.DictReader(open(root / "csv/claims_transactions.csv")) if r["TYPE"] == "CHARGE"]
out["csv_claims_transactions_CHARGE"] = {
    "rows": len(tx), "PROCEDURECODE all digits": sum(r["PROCEDURECODE"].isdigit() for r in tx),
    "PROCEDURECODE 5 chars (CPT/HCPCS-shaped)": sum(len(r["PROCEDURECODE"]) == 5 for r in tx),
    "MODIFIER1 filled": sum(bool(r["MODIFIER1"]) for r in tx),
    "PLACEOFSERVICE sample": tx[0]["PLACEOFSERVICE"] if tx else None}
print(json.dumps(out, indent=1))
