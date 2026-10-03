"""Step 2: how much of the known PHI in Synthea notes does a de-identification tool flag?

Run (from the repo root):
  experiments/deid-benchmark/.venv/bin/python experiments/deid-benchmark/run_benchmark.py

Systems compared on the same 3,147 notes:
  presidio_lg  Presidio AnalyzerEngine, default recognizers, spaCy en_core_web_lg
  presidio_sm  same, spaCy en_core_web_sm
  regex        dates, "N year-old" ages, phone, SSN, email; no names (shows what NLP adds)

Scoring:
  recall      a ground-truth span counts as found if any flagged span overlaps it, whatever the
              label. That is the redaction view: overlapping text would be masked. A partial
              overlap counts, so this is an upper bound on clean redaction.
  precision   flagged spans that overlap a PHI ground-truth span / all flagged spans. Flags on an
              age of 89 or under are reported apart: HIPAA Safe Harbor does not require removing
              them, so they are neither a hit on PHI nor plain noise.
  note clean  every PHI span in the note (ages 89 and under excluded) was overlapped.
Presidio is run with no score threshold (its default), and again at 0.5 for comparison.
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from importlib.metadata import version

from groundtruth import HERE, TYPES, ground_truth_spans, load_notes

OUT = os.path.join(HERE, "output")
PHI_TYPES = TYPES + ["age_over_89"]
REPORT_TYPES = ["given_name", "full_name", "encounter_date", "birth_date", "death_date",
                "age_over_89", "age_89_or_under"]

REGEX = {
    "DATE": r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    "AGE": r"\b\d{1,3}(?= year-old\b)|(?<=\bage )\d{1,3}\b",
    "PHONE": r"\b\d{3}[-. ]\d{3}[-. ]\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "EMAIL": r"\S+@\S+\.\w+",
}


def regex_detect(text):
    return [(lab, m.start(), m.end()) for lab, rx in REGEX.items() for m in re.finditer(rx, text)]


def presidio_detector(model):
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    nlp = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": model}]}).create_engine()
    engine = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])

    def detect(text):
        return [(r.entity_type, r.start, r.end, r.score) for r in engine.analyze(text=text, language="en")]
    return detect


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


def score(notes, gts, detections, min_score=None):
    found = Counter()
    total = Counter()
    found_by_label = defaultdict(Counter)
    flagged = tp = age_young = 0
    fp_labels = Counter()
    fp_texts = defaultdict(Counter)
    clean_notes = 0
    missed_examples = defaultdict(list)
    name_mentions_by_patient = defaultdict(lambda: [0, 0])  # patient -> [mentions, missed]
    missed_name_values = Counter()
    for n, gt, det in zip(notes, gts, detections):
        if min_score is not None:
            det = [d for d in det if d[3] >= min_score]
        text = n["text"]
        note_clean = True
        for t, s, e, val in gt:
            total[t] += 1
            hits = [d for d in det if overlaps((s, e), (d[1], d[2]))]
            if t in ("given_name", "full_name"):
                name_mentions_by_patient[n["patient"]][0] += 1
                if not hits:
                    name_mentions_by_patient[n["patient"]][1] += 1
                    missed_name_values[val] += 1
            if hits:
                found[t] += 1
                found_by_label[t][hits[0][0]] += 1
            else:
                if t != "age_89_or_under":
                    note_clean = False
                if len(missed_examples[t]) < 5:
                    line = text[text.rfind("\n", 0, s) + 1: text.find("\n", e)]
                    missed_examples[t].append(f"{val!r} in: {line.strip()[:120]}")
        clean_notes += note_clean
        for d in det:
            flagged += 1
            over = [g for g in gt if overlaps((g[1], g[2]), (d[1], d[2]))]
            if any(g[0] in PHI_TYPES for g in over):
                tp += 1
            elif over:
                age_young += 1
            else:
                fp_labels[d[0]] += 1
                fp_texts[d[0]][text[d[1]:d[2]]] += 1
    fp = flagged - tp - age_young
    return {
        "recall_by_type": {t: {"found": found[t], "total": total[t],
                               "recall": round(found[t] / total[t], 4) if total[t] else None,
                               "labels_used": dict(found_by_label[t].most_common(4))}
                           for t in REPORT_TYPES},
        "phi_spans_total": sum(total[t] for t in PHI_TYPES),
        "phi_spans_found": sum(found[t] for t in PHI_TYPES),
        "notes_fully_covered": clean_notes,
        "notes": len(notes),
        "flagged_spans": flagged,
        "flagged_on_phi": tp,
        "flagged_on_age_89_or_under": age_young,
        "false_positives": fp,
        "precision_phi_only": round(tp / flagged, 4) if flagged else None,
        "precision_counting_young_ages_as_ok": round((tp + age_young) / flagged, 4) if flagged else None,
        "false_positive_labels": dict(fp_labels.most_common()),
        "false_positive_top_texts": {lab: c.most_common(8) for lab, c in fp_texts.items()},
        "missed_examples": dict(missed_examples),
        "patients_with_name_mentions": len(name_mentions_by_patient),
        "patients_with_any_missed_name": sum(1 for v in name_mentions_by_patient.values() if v[1]),
        "patients_with_all_names_missed": sum(1 for v in name_mentions_by_patient.values() if v[1] == v[0]),
        "missed_name_values_top": missed_name_values.most_common(15),
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    notes, stats = load_notes()
    gts = [ground_truth_spans(n) for n in notes]
    results = {"scope": {"data": "out/run/fhir-clean (scrubbed), Synthea seed 42",
                         "unit": "note (DocumentReference copy; DiagnosticReport copy is identical)",
                         "load_stats": stats, "notes": len(notes),
                         "patients": len(set(n["patient"] for n in notes)),
                         "python": sys.version.split()[0]},
               "systems": {}}
    systems = [("regex", lambda: regex_detect, None)]
    if "--regex-only" not in sys.argv:
        for model in ("en_core_web_lg", "en_core_web_sm"):
            systems.append((f"presidio_{model[-2:]}", lambda m=model: presidio_detector(m),
                            {"presidio-analyzer": version("presidio-analyzer"), "spacy": version("spacy"),
                             model: version(model)}))
    for name, make, versions in systems:
        detect = make()
        t0 = time.time()
        if name == "regex":
            dets = [[(l, s, e, 1.0) for l, s, e in detect(n["text"])] for n in notes]
        else:
            dets = [detect(n["text"]) for n in notes]
        secs = round(time.time() - t0, 1)
        r = {"versions": versions, "seconds": secs, "threshold_none": score(notes, gts, dets)}
        if name != "regex":
            r["threshold_0.5"] = score(notes, gts, dets, min_score=0.5)
        results["systems"][name] = r
        print(name, secs, "s", file=sys.stderr)
    json.dump(results, open(os.path.join(OUT, "results.json"), "w"), indent=2)
    for name, r in results["systems"].items():
        for th in ("threshold_none", "threshold_0.5"):
            if th not in r:
                continue
            s = r[th]
            print(f"\n== {name} {th}  notes fully covered {s['notes_fully_covered']}/{s['notes']}  "
                  f"PHI spans found {s['phi_spans_found']}/{s['phi_spans_total']}  flagged {s['flagged_spans']}  "
                  f"FP {s['false_positives']}  precision {s['precision_phi_only']} "
                  f"(young ages ok: {s['precision_counting_young_ages_as_ok']})")
            for t, v in s["recall_by_type"].items():
                print(f"   {t:18} {v['found']:>5}/{v['total']:<5} {v['recall']}  {v['labels_used']}")
            print("   FP labels:", s["false_positive_labels"])
            print(f"   patients with name mentions {s['patients_with_name_mentions']}, any missed "
                  f"{s['patients_with_any_missed_name']}, all missed {s['patients_with_all_names_missed']}")


if __name__ == "__main__":
    main()
