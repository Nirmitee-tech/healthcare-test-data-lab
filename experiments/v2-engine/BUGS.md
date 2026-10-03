# Issues found in lab/to_hl7v2.py (2026-10-03)

Nothing in lab/ was changed by this experiment. Items 1 and 2 were fixed by the coordinator
during the run; evidence for before and after is in RESULTS.md table 4.

## 1. OBR-3 longer than v2.5.1 allows (fixed)

- What: OBR-3 (filler order number) carried the full DiagnosticReport id, 36 characters. HAPI 2.3's
  v2.5.1 OBR structure gives OBR-3 a maximum of 22.
- Evidence: `results/hapi-summary.json`, 1,008 of 1,008 ORU^R01 flagged. `results/obr3.txt`: truncating
  to 22 characters gives 999 distinct values for 1,008 reports (18 messages share a key), because
  Synthea ids share a per-patient prefix. The same reason the generator already hashes MSH-10.
- Why it matters: receivers that enforce or truncate lengths would merge different reports.
- After fix: 0 flagged, 1,008 distinct 22-character values, 0 collisions (`results/after-fix/`).

## 2. OBX-2 "CWE" longer than the v2.5.1 field length (fixed)

- What: coded results used value type `CWE` (3 characters); HAPI's v2.5.1 OBX-2 length is 2.
- Evidence: 150 ORU^R01 flagged in `results/hapi-summary.json`.
- Note: CWE is listed in v2.5.1 table 0125, so this is partly an inconsistency in the standard.
  HAPI's default validation and the engine both accepted it. The fix to `CE` avoids the question.

## 3. Documentation claim: "the same defects" in FHIR and v2 (open)

- README says the FHIR feed and the v2 feed carry the same people and the same defects. Measured
  (`results/coverage.txt`): duplicate_patient 0 of 2 reach v2 (only the first Patient is written),
  weight_in_lbs 0 of 68 (vital signs are not exported), missing_encounter_ref cannot be seen in v2
  (ORU has no PV1 or visit number), lab_local_code 929 of 994 (65 sit on Observations that no LAB
  DiagnosticReport references).
- Suggested: either state which defects reach v2, or emit them (a second ADT^A04 for the duplicate,
  a vitals ORU, PV1-19 in ORU so a missing visit link shows). Decision for the lab owner.

## 4. Docstring says messages are separated by a blank line (open, low)

- The files join messages with CRLF after the last segment, with no blank line (checked bytes in
  `Agnes294...hl7`: 6 CRLFs, 0 blank lines). OIE's File Reader with batch split on MSH handled it:
  1,064 of 1,064 messages (RESULTS.md table 2). A reader that splits on blank lines would get one
  message per file. Suggest fixing the docstring rather than the output.

## Not bugs (checked)

- Partial birth date as `YYYYMM` is a valid v2 TS; HAPI and hl7apy accept it. It is visible to the engine.
- Trailing spaces in PID-5.1 survive the engine's parse (strict and lenient), so the name defect is testable.
- OBX-3.3 `L` for local codes is accepted by every validator used; the codes are visible as intended.
