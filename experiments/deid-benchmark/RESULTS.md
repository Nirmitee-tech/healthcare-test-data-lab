# How much patient detail does an open-source de-identification tool find? (measured 3 Oct 2026)

**Result.** On 3,147 synthetic clinical notes where we know every patient detail in advance,
Microsoft Presidio with its recommended spaCy model flagged every date and every age, but missed
the patient's name in 1,576 of 3,147 notes. Only 1,571 notes (about half) came out with all of
their patient details flagged. One flagged span in three was a patient detail; the rest were mostly
insurer names, drug doses and race words. The smaller spaCy model did worse on both counts.

**What it means for a team choosing between the two paths.** De-identifying production notes with
an off-the-shelf tool needs its own measured recall on the team's own notes, plus human review, before
anything leaves the building. Synthetic data avoids that question for test environments, because
there is no real patient in it to leak. These are measurements on Synthea notes. How the tool does
on real notes is an expectation, discussed below, and was not measured here.

## Why Synthea notes work as a benchmark

Synthea generates fake patients and writes a short clinical note for each visit. The same file
also holds the patient's structured record: name, birth date, address, phone, record numbers, visit
dates and the clinic. So for every note we can list exactly which of that patient's details appear
in the text, without a person having to mark them up, and without any real patient involved.

We used the **scrubbed** copy of the data (this lab's `scrub` step), where Synthea's numeric name
suffixes are removed ("Dian810" becomes "Dian") and real facility names are replaced. Raw Synthea
names carry digits that no real note has, and a tool would find or miss them for the wrong reasons.

## What the notes actually contain (measured, unit = note)

We searched all 3,147 notes for every detail in the patient's record, and also searched for the
general shapes of patient details (any date format, phone-like or SSN-like numbers, street words,
"Dr.", hospital words, emails, web links), so that details written in an unexpected place would
still show up.

| Detail | Notes containing it (of 3,147) |
|---|---|
| Visit date (first line of every note) | 3,141, plus 5 where the visit date is the birth date and 1 where it is the death date |
| Patient name, two given names ("Agnes Laree") | 1,146 |
| Patient name, one given name ("Roxann") | 2,001 |
| Age 89 or under ("22 year-old", "quit smoking at age 16") | 3,071 notes, 3,936 mentions |
| Age over 89 (a HIPAA identifier) | 233 |
| Family name, maiden name | 0 |
| Street address, city, ZIP, phone, email | 0 |
| Record number, SSN, licence, passport | 0 |
| Facility name, clinician name | 0 |
| Any date format other than YYYY-MM-DD, any month name | 0 |

Every note names the patient exactly once, by given name only. Nothing else identifying is in the
text. So this benchmark tests three things: given names, dates and ages. It says nothing about
addresses, phone numbers, record numbers or clinician names, because Synthea never writes them into
notes. A real note set would test all of those as well.

Insurer names appear in most notes ("Patient currently has Humana"). An insurer name is not one of
the HIPAA identifiers (a member number would be), so we scored flags on them as false alarms.
A team that prefers to mask insurer names too would score them differently.

## Results (measured)

Three systems on the same 3,147 notes:

- **Presidio + large model**: Presidio 2.2.364, default recognizers, spaCy `en_core_web_lg` 3.8.0.
- **Presidio + small model**: same with `en_core_web_sm` 3.8.0.
- **Pattern rules only**: a handful of regular expressions for dates, ages, phones, SSNs and
  emails, and no name finding at all. It shows what the language model adds.

A detail counts as found if any flagged span overlaps it, whatever label the tool gave it, since an
overlapping span would be masked. Partial overlaps count, so these recall figures are an upper bound.

| Detail | Presidio + large | Presidio + small | Pattern rules |
|---|---|---|---|
| Name, two given names (1,146) | 1,146 (100%) | 492 (43%) | 0 |
| Name, one given name (2,001) | 425 (21%) | 633 (32%) | 0 |
| Visit date (3,141) | 3,141 | 3,141 | 3,141 |
| Birth date in note (5), death date in note (1) | 5, 1 | 5, 1 | 5, 1 |
| Age over 89 (233) | 233 | 233 | 233 |
| Age 89 or under (3,936; not required by HIPAA) | 3,936 | 3,936 | 3,936 |
| **Notes with every patient detail flagged** | **1,571 of 3,147** | **1,125 of 3,147** | **0** |
| Patients (of 56) with at least one missed name | 38 | 34 | 56 |
| Patients whose name was missed in every note | 35 | 34 | 56 |
| Flagged spans | 14,868 | 17,006 | 7,316 |
| Of those, on a patient detail | 4,951 | 4,505 | 3,380 |
| Of those, on an age 89 or under | 3,936 | 3,936 | 3,936 |
| False alarms (on nothing identifying) | 5,974 | 8,562 | 0 |
| Precision (share of flags on a patient detail) | 0.33 | 0.27 | 0.46 |
| Precision if flags on young ages count as fine | 0.60 | 0.50 | 1.00 |
| Run time, 3,147 notes, laptop CPU | 123 s | 121 s | 0.2 s |

Raising Presidio's score threshold to 0.5 removed only the false "driver licence" flags (151) and
changed no recall figure.

The name misses follow the name, not the sentence. Every one-name note opens the same way
("Roxann is a 22 year-old ..."), and the large model flags some names in that slot and never flags
others. Names it missed in every note include Tennille (109 notes), Carita (101), Rosalba (101),
Wayne (100), Virgie (88), Lavette (87) and Jody (81). When it did flag a one-name mention, 63 times
it called the name a place and 26 times an organisation, which would still mask it. The small model
missed "Corie Sofia" in all 591 of her notes, and "Agnes Laree" in 63.

### False alarms, with examples (all synthetic)

Presidio + large model, 5,974 false alarms:

- **Insurer names as organisations or places, 3,644 + part of 358**: "Dual Eligible" 858, "Medicaid"
  731, "Medicare" 435, "Humana" 327, "Anthem" 202 (as a place).
- **Drug quantities and test names as dates, 1,251**: "28 day" 604, "2000" 190, "0.15/30 28 day"
  149, "dast-10" 91.
- **Race and ethnicity words as a group label, 383**: "asian" 163, "hispanic" 116.
- **Drug strengths as driver licence numbers, 151**: "000813" 60, "000729" 44 (gone at threshold 0.5).
- **Text fragments as web links, 109**: "reported.ph" 86.
- **Clinical terms as people or places**: "lnp-s" 62 as a person, "covid-19" 72 and "mrna" 62 as places.

The small model adds clinical words labelled as people and places: the header text
"Social History / Patient" as a person 2,254 times, "simvastatin" 148 as a person, "acetaminophen"
496 as a place, "naproxen" 224 as an organisation.

## What to take from this

**Measured.** On these notes, the general-purpose tool finds structured details (dates, ages)
reliably and finds names unreliably. Names are the one thing every note contains, and the large
model missed the name in 1,576 notes, concentrated in 35 patients whose names it never recognised.
For those patients, every one of their notes would leave a de-identification pass with the name in
it. The pattern rules match the tool on dates and ages here only because Synthea writes a single
date format.

**Expected, not measured.** Real notes are longer and messier than Synthea's templates. We expect
that to cut both ways: more context around a name ("Mrs. Ortiz called back", "seen by Dr. Patel")
may help a language model, while misspellings, initials, nicknames, family members' names,
addresses, phone numbers, record numbers and dates written as "12/18" or "last Tuesday" give it
far more to miss, and none of those were tested here because Synthea never writes them. Published
studies on real notes would be the place to check this; we did not run one. The false alarm rate
on real notes could also be higher, since real notes mention more drugs, devices and places.

**For a company choosing a path.** If the goal is test data for building and testing integrations,
synthetic data removes the question this benchmark asks, because nothing in it belongs to a real
person. If the team does need real notes (for example to train or evaluate a model on real
language), an off-the-shelf tool is a starting point that needs measuring on the team's own notes:
recall per detail type, a list of the names it never catches, and human review of a sample before
release. A clean run of the tool shows that the tool flagged nothing more, which is weaker than
showing that no patient detail remains.

## What was not checked

- A transformer or clinical de-identification model (for example a Presidio set-up with a
  Hugging Face model). It was planned and dropped because the machine had about 2 to 6 GB of free
  disk during the run, and a PyTorch install plus model would not fit safely.
- Other de-identification tools (Philter, the NLM Scrubber, commercial services).
- Masking quality: we measured whether a span was flagged, not whether the masked output reads well
  or keeps clinical meaning.
- Real notes, other Synthea modules or seeds, larger populations.
- Whether results are stable across Presidio releases. Two runs on 3 Oct 2026 with the same versions
  gave identical flagged-span totals (14,868 and 17,006), so the run is repeatable on this setup.

## Decisions still needed

- Whether the blog states insurer names as false alarms (HIPAA reading, used here) or as fair masking.
  The author of the blog post decides.
- Whether to spend disk and time on the transformer comparison before publishing. Jitendra decides;
  it needs roughly 3 GB free and is expected to take under an hour.

---

## For whoever builds this

Skip unless you are rerunning or changing the experiment.

**Scope.** `out/run/fhir-clean/` (scrubbed output of `lab.pipeline --patients 50 --seed 42`),
56 patient bundles, Massachusetts, Synthea master-branch-latest jar of 3 Oct 2026. Unit = note.
Synthea writes each note twice, in `DocumentReference.content[].attachment.data` and
`DiagnosticReport.presentedForm[].data`; all 3,147 DiagnosticReport copies are byte-identical to a
DocumentReference copy, so only the DocumentReference copy is scored. (FINDINGS.md item 4 counts
6,294 because it counts both copies.)

**Environment.** Python 3.11.15 venv in `.venv/` (created with uv; system Python 3.9 runs the
stdlib-only scripts), presidio-analyzer 2.2.364, spaCy 3.8.16, en_core_web_lg 3.8.0,
en_core_web_sm 3.8.0. No Docker.

**Files.**
- `groundtruth.py`: loads notes, builds per-note ground truth by whole-token, case-sensitive string
  match of the patient's structured values (names, birth/death/encounter dates in seven written
  forms, address, city, ZIP, telecom, identifiers, facility and practitioner names from the bundle
  and Synthea's shared info files) plus ages from `N year-old` and `age N`. Nested spans are reduced
  to the longest one, so "Agnes" inside "Agnes Laree" counts once. When the visit date equals the
  birth or death date, the span is counted once under birth or death date.
- `profile_notes.py`: step 1 counts, writes `output/profile.json` and `output/sample_notes.txt`
  (20 notes, `random.Random(42)`).
- `run_benchmark.py`: step 2, writes `output/results.json` (per system: recall by type with labels
  used, missed examples, false alarm labels and top texts, per-patient name misses, at no threshold
  and at 0.5). Console output saved in `output/run_log.txt`.
- `test_groundtruth.py`: 4 unit tests of the ground-truth rules and 1 data test that fails if the
  note count, the duplication or the one-name-per-note property changes.

**Scoring detail.** Found = any detected span overlapping the ground-truth span (any entity label).
Precision = detected spans overlapping a PHI ground-truth span / all detected spans; PHI types are all
structured types plus `age_over_89`. Spans overlapping only `age_89_or_under` are counted apart.
Ground truth only contains what string matching against the structured record finds; the generic
pattern search in `profile_notes.py` (dates in other formats, phone, SSN, street and hospital words,
titles, emails, URLs) found nothing beyond it, apart from 108 notes with 5+ digit runs, which are
drug strengths such as `0.000625`.

**Rerun.**

```bash
cd healthcare-test-data-lab
uv venv --python 3.11 experiments/deid-benchmark/.venv
uv pip install --python experiments/deid-benchmark/.venv/bin/python presidio-analyzer==2.2.364 spacy==3.8.16
experiments/deid-benchmark/.venv/bin/python -m spacy download en_core_web_lg
experiments/deid-benchmark/.venv/bin/python -m spacy download en_core_web_sm
cd experiments/deid-benchmark
python3 -m unittest test_groundtruth                  # 5 tests, about 4 s
python3 profile_notes.py                              # step 1, about 20 s
.venv/bin/python run_benchmark.py                     # step 2, about 4 min on a laptop CPU
```
