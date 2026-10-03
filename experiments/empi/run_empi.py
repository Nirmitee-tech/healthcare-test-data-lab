"""Patient-matching benchmark on synthetic patients with injected duplicates.

Usage: python3 experiments/empi/run_empi.py [rate] [seed]
Input: experiments/empi/patients (scrubbed Patient-only Synthea bundles, 589 records, seed 7).
Ground truth: the messify manifest (duplicate_of pairs). Unit: candidate patient pair.
Three rules a team might write first are scored for recall and precision.
"""
import difflib
import itertools
import json
import random
import sys
import tempfile
from pathlib import Path

from lab import messify
from lab.fhirutil import read_bundles

HERE = Path(__file__).parent
rate = float(sys.argv[1]) if len(sys.argv) > 1 else 0.2
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1

defects = {k: messify.LOADABLE[k] for k in
           ("mrn_missing_system", "duplicate_patient", "birthdate_partial", "name_case_whitespace")}
patients, manifest = [], []
rng = random.Random(seed)
for path, b in read_bundles(HERE / "patients"):
    manifest += messify.messify_bundle(b, defects, rate, rng, path.name)
    patients += [e["resource"] for e in b["entry"]]

truth = {frozenset((m["id"], m["before"]["duplicate_of"])) for m in manifest if m["defect"] == "duplicate_patient"}


def rec(p):
    n = p["name"][0]
    a = (p.get("address") or [{}])[0]
    return {"id": p["id"], "family": n.get("family", ""), "given": (n.get("given") or [""])[0],
            "dob": p.get("birthDate", ""), "zip": a.get("postalCode", ""), "line": " ".join(a.get("line", [])),
            "gender": p.get("gender")}


R = [rec(p) for p in patients]
norm = lambda s: s.strip().lower()
sim = lambda a, b: difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def exact(a, b):
    # Exact family + given + full birth date, as written.
    return a["family"] == b["family"] and a["given"] == b["given"] and a["dob"] == b["dob"]


def normalized(a, b):
    # Same, after trimming and lower-casing names.
    return norm(a["family"]) == norm(b["family"]) and norm(a["given"]) == norm(b["given"]) and a["dob"] == b["dob"]


def fuzzy(a, b):
    # Birth year and gender must agree; birth date may be partial on one side; names fuzzy; address must agree.
    if a["dob"][:4] != b["dob"][:4] or a["gender"] != b["gender"]:
        return False
    if not (a["dob"].startswith(b["dob"]) or b["dob"].startswith(a["dob"])):
        return False
    return sim(a["family"], b["family"]) >= 0.8 and norm(a["given"]) == norm(b["given"]) and a["line"] == b["line"]


rules = {"exact": exact, "normalized": normalized, "fuzzy+address": fuzzy}
results = []
for name, fn in rules.items():
    found = {frozenset((a["id"], b["id"])) for a, b in itertools.combinations(R, 2) if fn(a, b)}
    tp = len(found & truth)
    results.append({"rule": name, "true_pairs": len(truth), "found": len(found), "true_positives": tp,
                    "recall": round(tp / len(truth), 3) if truth else None,
                    "precision": round(tp / len(found), 3) if found else None})

counts = {}
for m in manifest:
    counts[m["defect"]] = counts.get(m["defect"], 0) + 1
out = {"records_after_injection": len(R), "rate": rate, "seed": seed, "defects": counts, "results": results}
(HERE / "results.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
