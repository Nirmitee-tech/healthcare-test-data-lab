"""Messify: inject the defects real feeds carry, and write down every one.

Synthea output is cleaner than any production feed. A pipeline tested only on clean data has
never seen a local lab code, a duplicate patient or a weight in pounds. This step injects such
defects at a chosen rate and writes a manifest (JSON lines) naming each change, so a test can
assert that the pipeline caught every defect it was given.

Defects in the "loadable" set are valid FHIR that a server will store. The "strict" set adds two
spec violations. Measured against hapiproject/hapi:latest with its default settings (3 Oct 2026):
the dangling reference is rejected, and the time without a zone is stored (HTTP 200). A receiver
that relies on the server to catch the second one will not.
"""
import argparse
import copy
import json
import random
import sys
import uuid
from pathlib import Path

from lab.fhirutil import read_bundles, write_bundle

LOCAL_LAB_SYSTEM = "http://lab.example.org/codes/local"


def _lab_observations(bundle):
    for e in bundle["entry"]:
        r = e["resource"]
        if r.get("resourceType") == "Observation" and any(
                c.get("code") == "laboratory" for cat in r.get("category", []) for c in cat.get("coding", [])):
            yield r


def _patient_entry(bundle):
    for e in bundle["entry"]:
        if e["resource"].get("resourceType") == "Patient":
            return e
    return None


def lab_local_code(bundle, rng, rate):
    """Replace the LOINC coding with a local lab code only, as many lab systems send."""
    out = []
    for r in _lab_observations(bundle):
        if rng.random() < rate:
            before = copy.deepcopy(r["code"])
            loinc = before["coding"][0]["code"]
            r["code"] = {"coding": [{"system": LOCAL_LAB_SYSTEM, "code": "L" + loinc.replace("-", ""),
                                     "display": before.get("text", "")}], "text": before.get("text", "")}
            out.append(("Observation", r["id"], "code", before, r["code"]))
    return out


def mrn_missing_system(bundle, rng, rate):
    """Drop the system from the MRN, so the identifier cannot be matched on its own."""
    e = _patient_entry(bundle)
    if not e or rng.random() >= rate:
        return []
    for ident in e["resource"].get("identifier", []):
        if any(c.get("code") == "MR" for c in ident.get("type", {}).get("coding", [])) and "system" in ident:
            before = ident.pop("system")
            return [("Patient", e["resource"]["id"], "identifier[MR].system", before, None)]
    return []


def _typo(name, rng):
    if len(name) < 3:
        return name + name[-1]
    i = rng.randrange(1, len(name) - 1)
    return name[:i] + name[i + 1] + name[i] + name[i + 2:]


def duplicate_patient(bundle, rng, rate):
    """Add a second Patient for the same person: name typo, new MRN, same birth date and address."""
    e = _patient_entry(bundle)
    if not e or rng.random() >= rate:
        return []
    dup = copy.deepcopy(e["resource"])
    new_id = str(uuid.UUID(int=rng.getrandbits(128)))
    dup["id"] = new_id
    official = dup["name"][0]
    official["family"] = _typo(official["family"], rng)
    for ident in dup.get("identifier", []):
        ident["value"] = new_id if ident.get("value") == e["resource"]["id"] else ident["value"]
    dup["identifier"] = [i for i in dup.get("identifier", [])
                         if not str(i.get("system", "")).endswith("us-ssn")]  # many feeds omit SSN
    bundle["entry"].append({"fullUrl": f"urn:uuid:{new_id}", "resource": dup,
                            "request": {"method": "POST", "url": "Patient"}})
    return [("Patient", new_id, "(new resource)", {"duplicate_of": e["resource"]["id"]},
             {"family": official["family"]})]


def weight_in_lbs(bundle, rng, rate):
    """Report body weight in pounds. Valid UCUM, but a consumer that assumes kg is now wrong."""
    out = []
    for e in bundle["entry"]:
        r = e["resource"]
        if r.get("resourceType") == "Observation" and r.get("code", {}).get("coding", [{}])[0].get("code") == "29463-7":
            vq = r.get("valueQuantity", {})
            if vq.get("code") == "kg" and rng.random() < rate:
                before = dict(vq)
                r["valueQuantity"] = {"value": round(vq["value"] * 2.20462, 1), "unit": "lb",
                                      "system": "http://unitsofmeasure.org", "code": "[lb_av]"}
                out.append(("Observation", r["id"], "valueQuantity", before, r["valueQuantity"]))
    return out


def birthdate_partial(bundle, rng, rate):
    """Send only year and month of birth. Valid FHIR, and it weakens patient matching."""
    e = _patient_entry(bundle)
    if not e or rng.random() >= rate:
        return []
    before = e["resource"]["birthDate"]
    e["resource"]["birthDate"] = before[:7]
    return [("Patient", e["resource"]["id"], "birthDate", before, before[:7])]


def name_case_whitespace(bundle, rng, rate):
    """Upper-case the family name and pad it, as older registration systems do."""
    e = _patient_entry(bundle)
    if not e or rng.random() >= rate:
        return []
    n = e["resource"]["name"][0]
    before = n["family"]
    n["family"] = before.upper() + "  "
    return [("Patient", e["resource"]["id"], "name[0].family", before, n["family"])]


def missing_encounter_ref(bundle, rng, rate):
    """Drop Observation.encounter, so the result cannot be tied to a visit."""
    out = []
    for e in bundle["entry"]:
        r = e["resource"]
        if r.get("resourceType") == "Observation" and "encounter" in r and rng.random() < rate:
            out.append(("Observation", r["id"], "encounter", r.pop("encounter"), None))
    return out


def dangling_reference(bundle, rng, rate):
    """Point an Observation at a Patient that does not exist. A server should reject the bundle."""
    for e in bundle["entry"]:
        r = e["resource"]
        if r.get("resourceType") == "Observation" and rng.random() < rate:
            before = r["subject"]
            r["subject"] = {"reference": "Patient/does-not-exist-" + r["id"][:8]}
            return [("Observation", r["id"], "subject", before, r["subject"])]
    return []


def datetime_no_tz(bundle, rng, rate):
    """Strip the time zone from effectiveDateTime. Invalid in FHIR R4 when a time is present."""
    for e in bundle["entry"]:
        r = e["resource"]
        v = r.get("effectiveDateTime", "")
        if r.get("resourceType") == "Observation" and "T" in v and rng.random() < rate:
            r["effectiveDateTime"] = v[:19]
            return [("Observation", r["id"], "effectiveDateTime", v, v[:19])]
    return []


LOADABLE = {
    "lab_local_code": lab_local_code,
    "mrn_missing_system": mrn_missing_system,
    "duplicate_patient": duplicate_patient,
    "weight_in_lbs": weight_in_lbs,
    "birthdate_partial": birthdate_partial,
    "name_case_whitespace": name_case_whitespace,
    "missing_encounter_ref": missing_encounter_ref,
}
STRICT = dict(LOADABLE, dangling_reference=dangling_reference, datetime_no_tz=datetime_no_tz)


def messify_bundle(bundle, defects, rate, rng, bundle_name=""):
    manifest = []
    if bundle.get("type") != "transaction" or not _patient_entry(bundle):
        return manifest  # hospital and practitioner bundles are left alone
    for name, fn in defects.items():
        for rtype, rid, path, before, after in fn(bundle, rng, rate):
            manifest.append({"defect": name, "bundle": bundle_name, "resourceType": rtype, "id": rid,
                             "path": path, "before": before, "after": after})
    return manifest


def messify_folder(src, dst, rate=0.1, seed=7, profile="loadable", only=None):
    defects = STRICT if profile == "strict" else LOADABLE
    if only:
        defects = {k: v for k, v in defects.items() if k in only}
    rng = random.Random(seed)
    manifest = []
    for path, bundle in read_bundles(src):
        manifest += messify_bundle(bundle, defects, rate, rng, path.name)
        write_bundle(Path(dst) / path.name, bundle)
    with open(Path(dst) / "defects.manifest.jsonl", "w") as f:
        for m in manifest:
            f.write(json.dumps(m) + "\n")
    counts = {}
    for m in manifest:
        counts[m["defect"]] = counts.get(m["defect"], 0) + 1
    return {"profile": profile, "rate": rate, "seed": seed, "defects_injected": counts}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--rate", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--profile", choices=["loadable", "strict"], default="loadable")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args(argv)
    print(json.dumps(messify_folder(args.src, args.dst, args.rate, args.seed, args.profile, args.only), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
