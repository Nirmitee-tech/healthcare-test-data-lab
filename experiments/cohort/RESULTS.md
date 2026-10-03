# Targeted cohorts with keep modules (measured 3 Oct 2026)

`-k keep_diabetes.json` (shipped inside the Synthea jar under keep_modules/) keeps only patients
with active diabetes (SNOMED 44054006). Rerun: `experiments/cohort/run_cohort.sh 20 experiments/cohort/keep_diabetes.json`.

- 20 requested, 22 records kept, 49 s, history 2 years. 22 of 22 have SNOMED 44054006; 12 of 22
  also carry prediabetes (714628002) from earlier in life.
- Cost: about 2.2 s per kept patient versus about 0.1 s for unfiltered patients at the same
  history setting (19 s for 228 in experiments/scale). Synthea simulates and discards non-matching
  people, so rare conditions cost more.
- Other shipped keep modules: keep_diabetes_no_dr, keep_hospice, keep_medicare_beneficiaries.
