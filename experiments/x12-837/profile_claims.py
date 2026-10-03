"""Profile Synthea Claim and ExplanationOfBenefit resources against what an 837P needs.

  python3 profile_claims.py ../../out/run/fhir-clean > results/profile-fhir-clean.json

Unit: Claim (or EOB) resource unless a row says otherwise. Scope: every transaction bundle in the
folder. Read-only. Prints fill rates, code systems and value distributions; no patient values.
"""
import collections
import json
import re
import sys
from pathlib import Path


def systems(cc):
    return [c.get("system", "(none)") for c in (cc or {}).get("coding", [])] or ["(no coding)"]


def short(sys_):
    return {"http://snomed.info/sct": "SNOMED", "http://www.ama-assn.org/go/cpt": "CPT",
            "http://hl7.org/fhir/sid/icd-10-cm": "ICD-10-CM", "http://hl7.org/fhir/sid/icd-10": "ICD-10",
            "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm", "http://loinc.org": "LOINC",
            "http://hl7.org/fhir/sid/cvx": "CVX", "urn:oid:2.16.840.1.113883.6.285": "HCPCS"}.get(sys_, sys_)


def luhn_npi_ok(npi):
    """NPI check digit (Luhn over '80840' + first 9 digits). Well-formed is not the same as issued."""
    if not re.fullmatch(r"\d{10}", npi or ""):
        return False
    digits = [int(d) for d in "80840" + npi[:9]]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == int(npi[9])


def main():
    src = Path(sys.argv[1])
    c = collections.Counter()
    dist = collections.defaultdict(collections.Counter)
    org_ids = collections.Counter()
    npis = set()
    for p in sorted(src.glob("*.json")):
        b = json.loads(p.read_text())
        by_url = {e.get("fullUrl"): e["resource"] for e in b.get("entry", [])}
        for e in b.get("entry", []):
            r = e["resource"]
            rt = r["resourceType"]
            if rt == "Organization":
                for i in r.get("identifier", []):
                    org_ids[i.get("system", "(none)")] += 1
            if rt == "Practitioner":
                for i in r.get("identifier", []):
                    if i.get("system") == "http://hl7.org/fhir/sid/us-npi":
                        npis.add(i["value"])
            if rt == "Claim":
                c["claims"] += 1
                dist["claim.type"][(r.get("type", {}).get("coding") or [{}])[0].get("code")] += 1
                prof = (r.get("type", {}).get("coding") or [{}])[0].get("code") == "professional"
                c["claims_professional"] += prof
                prov = r.get("provider", {}).get("reference", "")
                dist["claim.provider reference kind"][prov.split("?")[0] if "?" in prov else prov[:9]] += 1
                c["claim.provider has NPI in reference"] += "us-npi" in prov
                c["claim.facility present"] += "facility" in r
                c["claim.billablePeriod present"] += "billablePeriod" in r
                c["claim.total present"] += "total" in r
                ins = r.get("insurance", [])
                c["claim.insurance present"] += bool(ins)
                c["claim.insurance.coverage is a reference (not display only)"] += any(
                    "reference" in i.get("coverage", {}) for i in ins)
                dist["claim.payer display"][(ins[0].get("coverage", {}).get("display") if ins else None)] += 1
                dx = r.get("diagnosis", [])
                c["claim.diagnosis present"] += bool(dx)
                dist["claim.diagnosis count"][len(dx)] += 1
                for d in dx:
                    c["diagnosis entries"] += 1
                    if "diagnosisCodeableConcept" in d:
                        for s in systems(d["diagnosisCodeableConcept"]):
                            dist["diagnosis code system (unit: diagnosis entry)"][short(s)] += 1
                    elif "diagnosisReference" in d:
                        cond = by_url.get(d["diagnosisReference"].get("reference"))
                        if cond:
                            for s in systems(cond.get("code")):
                                dist["diagnosis code system via Condition (unit: diagnosis entry)"][short(s)] += 1
                        else:
                            dist["diagnosis code system via Condition (unit: diagnosis entry)"]["(unresolved)"] += 1
                for it in r.get("item", []):
                    c["claim items"] += 1
                    for s in systems(it.get("productOrService")):
                        dist["item.productOrService system (unit: item)"][short(s)] += 1
                    disp = (it.get("productOrService", {}).get("coding") or [{}])[0].get("display", "")
                    sem = re.search(r"\(([^()]*)\)\s*$", disp)
                    dist["item SNOMED semantic tag (unit: item)"][sem.group(1) if sem else "(none)"] += 1
                    c["items with net amount"] += "net" in it
                    c["items with modifier"] += "modifier" in it
                    c["items with quantity"] += "quantity" in it
                    c["items with locationCodeableConcept"] += "locationCodeableConcept" in it
                    c["items with servicedDate/Period"] += ("servicedDate" in it or "servicedPeriod" in it)
            if rt == "ExplanationOfBenefit":
                c["eobs"] += 1
                prov = r.get("provider", {}).get("reference", "")
                c["eob.provider is Practitioner by NPI"] += "Practitioner?identifier=http://hl7.org/fhir/sid/us-npi" in prov
                c["eob.payment present"] += "payment" in r
                c["eob.total present"] += "total" in r
                cov = next((x for x in r.get("contained", []) if x["resourceType"] == "Coverage"), None)
                c["eob contained Coverage"] += cov is not None
                if cov:
                    c["eob Coverage.subscriberId (member id)"] += "subscriberId" in cov
                    c["eob Coverage.identifier"] += "identifier" in cov
                    c["eob Coverage.payor is reference"] += any("reference" in x for x in cov.get("payor", []))
                for it in r.get("item", []):
                    c["eob items"] += 1
                    loc = it.get("locationCodeableConcept")
                    if loc:
                        dist["eob item place of service (unit: item)"][
                            (loc.get("coding") or [{}])[0].get("code", "?") + " " + (loc.get("coding") or [{}])[0].get("display", "")] += 1
                    for a in it.get("adjudication", []):
                        code = (a.get("category", {}).get("coding") or [{}])[0].get("code", "").rsplit("/", 1)[-1]
                        dist["eob adjudication category (unit: adjudication)"][code] += 1
    npi_ok = sum(luhn_npi_ok(n) for n in npis)
    out = {"scope": str(src), "counts": dict(c), "distributions": {k: dict(v.most_common(25)) for k, v in dist.items()},
           "organization identifier systems (unit: identifier)": dict(org_ids),
           "practitioner NPIs (unit: distinct NPI)": {"distinct": len(npis), "check digit valid": npi_ok,
                                                      "start with 9999": sum(n.startswith("9999") for n in npis)}}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
