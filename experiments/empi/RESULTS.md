# Patient matching on synthetic duplicates (measured 3 Oct 2026)

Scope: 589 scrubbed Synthea patients (seed 7, Patient resources only) plus injected defects at
rate 0.2, seed 1: 126 duplicates (name typo, new MRN, no SSN), 102 partial birth dates, 118
upper-cased padded family names, 117 MRNs without a system. 715 records. Unit: patient pair.
Rerun: `PYTHONPATH=. python3 experiments/empi/run_empi.py 0.2 1` (writes results.json).

| Rule | Pairs found | True duplicates found (of 126) | Recall | Precision |
|---|---|---|---|---|
| exact family + given + birth date | 7 | 7 | 0.056 | 1.0 |
| same, after trim and lower-case | 10 | 10 | 0.079 | 1.0 |
| fuzzy family (>= 0.8), same given, birth date prefix, same address line | 117 | 117 | 0.929 | 1.0 |

Read with care:
- Every injected duplicate has a name typo by design, so exact rules are expected to fail here.
  The value is the harness: the manifest says which pairs are true, so any matcher can be scored.
- Precision of 1.0 says little. Synthea patients are generated independently, so there are no
  twins, Jr/Sr pairs or relatives sharing an address, the hard negatives that cause false merges
  in real registries. Testing precision needs those added deliberately (not done here).
