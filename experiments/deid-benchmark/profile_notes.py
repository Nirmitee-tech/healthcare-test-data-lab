"""Step 1: which identifier types occur in Synthea notes, and how often (unit = note).

Run: python3 experiments/deid-benchmark/profile_notes.py
Writes output/profile.json and output/sample_notes.txt (20 notes, synthetic, fixed sample).
"""
import json
import os
import random
import re
from collections import Counter

from groundtruth import HERE, TYPES, ground_truth_spans, load_notes

OUT = os.path.join(HERE, "output")

# Concept searches that do not depend on the structured record: any date-like, phone-like,
# long number, "Dr."/titles, street words, and capitalised words outside the section headers.
GENERIC = {
    "any_iso_date": r"\b\d{4}-\d{2}-\d{2}\b",
    "any_slash_date": r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    "any_month_name": r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b",
    "phone_like": r"\b\d{3}[-. ]\d{3}[-. ]\d{4}\b",
    "ssn_like": r"\b\d{3}-\d{2}-\d{4}\b",
    "digit_run_5plus": r"\b\d{5,}\b",
    "title_dr_mr_mrs": r"\b(Dr|Mr|Mrs|Ms)\.",
    "street_word": r"\b(Street|St\.|Avenue|Ave|Road|Rd|Lane|Drive|Suite|Apt|Highway|Boulevard)\b",
    "hospital_word": r"\b(Hospital|Clinic|Medical Center|Health Center|Urgent Care|Family Practice)\b",
    "email_like": r"\S+@\S+\.\w+",
    "url_like": r"https?://",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    notes, stats = load_notes()
    per_type_notes = Counter()
    per_type_spans = Counter()
    generic_notes = Counter()
    first_line_is_date = 0
    insurance = Counter()
    for n in notes:
        spans = ground_truth_spans(n)
        for t in set(s[0] for s in spans):
            per_type_notes[t] += 1
        for s in spans:
            per_type_spans[s[0]] += 1
        for k, rx in GENERIC.items():
            if re.search(rx, n["text"]):
                generic_notes[k] += 1
        if re.match(r"\s*\d{4}-\d{2}-\d{2}\s*\n", n["text"]):
            first_line_is_date += 1
        m = re.search(r"currently has (.+)\.", n["text"])
        if m:
            insurance[m.group(1)] += 1
    all_types = TYPES + ["age_89_or_under", "age_over_89"]
    result = {
        "scope": "out/run/fhir-clean, Synthea seed 42, DocumentReference notes; unit = note",
        "stats": stats,
        "notes": len(notes),
        "patients": len(set(n["patient"] for n in notes)),
        "notes_containing_type": {t: per_type_notes.get(t, 0) for t in all_types},
        "spans_of_type": {t: per_type_spans.get(t, 0) for t in all_types},
        "generic_pattern_notes": {k: generic_notes.get(k, 0) for k in GENERIC},
        "first_line_is_iso_date": first_line_is_date,
        "insurance_names_top": insurance.most_common(12),
    }
    json.dump(result, open(os.path.join(OUT, "profile.json"), "w"), indent=2)
    rnd = random.Random(42)
    with open(os.path.join(OUT, "sample_notes.txt"), "w") as fh:
        for n in rnd.sample(notes, 20):
            fh.write(f"===== note {n['id']} patient {n['patient']}\n")
            fh.write("ground truth: " + json.dumps([s[0] + ':' + s[3] for s in ground_truth_spans(n)]) + "\n")
            fh.write(n["text"] + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
