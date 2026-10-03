# Experiment B: can Synthea's Claim/ExplanationOfBenefit data drive X12 837P testing?

Date: 2026-10-03. Measured unless marked as inferred.

## Short answer

Not on its own. Synthea gives the claim skeleton for 837P testing: patients, dates, charges, a
payer name, a place of service and a practitioner NPI. It does not give the codes an 837P needs.
Every diagnosis in every export we checked is SNOMED CT, never ICD-10-CM. Every procedure is
SNOMED (or LOINC, RxNorm, CVX), never CPT or HCPCS. There is no member id and no payer id. Only
1,007 of 2,922 professional claims (34%) have any diagnosis, and an 837P needs at least one.

The one Synthea exporter built to map codes to billing code sets (BFD, the Blue Button RIF exporter)
needs mapping files that the public jar does not include. With `require_code_maps=true` it stops.
With `false` it writes beneficiary files, zero claims, and a list of 252 unmapped codes.

With a small hand-made SNOMED to ICD-10-CM and CPT crosswalk and placeholder ids, we produced a
5-claim 837P that passes pyx12 syntax validation. pyx12 also passed the same file with a SNOMED number
in the diagnosis slot. So syntax validation says nothing about whether the codes are real billing codes.

## Scope and versions

- Main profile: `out/run/fhir-clean`, 58 bundles (Synthea master-branch-latest, seed 42, 50
  patients, Massachusetts, reference date 2026-10-03). Unit: Claim resource unless stated.
- Exporter check: a new Synthea run, same jar, seed and date, `-p 10` (Synthea reported "Population:
  10, Records: total=34, alive=28, dead=6"), with the CSV, CPCDS and BFD exporters on
  (`run_synthea.sh`). The large outputs were deleted after profiling to save disk space. Rerun the
  script to regenerate them.
- pyx12 2.3.3 (005010X222A1 map shipped with it), Python 3.9.6.

## Results

### 1. Synthea FHIR Claim and EOB (`results/profile-fhir-clean.json`, `results/profile-professional.json`)

| Field an 837P needs | What Synthea has | Fill rate |
|---|---|---|
| Claim type | professional 2,922, pharmacy 1,232, institutional 225 | 4,379 Claims |
| Diagnosis (HI, at least 1 required) | `diagnosisReference` to a Condition | 1,007 of 2,922 professional Claims |
| Diagnosis code system | SNOMED CT | 1,706 of 1,706 diagnosis entries; 0 ICD-10 anywhere (grep over all bundles: 0 files mention icd-10 or the CPT system) |
| Procedure code (SV1) | SNOMED 14,019, LOINC 1,986, RxNorm 1,232, CVX 841 | 18,078 items; 0 CPT, 0 HCPCS |
| What the SNOMED items are | procedure 9,404; regime/therapy 1,283; physical object 1,192; finding 706; disorder 621; situation 358; others | Diagnoses and social findings also appear as claim lines (for example "Victim of intimate partner abuse (finding)") |
| Modifiers, units | none | 0 items with modifier, 0 with quantity |
| Line charge | `item.net` | 15,140 of 18,078 items |
| Billing provider NPI | Claim.provider is an Organization by Synthea id, no NPI | 0 of 4,379 Claims |
| Rendering NPI | EOB.provider is a Practitioner by NPI | 4,379 of 4,379 EOBs; 160 distinct NPIs, all 9999-prefixed with a valid check digit |
| Payer | display name only (Medicare, Medicaid, Dual Eligible, Humana, ...); `NO_INSURANCE` on 194 Claims | no payer id, no reference |
| Member id | EOB contained Coverage has no subscriberId or identifier | 0 of 4,379 |
| Place of service | EOB item location: 21 Inpatient Hospital 10,611; 19 Off Campus-Outpatient 6,274; 20 Urgent Care 1,193 | EOB items only; no 11 (Office) |
| Adjudication (835 side) | submitted, allowed, coinsurance, deductible, provider payment per line | 15,140 lines |

Inferred: place of service 21 on routine "Encounter for symptom" visits does not look like a real
office visit. Our 5 sample claims all carry POS 21. A tester should set POS by encounter class.

### 2. Synthea exporters (`results/profile-exporters.json`, `results/npi-check-csv.json`, `synthea-out/`)

| Exporter | Diagnosis codes | Procedure codes | Other |
|---|---|---|---|
| CSV `claims.csv` (2,998 rows) | DIAGNOSIS1 filled 2,998, all digits (SNOMED-shaped; ICD-10-CM starts with a letter) | | |
| CSV `claims_transactions.csv` (8,648 CHARGE rows) | | PROCEDURECODE all digits, 0 five-character codes; MODIFIER1 filled 0 | PLACEOFSERVICE is an organization UUID, not a POS code |
| CPCDS `CPCDS_Claims.csv` (7,514 lines) | Diagnosis code type SNOMED 4,482, empty 3,032 | Procedure code type SNOMED 5,358, empty 2,156 | Billing NPI 12 digits on all 7,514 lines (an NPI is 10); claim types inpatient-facility 6,181, outpatient-facility 1,033, pharmacy 251, professional-nonclinician 49 |
| BFD / RIF, `require_code_maps=true` | | | Stops: `MissingResourceException: Unable to read code map file: export/condition_code_map.json` |
| BFD / RIF, `require_code_maps=false` | | | 13 beneficiary files, 0 claims of any type (`export_summary.csv`), `missing_codes.csv` lists 252 unmapped codes |
| CSV organization NPIs | | | 114 distinct, 112 found in NPPES as real organizations (unit: distinct NPI). Practitioner NPIs: 0 of 114 found |

The jar references 13 code-map JSON files (`condition_code_map.json`, `hcpcs_code_map.json`,
`drg_code_map.json` and others) and contains none of them (checked with `unzip -l`).

Warning for anyone building 837s from the CSV export: the organization NPIs are real facilities.
Using them as billing NPIs in test claims would name real providers. FINDINGS.md item 1 found the same.

### 3. Minimal 837P (`gen_837p.py`, `out/sample-837p.x12`, `results/837p-claims.json`)

Five professional Claims from `fhir-clean`, chosen where the first diagnosis and first item are in
the crosswalk and the payer is not NO_INSURANCE.

What was mapped and how. These are candidate mappings I wrote for this test. No certified coder
reviewed them. They are not for real billing.

| SNOMED CT | Meaning | Mapped to | Used in sample |
|---|---|---|---|
| 444814009 | Viral sinusitis | ICD-10-CM J01.90 | 3 claims |
| 10509002 | Acute bronchitis | ICD-10-CM J20.9 | 2 claims |
| 195662009, 66383009, 73595000 | Acute viral pharyngitis, gingivitis, stress | J02.9, K05.10, Z73.3 | in the map, not picked |
| 185345009 | Encounter for symptom | CPT 99213 (visit level is a fixed guess; Synthea has nothing to derive it from) | 5 claims |
| 185347001 | Encounter for problem | CPT 99213 | not picked |

Filled with obviously synthetic values because Synthea has none: member id (`SYN` + hash), payer id,
billing provider name, address and tax id (`999999999`), submitter and receiver. Billing NPI is the
EOB practitioner NPI (9999-prefixed, unregistered per FINDINGS.md), an individual NPI used where
an organization would normally bill. Subscriber ZIP `00000` comes from Synthea (FINDINGS.md item 5).

### 4. pyx12 validation (`results/pyx12.txt`)

| File | pyx12 result | What it shows |
|---|---|---|
| `out/sample-837p.x12`, 5 claims | OK, 0 errors | syntax, loops, required segments and element lengths pass |
| `out/control-snomed-in-hi.x12` (HI = `ABK:444814009`, the raw Synthea code) | OK, 0 errors | pyx12 does not check that a diagnosis is a real ICD-10-CM code |
| `out/control-no-hi.x12` (HI removed, like the 1,915 professional Claims with no diagnosis) | FAILURE, 5 errors "Mandatory segment HI missing" | pyx12 does catch a missing diagnosis |

## What failed or is still open

- The `x12valid` command in pyx12 2.3.3 crashes on Python 3.9 when it writes its 999 file (str vs
  bytes). `validate_837.py` calls the library without writing a 999 file.
- Not done: code-set validation (ICD-10-CM and CPT existence, NCCI edits), payer-specific companion
  guide rules, any 835 generation from the EOB adjudication data, and Stedi or a clearinghouse
  test. The adjudication fields look usable for 835 testing (inferred, not tried).
- Open decision: where a real crosswalk would come from. SNOMED to ICD-10-CM has the NLM map
  (UMLS licence). There is no free SNOMED to CPT map; CPT itself is licensed by the AMA. This is the
  main blocker for using Synthea as an 837P source at scale.

## Rerun

```bash
cd experiments/x12-837
python3 profile_claims.py ../../out/run/fhir-clean > results/profile-fhir-clean.json
python3 profile_professional.py ../../out/run/fhir-clean > results/profile-professional.json
./run_synthea.sh true;  ./run_synthea.sh false         # about 10 s each, -p 10, container exp-synthea
python3 profile_exporters.py synthea-out/synthea-false > results/profile-exporters.json
(cd ../.. && python3 scripts/check_npis.py experiments/x12-837/synthea-out/synthea-false/csv 400)  # NPPES GETs
python3 gen_837p.py ../../out/run/fhir-clean out/sample-837p.x12 5 > results/837p-claims.json
/tmp/expvenv/bin/pip install pyx12 && /tmp/expvenv/bin/python validate_837.py out/*.x12
```

The two control files are made from the sample with `sed` (replace `HI*ABK:J0190` with
`HI*ABK:444814009`) and by deleting the HI lines and lowering SE01 by 5.
