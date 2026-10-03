# Test data without PHI: landscape notes

Research notes for a Nirmitee.io blog post answering a healthcare-integration Slack question:
"What are healthcare companies using to generate test data or test FHIR files with mocked up
data without any security issues?" One reply said "Synthea".

Research date: 3 October 2026. Every live number below (stars, citations, release dates) was
read on that date and will drift. Lines marked **Inference** are my reading, not something the
source states. Lines marked **Not verified** are claims I could not confirm against a primary
source.

How these notes were gathered: Synthea's GitHub wiki (cloned read-only), the `synthea.properties`
file on `master`, the GitHub API for releases and issues, the Synthea downloads page (rendered in a
headless browser because it is a JavaScript app), CMS's Beneficiary FHIR Data (BFD) wiki on
GitHub, OpenAlex/Semantic Scholar/Crossref for citation counts and abstracts, Cornell LII for the
regulation text, and vendor documentation pages. Several CMS and HHS pages (data.cms.gov,
bluebutton.cms.gov, hhs.gov, cms.gov PDFs) returned HTTP 403 to every automated fetch, so for
those I used CMS's own GitHub wiki or secondary sources and say so.

---

## 1. Synthea

### 1.1 What it is

- Synthea is an open-source "Synthetic Patient Population Simulator" that generates synthetic
  patients and their health records, from birth to death.
  Source: https://github.com/synthetichealth/synthea (README).
- Licence: Apache 2.0, copyright The MITRE Corporation. Requires Java JDK 17 or newer.
  Source: README above.
- It is model-driven, not trained on patient records. The FAQ: "No individual-level data was used
  in creating it, so there is no risk of any real individual's data being present."
  Source: https://github.com/synthetichealth/synthea/wiki/Frequently-Asked-Questions
- The same FAQ answers "Can Synthea produce anonymized data?" with "No. ... It cannot take an
  existing dataset and anonymize it." This matters for the blog: Synthea replaces production data,
  it does not clean it.
- Default population: Massachusetts, but it ships demographics for every US state and generates
  "one US state at a time". Source: FAQ above.
- Over 90 disease modules, starting from the "Two Top Tens" (top 10 reasons for primary care
  visits and top 10 causes of years of life lost). Source: FAQ above. A `./gradlew concepts`
  example in the FAQ shows "Scanned 76 modules and 90 submodules. Catalogued 1412 concepts". That
  count is an example in the wiki, not a current measurement.
- GitHub, read via API on 3 Oct 2026: 3,372 stars, 947 forks, 259 open issues and PRs, last push
  18 Aug 2026. Latest tagged release v4.0.0 (5 Mar 2026).
  Source: https://api.github.com/repos/synthetichealth/synthea and
  https://github.com/synthetichealth/synthea/releases

### 1.2 Exporters (output formats)

Stated by the wiki FAQ "Does Synthea have data in format ___?" and the `synthea.properties` file
(https://github.com/synthetichealth/synthea/blob/master/src/main/resources/synthea.properties):

| Format | Setting | Default on `master` | Notes |
|---|---|---|---|
| FHIR R4 | `exporter.fhir.export` | on | Uses US Core; `exporter.fhir.us_core_version = 6.1.0` in properties. v4.0.0 release notes add US Core 7. |
| FHIR STU3 | `exporter.fhir_stu3.export` | off | |
| FHIR DSTU2 | `exporter.fhir_dstu2.export` | off | |
| Bulk FHIR (ndjson) | `exporter.fhir.bulk_data` | off | "using bulk_data=true will ignore exporter.pretty_print". Added in v2.4.0 (Jan 2019). |
| C-CDA | `exporter.ccda.export` | off | |
| CSV | `exporter.csv.export` | off | Data dictionary on wiki. |
| CPCDS (payer consumer data set, feeds CARIN Blue Button) | `exporter.cpcds.export` | off | Three files: patients, coverage, claims. Added v2.6.0 (Sep 2020). |
| BFD RIF (CMS Medicare claims layout) | `exporter.bfd.export` | off | Added v3.1.0 (Sep 2022). |
| JSON (Synthea-internal) | `exporter.json.export` | off | Includes simulation detail not in other formats. |
| Plain text, clinical notes, symptoms CSV | `exporter.text.export`, `exporter.clinical_note.export`, `exporter.symptoms.*` | off | |
| CDW | `exporter.cdw.export` | off | |
| Custom exporters (JAR plug-ins) | `exporter.enable_custom_exporters` | on | See wiki "Custom Exporters". |
| OMOP | not built in | n/a | Wiki home lists "OMOP (via external ETL)". |

Other defaults that surprise people (from the same properties file):

- `exporter.years_of_history = 10`. Synthea simulates the whole life but exports only active
  conditions plus the last 10 years unless this is set to 0. The FAQ warns full history gives
  "extremely large files". Source: FAQ section "The entry is old and not 'active' so was
  filtered out".
- `exporter.fhir.transaction_bundle = true`. Patient bundles are FHIR transactions that refer to
  Practitioner, Organization and Location by **conditional (query) references** such as
  `Practitioner?identifier=http://hl7.org/fhir/sid/us-npi|999999647`. The server must already hold
  those resources, so the wiki says to upload `hospitalInformation*.json`, then
  `practitionerInformation*.json`, then each patient bundle.
  Source: https://github.com/synthetichealth/synthea/wiki/FHIR-Transaction-Bundles
- Supported FHIR R4 resources per the wiki: AllergyIntolerance, Bundle, CarePlan, Claim,
  Condition, Coverage, DiagnosticReport, Encounter, ExplanationOfBenefit, Goal, ImagingStudy,
  Immunization, MedicationRequest, MedicationAdministration, Observation, Organization, Patient,
  Practitioner, Procedure; with US Core on also CareTeam, Device, DocumentReference, Location,
  Medication, PractitionerRole, Provenance.
  Source: https://github.com/synthetichealth/synthea/wiki/HL7-FHIR
  - **Inference**: resources an interface or payer team often needs are absent from that list,
    for example ServiceRequest, MedicationDispense, Specimen, Appointment, QuestionnaireResponse,
    Communication. Open feature requests exist for several: MedicationDispense #906 (2021),
    ServiceRequest #966 (2021), Appointment #1007 (2022), Communication/PractitionerRole/Location
    #738 (2020). Source: https://github.com/synthetichealth/synthea/issues

### 1.3 Modules and the Generic Module Builder

- Disease models are JSON state machines in the "Generic Module Framework" (states, transitions,
  logic, submodules). Wiki pages: https://github.com/synthetichealth/synthea/wiki/Generic-Module-Framework
- The Module Builder is a browser tool to view and edit modules:
  https://synthetichealth.github.io/module-builder/ (linked from the FAQ).
- ONC's 2023 final report describes the builder as letting users "create full-featured modules
  without needing" to hand-write JSON, and to download a module as JSON.
  Source: ONC/ASPE "Synthetic Health Data Generation to Accelerate PCOR: Final Report",
  https://aspe.hhs.gov/sites/default/files/documents/b279de5c07fc8fddbc0007a6fab99937/Synthetic-Data-Final-Report.pdf
- Medication realism add-on: the Medication Diversification Tool (MDT) from CodeRx builds
  medication distributions from RxClass/RxNorm and MEPS. The wiki says medication generation in
  core Synthea "is manual and limited to a small selection of medications in individual modules".
  Source: https://github.com/synthetichealth/synthea/wiki/Medication-Diversification-Tool-(MDT)
- LLM-assisted module authoring is now a research topic: a 2025 JAMIA Open paper used Claude 3.5
  Sonnet, GPT-4o and Gemini 1.5 Pro to draft a hyperthyroidism module; requirement scores rose
  with iteration but "evaluation by human experts revealed various structural deficits in final
  models". Source: https://doi.org/10.1093/jamiaopen/ooaf123

### 1.4 Keep-module filtering (only patients you want)

- Run with `-k keep_module.json`. For each slot Synthea generates candidates with new seeds and
  keeps one whose keep module ends in a state named "Keep". After 1,000 failed attempts it gives up
  and the population is one patient short.
  Source: https://github.com/synthetichealth/synthea/wiki/Keep-Patients-Module
- The wiki warns: "It is very easy to build a 'keep module' that only keeps impossible patients",
  for example asking for diabetes in ages 1-100 when no patient under 18 gets diabetes in Synthea.
- Cheaper knobs for the same goal: `-a 18-55` age range, `-g` gender, a city/state argument.
  Source: FAQ and https://github.com/synthetichealth/synthea/wiki/Basic-Setup-and-Running

### 1.5 Flexporter (map Synthea output to other Implementation Guides)

- Wiki opens with "Here be dragons. This feature is a work in progress."
- Purpose: "add new fields, values, and resource types to Synthea-generated FHIR, without having to
  modify the Synthea engine". Intended users: IG authors, eCQM developers and testers.
- YAML mapping file with FHIRPath `applicability`, optional variables and inline ValueSets, and
  actions such as Apply Profiles (example adds QI-Core profiles), Set Values, create resources.
- Runs inside Synthea (`./run_synthea -fm mapping_file [-ig ig_folder]`) or standalone on existing
  bundles (`./run_flexporter -fm mapping_file -s source_fhir`).
  Source: https://github.com/synthetichealth/synthea/wiki/Flexporter
- Shipped in v3.3.0 (Sep 2024). Open issue #1651 (Mar 2026): "Flexporter should be supported for
  all FHIR R4 exporters". Sources: releases page; https://github.com/synthetichealth/synthea/issues/1651
- **Inference**: Flexporter is the route to Da Vinci or CARIN profiles on Synthea data, but it
  only reshapes what Synthea simulated. It cannot invent a prior-auth workflow Synthea does not
  model.

### 1.6 Fixed Records and split records (patient matching / EMPI testing)

- `exporter.split_records = true` writes one record per provider organization instead of one
  longitudinal record. Source: https://github.com/synthetichealth/synthea/wiki/Splitting-Records-and-Duplicate-Data
- Fixed Records (`-f file.json`) let you supply "entities" with "seeds" (ground truth over time)
  and "variants" (deliberate errors such as "William" vs "Bill", wrong birth month, misspelled
  city "RAHLEY"). Combined with split records this "simulate[s] the types of variation in
  demographic information typically found across information systems".
  Source: https://github.com/synthetichealth/synthea/wiki/Fixed-Records
- This is how the "Synthetic Denver" set was built (see 1.9). AWS used it in a Feb 2025 blog to
  demo AWS Entity Resolution: "Synthea ... was used to generate multiple split records for some
  individuals", about 6,300 records.
  Source: https://aws.amazon.com/blogs/industries/build-a-unified-patient-index-using-aws-entity-resolution/

### 1.7 synthea-international

- Folders in https://github.com/synthetichealth/synthea-international (listed via GitHub API on
  3 Oct 2026): at, be, bg, ca, cz, de, dk, ee, es, fi, fr, gb, hr, hu, ie, it, nl, no, nz, pl, pt,
  ro, se, si, sk. That is 22 European countries plus Canada (`ca`, with Alberta etc. census
  divisions in `demographics_ca.csv`) and New Zealand. One automated summary I used mislabelled
  `ca` as Catalonia; the file contents show it is Canada.
- README caveats, verbatim in substance:
  - "Finland demographics are copied to all European countries."
  - "phone numbers are in US format still."
  - "Names are based on USA common names except for Finland."
  - "Most regions of the countries provided in this repository are working but some are not";
    providers come from OpenStreetMap, so gaps follow mapping gaps. `status.txt` lists per-region
    readiness.
- **Inference**: for a non-US demo the data will look "foreign enough" but its population
  statistics are Finnish everywhere in Europe. Fine for interface tests, wrong for any analysis.
- The Synthea downloads page also offers a "Sample of Canadian FHIR Data: 124 MB".

### 1.8 Known limitations and recurring complaints

From Synthea's own documents:

- FAQ: "Statistical accuracy of Synthea data can vary significantly depending on the condition of
  interest, and Synthea data has limited diversity." Also: "Synthea creates complete longitudinal
  patient records, with no missing or incorrect information, whereas real-world patient data can
  have gaps or inconsistencies". The FAQ says not to use it for machine learning or data-driven
  discovery, or for rare and complex conditions.
  Source: https://github.com/synthetichealth/synthea/wiki/Frequently-Asked-Questions
- The original 2018 JAMIA paper reported its own early validation gaps: Synthea "incorrectly
  generated 20% of patients in the infant age group" and patients were "4000 times more likely to
  undergo a diabetes-related amputation than the national or state average".
  Source: https://academic.oup.com/jamia/article/25/3/230/4098271 (as summarised by the fetch
  tool; **Not verified** against the PDF text by me).
- MITRE's FHIR for Research course: "Synthea generates basic FHIR resources: it includes required
  fields but rarely populates optional fields." and module detail "varies across modules".
  Source: https://mitre.github.io/fhir-for-research/modules/synthea-overview

From independent validation:

- Chen et al., BMC Medical Informatics and Decision Making, 2019, computed four quality measures on
  1,193,439 Synthea Massachusetts patients. Colorectal cancer screening 63% vs 77.3% (MA) and 69.8%
  (US). COPD 30-day mortality 0.7% vs 7% (MA) and 8% (US). Hip/knee complications 0% vs 2.9%.
  Blood pressure controlled after hypertension diagnosis: no Synthea patients, vs 74.52% (MA).
  Conclusion: Synthea models demographics and "probabilities of services being offered" well but
  not "deviations in care" and their outcomes.
  Source: https://doi.org/10.1186/s12911-019-0793-0 (abstract read via OpenAlex).

From ONC's 2023 final report on its Synthea project (Recommendations section):

- Same seed does not always give identical output, "particularly when generating a large sample".
- Systolic and diastolic blood pressure are drawn independently from ranges, so "pressure
  differences may not correlate".
- "every clinician is designated as a general practitioner".
- No ICD-10 support at the time. **Note**: this is now partly stale. Synthea v3.4.0 (Nov 2025)
  added "Support for mapping condition codes to ICD-10-CM in the FHIR R4 exporter".
- A TEP member summary (31 Mar 2021): Synthea "cannot create a population of patients who reflect
  the complexity of the real world" but output "appeared to produce data sufficiently valid for the
  purposes of software development, testing, and demonstration."
  Source: ASPE PDF linked in 1.3.

From GitHub issues (read 3 Oct 2026; counts are comment counts at that time):

| Theme | Example issues | What they say |
|---|---|---|
| Reproducibility | #1236 (open, 22 comments, bug) | Same seed, same commit, different resource IDs on a later day. Maintainer: "a bug that we'll look at as a high priority"; array ordering "probably not something we can fix". Reporter found IDs changed after moving the system clock forward 2 days. |
| FHIR validation / references | #923 (open), #295 (closed, 15 comments), #1437 (open) | Validators flag `Organization?identifier=...` as malformed. Maintainer: these are valid conditional references in transactions; set `exporter.fhir.transaction_bundle = false` to get normal references, at the cost of duplicating Practitioner/Organization/Location in every bundle. |
| No HL7 v2 | #1011 (closed), #535 (open, 14 comments) | "Does Synthea support exporting data sets in HL7 v2.x formats?" Maintainer reply in full: "No." In #535 (Maryland HIE CRISP wanting ADT A01-A13/A31 for Mirth testing) a contributor explains there is "not enough information in the current output to create useful ADT messages because there is no Scheduling module". James Agnew described loading Synthea into Smile CDR and using its v2 transforms (commercial). |
| Clinical notes | #1303 (open), #703 (open), #769 (open) | "Clinical notes contain information before it happens"; "Notes exporter can create notes with misaligned information". Notes are rendered from a FreeMarker template (`ClinicalNoteExporter.java` loads `note.ftl`), so they are short and formulaic. |
| Duplicates / keys | #1552, #1545, #1648, #815 | Duplicate lab panels on the same date; duplicate IDs in CSV tables; duplicate primary keys in `claims_transactions.csv`; duplicate EOB identifiers. |
| Temporal realism | #556, #133, #236 | Encounter times "not random"; outpatient visits only on weekdays; medications prescribed before they existed. |
| Medication realism | #1052 (10 comments) | "Low similarity of medication between Synthea generation and our own database". |
| Missing resources | #906, #966, #1007, #738 | MedicationDispense, ServiceRequest, Appointment, Communication. |
| Build / environment | #1043 (68 comments), #841, #983 | Build failures, M1 Mac hang. |

**Inference**: the realism complaints and the "too clean" point cut both ways for testing. Clean,
complete, deterministic-ish data is good for happy-path API tests and bad for testing how an
interface handles the mess of real feeds. Teams that need dirty data must inject it themselves
(Fixed Records variants are the only built-in tool for that, and only for demographics).

Performance: I found no recurring performance complaint in issue titles beyond one closed
`OutOfMemoryError` (#889) and an open question on `ExpressionProcessor` performance (#610). I did
not benchmark it. **Not verified**: any generation-speed figure.

### 1.9 Ready-made datasets (no Java needed)

From the downloads page, rendered 3 Oct 2026 (https://synthea.mitre.org/downloads; the page says it
is moving to https://synthetichealth.github.io/downloads.html). The page states the data "is free
from cost, privacy, and security restrictions".

| Dataset | Size | Content |
|---|---|---|
| SyntheticMass v2 (24 May 2017) | 21 GB | 1 million patients per archive; FHIR 3.0.1 (STU3), CSV, C-CDA |
| SyntheticMass v1 (27 Feb 2017) | 28 GB | FHIR 1.8.0, CSV, C-CDA |
| 100 sample patients, latest Synthea | 7-36 MB each | C-CDA, CSV, FHIR R4 (36 MB), STU3, DSTU2 |
| 1K sample patients (2019-2021) | 9-83 MB | FHIR R4 (81 MB), STU3, DSTU2, C-CDA, CSV |
| COVID-19 10K | 54 MB | CSV |
| COVID-19 100K | 512 MB | CSV |
| Synthetic Denver (CODI) | 295 MB | FHIR; 6,357 child patients, records split "to test and identity matching system", "realistic name, address, contact info" |
| mCODE breast cancer | link out | FHIR + mCODE oncology profiles |
| Canadian sample | 124 MB | FHIR |
| Coherent Data Set | 9 GB | FHIR plus DICOM images, genomic data, ECG waveforms, simple notes, linked by FHIR |

- The Coherent Data Set paper (Electronics 2022) gives 1,346 FHIR bundles, 298 DICOM images and
  949 DNA files. Source: https://www.mdpi.com/2079-9292/11/8/1199 (figures via search snippet,
  **Not verified** in the full text).
- The Coherent set is also on the AWS Open Data Registry under CC BY 4.0, bucket
  `arn:aws:s3:::synthea-open-data/coherent/`.
  Source: https://github.com/awslabs/open-data-registry/blob/main/datasets/synthea-coherent-data.yaml
- The "100K" people remember is most likely the AWS-hosted OMOP version: "1,000 person (1k),
  100,000 person (100k), and 2,800,000 person (2.8m) data sets in the OMOP Common Data Model",
  managed by AWS, bucket `arn:aws:s3:::synthea-omop`.
  Source: https://github.com/awslabs/open-data-registry/blob/main/datasets/synthea-omop.yaml
- Google Cloud hosts a BigQuery public dataset of Synthea FHIR, reported as about 1M Patients
  (`fhir_synthea`). Source: https://github.com/google/fhir-dbt-analytics (search snippet; **Not
  verified** on the Google listing itself).
- COVID-19 model paper: Walonoski et al., Intelligence-Based Medicine, 2020,
  https://doi.org/10.1016/j.ibmed.2020.100007
- Note for this lab: the machine's disk is nearly full (4.4 GB free on 3 Oct 2026). Do not pull
  SyntheticMass (21-28 GB) or the Coherent set (9 GB) here.

---

## 2. Other synthetic and test data sources

### 2.1 CMS

**DE-SynPUF (2008-2010 Data Entrepreneurs' Synthetic Public Use File)**
- Released 11 Feb 2013 by CMS, built by NORC at the University of Chicago and IMPAQ. Based on a 5%
  sample of 2008 Medicare beneficiaries, about 2.33 million people, claims years 2008-2010.
  Source: https://www.norc.org/research/library/access-to-medicare-claims-data-increased-with-release-of-the-dat.html
- Purpose and limit, from the AWS registry entry that quotes CMS: built so that programs written on
  it "will function on CMS Limited Data Sets", but it "has very limited inferential research value
  to draw conclusions about Medicare beneficiaries due to the synthetic processes used".
  Available in OMOP as 1k, 100k and 2.3m person sets (`arn:aws:s3:::synpuf-omop`).
  Source: https://github.com/awslabs/open-data-registry/blob/main/datasets/cmsdesynpuf-omop.yaml
- CMS's user guide (https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/SynPUF_DUG.pdf)
  returned 403 to me. Search snippets quote it as saying statistics from it "will be biased"
  because "interdependence and co-variation among variables has been altered". **Not verified**
  in the PDF.
- Method difference worth stating: DE-SynPUF was made by perturbing real claims (imputation,
  suppression, coarsening). Synthea is simulated from published statistics. Different privacy
  argument, see section 3.4.

**Synthetic Medicare Enrollment, FFS Claims and Part D (2023)**
- CMS collection: https://data.cms.gov/collection/synthetic-medicare-enrollment-fee-for-service-claims-and-prescription-drug-event
  (403 to me). Search snippets of the CMS/MITRE user guide (May 2023) say 8,671 synthetic
  beneficiaries aged 0-110, generated with Synthea, in CCW RIF layouts.
  User guide: https://data.cms.gov/sites/default/files/2023-05/d51e1218-68c3-4c7c-9598-0b81f22fe903/User%20Guide%20-%20CMS%20Synthetic%20RIF%20Files%20May%202023_AM508_v2.pdf
  **Not verified**: the 8,671 figure; I could not open the PDF.
- CMS's BFD wiki links that same PDF as a white paper "published by MITRE, the group that
  generates the synthetic data". Source: https://github.com/CMSgov/beneficiary-fhir-data/wiki/Synthetic-Data-Guide

**Blue Button 2.0, BCDA, DPC, AB2D sandboxes (shared synthetic beneficiaries)**
All from CMS's own BFD wiki, which I read in full:
https://github.com/CMSgov/beneficiary-fhir-data/wiki/Synthetic-Data-Guide and
https://github.com/CMSgov/beneficiary-fhir-data/wiki/Synthetic-Data-FAQ
- One synthetic population serves four CMS claims APIs: Blue Button 2.0, BCDA, DPC and AB2D, as
  FHIR Patient, Coverage and ExplanationOfBenefit.
- Synthetic records always have negative `Patient.id` and `ExplanationOfBenefit.id`; production
  IDs are positive. **Inference**: a cheap, copyable safety convention for anyone's test data.
- Release history: 2017 initial 30,000 beneficiaries with about 1,000,000 claims (Carrier,
  Inpatient, Part D); early 2021 outpatient claims; Oct 2021 10,000 "enhanced" beneficiaries
  (all eight EOB types); Spring 2022 10,000 more, nationwide, 143 more claim fields; 03/2023 and
  10/2023 "Rolling Claims" sets that receive new claims every Wednesday to mimic production
  arrivals; a 2025 post-acute care (PAC) set. The characteristics files live under
  `apps/bfd-model/bfd-model-rif-samples/dev/synthea_releases/`, so these releases come from
  Synthea's BFD exporter.
- Built-in edge cases: a "Golden Beneficiary" (-88888888888888) with most fields; an MBI
  collision pair that deliberately returns an OperationOutcome error; an MBI-history case.
- Honest limits stated by CMS: "Not all fields will be present", "Some of the fields that are
  present may not have realistic values". As of Aug 2021, maximum field coverage was 27% for
  Beneficiary, 79% Carrier, 83% Inpatient, 93% Part D. "Does the synthetic data contain at least
  one record with each possible code ...? No."
- Login pattern BBUser00000 / PW00000! and the 10,000 vs 40,000 account counts come from
  secondary sources and the Blue Button Google Group, since bluebutton.cms.gov returned 403.
  **Not verified** on the CMS page itself.

### 2.2 ONC test tools and Inferno

- Inferno's reference server (the public target used with the ONC (g)(10) test kit) ships patients
  85 and 355 and a Group `1a`. Source: https://github.com/inferno-framework/inferno-reference-server
- Those patients come from `uscore-data-script`, which "Creates a minimal set of complete,
  realistic synthetic patients for HL7 FHIR US Core v3.1.0 by generating a population of patients
  in Synthea and finding a small representive set that contain all required data elements". It
  then edits them: caps resources at 30 per type, forces a smoker, injects data-absent-reason on a
  condition category and a patient name, adds a standalone Medication. An `mrburns` option makes
  "one patient with everything".
  Source: https://github.com/inferno-framework/uscore-data-script
  **Inference**: this is the cleanest public example of the right pattern. Generate broadly with
  Synthea, select for coverage, then hand-inject the edge cases Synthea will not produce.
- Inferno test kits for the CMS-0057-F era exist and were active in Sep-Oct 2026: Da Vinci PAS,
  CRD, DTR, PDex, Plan-Net, US Drug Formulary, CARIN for Blue Button, Bulk Data, SMART App Launch.
  Source: https://github.com/orgs/inferno-framework/repositories (listed via API). PDex and CARIN
  kits simulate servers using the Inferno Reference Server.
- HL7 v2 certification testing uses NIST tools with ONC-supplied test data, for example the NIST
  Immunization Test Suite for 170.315(f)(1). Source: https://healthit.gov/test-method/transmission-immunization-registries/
  and https://hl7v2tools.nist.gov/immunization-edition2/
- ONC Patient Matching Algorithm Challenge (2017) published its test set: "1 million test patients
  ... split into eight files of alphabetical groupings". Source: https://github.com/onc-healthit/patient-matching

### 2.3 SMART Health IT sandbox

- The SMART sample data repository's R4 folder holds one subfolder, `SYNTHEA`, with 631 files
  (counted via GitHub API, 3 Oct 2026). Source: https://github.com/smart-on-fhir/generated-sample-data
  **Inference**: the R4 patients in the public SMART launcher are Synthea patients.
- That repo notes "As time passes the patients get older" and points to a `timeshift` tool to renew
  them. Same source.
- Synthea's wiki also lists SMART's Docker HAPI image preloaded with Synthea data and its Bulk
  Data Server. Source: https://github.com/synthetichealth/synthea/wiki/HL7-FHIR

### 2.4 EHR vendor sandboxes

- **Epic (open.epic)**: the test-patient page lists named patients including Camila Lopez, Derrick
  Lin, Desiree Powell, Olivia Roberts and others. It states the sandbox "should be populated only
  with sample or synthetic data", "You agree not to put individually identifiable information in
  any Epic-provided sandboxes", and Epic may wipe data at its discretion.
  Source: https://fhir.epic.com/Documentation?docId=testpatients. **Not verified**: the exact
  patient count (the fetch tool reported both 6 and 9).
- **Oracle Health (Cerner) Millennium**: open sandbox
  `https://fhir-open.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d/` needs no auth and is
  read-only ("No writes are available in sandbox without using authentication"); secure sandbox at
  `fhir-ehr-code.cerner.com` (provider) and `fhir-myrecord.cerner.com` (patient) supports writes.
  Source: https://docs.oracle.com/en/industries/health/millennium-platform-apis/mfrap/srv_root_url.html
- **athenahealth**: preview environment at `api.preview.platform.athenahealth.com`; shared sandbox
  practice ID 195900 is widely cited by SDKs. Sources are third-party (for example
  https://github.com/HealthTechDevelopers/athenahealth-sdk-dotnet); athena's docs returned 403.
  **Not verified** on athena's own docs.
- **Inference**: vendor sandboxes test the vendor's API behaviour and auth, with a handful of fixed
  patients. They do not give you volume, and in shared sandboxes other developers see what you
  write.

### 2.5 Public FHIR test servers (warning)

- HAPI public server home page: "This is not a production server! Do not store any information here
  that contains personal health information or any other confidential information. This server
  will be regularly purged and reloaded with fixed test data." Source: https://hapi.fhir.org/
- Synthea's own wiki uses `curl http://hapi.fhir.org/baseR4 --data-binary @patient.json` as the
  example. Source: https://github.com/synthetichealth/synthea/wiki/HL7-FHIR
  **Inference**: fine for Synthea output; never for anything derived from production, including
  "de-identified" extracts, because everything posted is world-readable.

### 2.6 MIMIC-IV demo (de-identified real data, not synthetic)

- MIMIC-IV Clinical Database Demo v2.2 (31 Jan 2023): 100 patients, Open Data Commons ODbL v1.0,
  no credentialing. Safe Harbor de-identification; "dates were shifted consistently using a random
  integer". Excludes free-text notes. Source: https://physionet.org/content/mimic-iv-demo/
- MIMIC-IV Clinical Database Demo on FHIR v2.1.0 (27 Aug 2025): same 100 patients plus ED demo,
  FHIR R4 ndjson, 22 profiles, resources prefixed "Mimic", ODbL.
  Source: https://physionet.org/content/mimic-iv-fhir-demo/
- Full MIMIC-IV needs PhysioNet credentialing and a data use agreement (stated on the demo page as
  the difference). **Inference**: the demo is the only free, real-patient-shaped FHIR set I found.
  It is ICU data from one hospital, so it fits analytics prototypes, not outpatient or payer flows.

### 2.7 Commercial generators and privacy vendors

| Vendor | What they say they do | Source | Status note |
|---|---|---|---|
| MDClone (ADAMS) | "synthetic derivatives" of a health system's own data with "virtually identical statistical properties" | https://www.mdclone.com/synthetic-data | Derived from real data |
| Syntegra | Synthetic EHR data platform (founded 2019) | https://pitchbook.com/profiles/company/437403-52 | PitchBook lists "Out of Business"; other listings still name it. **Not verified** |
| Gretel | Synthetic data APIs | https://techcrunch.com/2025/03/19/nvidia-reportedly-acquires-synthetic-data-startup-gretel | Acquired by NVIDIA, March 2025 (reported) |
| MOSTLY AI | Open-source Synthetic Data SDK, Apache 2.0, released 23 Jan 2025, TabularARGN, optional differential privacy | https://mostly.ai/blog/unlocking-ai-training-data-for-all-mostly-ai-releases-worlds-first-industry-grade-open-source-toolkit-for-synthetic-data | Trains on your real tables |
| Tonic.ai (Textual, Structural) | Redacts or synthesizes PHI in free text and PDFs; partners with Expert Determination providers | https://www.tonic.ai/products/textual | De-identification plus synthesis |
| Smile CDR | No synthetic generator found. Its founder described using Synthea + Smile CDR v2 transforms to make HL7 v2 feeds (issue #535 above) | https://github.com/synthetichealth/synthea/issues/535 | |

**Inference**: every vendor in this table except Synthea starts from real patient data. That puts
them in the privacy debate of section 3.4, which Synthea avoids by design.

### 2.8 HL7 v2 test messages

- Synthea does not export v2 (maintainer: "No.", #1011).
- Open-source generators found (I did not test any): HL7Forge (.NET 8; ADT A01-A40 and ORU^R01;
  seeded, deterministic) https://github.com/rich-howell/HL7Forge ; iris-HL7v2Gen for InterSystems
  IRIS (claims 184 message types) https://github.com/mwaseem75/iris-HL7v2Gen ; a seeded ADT/ORU/ORM
  generator with PHI ground truth proposed in OpenMed https://github.com/maziyarpanahi/openmed/issues/3884
- A 2015 study compared two methods for synthetic HL7 segments that mirror real HIE traffic:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4419874/ (title only read).
- **Inference**: the practical routes for Mirth/interface testing are (a) Synthea FHIR -> FHIR
  server -> FHIR-to-v2 mapping in the engine, or (b) a v2-native faker, plus (c) the sanitized
  real messages your partner's spec appendix already contains. Route (a) inherits the missing
  scheduling and ADT event history problem from #535.

### 2.9 X12 test data

- Stedi test mode: mock 270/271 eligibility "for payers like Aetna, Cigna, and UnitedHealthcare",
  test 837 claims returning test 277CA and test 835 ERAs, "without PHI/PII and without sending any
  data to payers", with fair-use limits. Source: https://www.stedi.com/docs/healthcare/test-mode
- X12 examples library lists 005010 examples for 270/271, 276/277, 277, 278, 820, 834, 835, 837
  (D/P/I). Source: https://x12.org/examples. Whether every example is free to view was not stated
  on the page. **Not verified**.
- Synthea's own claims output (CSV claims, CPCDS, BFD RIF) is claims data, not X12.
  **Inference**: no open Synthea-to-837 exporter turned up; teams map Synthea claims to X12 with
  their own code or use clearinghouse test modes.

### 2.10 LLM-generated synthetic notes

- Synthea notes are template text (FreeMarker `note.ftl`), and its own issues report timing errors
  in notes (#1303). v3.4.0 added labs and reports to the notes.
- Asclepius (ACL Findings 2024) trained a clinical LLM on synthetic notes generated from published
  case reports so the model could be shared publicly. Source: https://doi.org/10.18653/v1/2024.findings-acl.305
  (I read only the bibliographic record; **Not verified**: method details.)
- **Inference**: an LLM that writes notes from a Synthea record keeps the "no real patient"
  property only if the prompt contains no real data and the model is not fine-tuned on real notes.
  It adds a new risk: generated names, phone numbers or NPIs can collide with real people. Check
  any identifier-shaped value (for example NPIs against NPPES) before publishing.

---

## 3. The other path: de-identifying production data

### 3.1 The rule

45 CFR 164.514(b) gives two ways. Text read from https://www.law.cornell.edu/cfr/text/45/164.514

- **Expert Determination**, (b)(1): a qualified person determines "the risk is very small that the
  information could be used, alone or in combination with other reasonably available information,
  by an anticipated recipient to identify an individual", and "Documents the methods and results".
- **Safe Harbor**, (b)(2): remove 18 identifiers of the individual "or of relatives, employers, or
  household members", and have no "actual knowledge" the rest could identify someone. The 18:
  (A) names; (B) geography smaller than a state, except the first three ZIP digits when that
  three-digit area has more than 20,000 people (otherwise 000); (C) all date elements except year
  for dates directly related to the individual, and ages over 89 (aggregate as 90+); (D) phone;
  (E) fax; (F) email; (G) SSN; (H) medical record numbers; (I) health plan beneficiary numbers;
  (J) account numbers; (K) certificate/licence numbers; (L) vehicle identifiers and plates;
  (M) device identifiers and serial numbers; (N) URLs; (O) IP addresses; (P) biometric
  identifiers; (Q) full-face photos and comparable images; (R) any other unique identifying
  number, characteristic or code.
- (c) allows a re-identification code if it is not derived from patient information and the
  mechanism is not disclosed.
- **Inference, important for integration teams**: (C) removes admission, discharge and service
  dates. Interface and claims tests depend on those dates, so Safe Harbor output is often useless
  for timing logic unless dates are shifted, and shifting is not Safe Harbor; it needs Expert
  Determination.

HHS guidance (26 Nov 2012) explains both methods: no fixed expiry for an Expert Determination but
time limits are suggested; risk depends on replicability, availability and distinguishability of
features; "actual knowledge" means "clear and direct knowledge"; occupation can be an identifier.
Source: Ropes & Gray summary, 5 Dec 2012,
https://www.ropesgray.com/en/-/media/files/publications/2012/12/guidanceregardingmethodsfordeidentificationofprotectedhealthinformationinaccordancewiththehealthinsu.pdf
HHS original: https://www.hhs.gov/sites/default/files/ocr/privacy/hipaa/understanding/coveredentities/De-identification/hhs_deid_guidance.pdf
(403 to me; **Not verified** directly).

### 3.2 Why de-identified is not the same as synthetic

- Rocher, Hendrickx, de Montjoye, Nature Communications 2019: "99.98% of Americans would be
  correctly re-identified in any dataset using 15 demographic attributes".
  https://doi.org/10.1038/s41467-019-10933-3
- Na et al., JAMA Network Open 2018: from NHANES accelerometer data with PHI removed, a random
  forest re-identified 94.9% of adults and 87.4% of children (2003-2004 cohort).
  https://doi.org/10.1001/jamanetworkopen.2018.6040
- Sweeney, "Simple Demographics Often Identify People Uniquely" (Carnegie Mellon, 2000), the
  source of the often-quoted 87% figure for ZIP + sex + birth date.
  https://doi.org/10.1184/r1/6625769.v1 . **Not verified**: I did not read the full text; the 87%
  figure is from common citation, not from my reading.
- And synthetic data made from real data is not automatically safe either: Stadler, Oprisanu,
  Troncoso, "Synthetic Data: Anonymisation Groundhog Day" (arXiv 2020, USENIX Security 2022):
  "synthetic data either does not prevent inference attacks or does not retain data utility".
  https://doi.org/10.48550/arxiv.2011.07018
- **Inference, the core of the blog's answer**: there are three different things people call "test
  data". (1) Simulated from public statistics (Synthea): no individual's data, so no HIPAA question
  about the records themselves. (2) Generated by a model trained on your patients (MDClone, Gretel,
  MOSTLY AI): privacy depends on the model and needs evaluation, often an Expert Determination.
  (3) De-identified production data: still derived from real people, re-identification risk is
  measurable and non-zero, and the data stays subject to your agreements and controls. Only (1)
  answers the Slack question "without any security issues". (2) and (3) answer a different
  question: "I need realism Synthea cannot give me."

### 3.3 Tools

| Tool | What it is | Stated caveat | Source |
|---|---|---|---|
| Presidio | PII detection and anonymization for text, images, structured data; MIT licence; 11,139 stars (3 Oct 2026) | "there is no guarantee that Presidio will find all sensitive information" | https://github.com/data-privacy-stack/presidio |
| Philter (UCSF) | Command-line clinical note de-identification; BSD-3; default config evaluated on i2b2 | Built on what the authors call the largest annotated PHI note corpus | https://github.com/BCHSI/philter-ucsf ; paper https://doi.org/10.1038/s41746-020-0258-y |
| NLM Scrubber | Free clinical text de-identifier from NLM | "the success rate of this goal depends on the input data"; data manager must evaluate it; re-identification may still be possible | https://lhncbc.nlm.nih.gov/scrubber/ |
| AWS Comprehend Medical DetectPHI | API returning AGE, DATE, NAME, PHONE_OR_FAX, EMAIL, ID, URL, ADDRESS, PROFESSION with confidence scores | Entities "don't map 1:1 to the list specified by the Safe Harbor method"; recommends "additional human review" for compliance use | https://docs.aws.amazon.com/comprehend-medical/latest/dev/textanalysis-phi.html |
| Tonic Textual / Structural | Commercial redaction and synthesis; Expert Determination partners | | https://www.tonic.ai/products/textual |

Surprise for the blog: Presidio moved out of Microsoft. Its README says "Presidio has moved to a new
home!" and the transition note says it is "transitioning from a Microsoft-owned project to an
independent, community-governed open source project under the new GitHub organization Data Privacy
Stack", still MIT. `github.com/microsoft/presidio` now redirects there.
Source: https://github.com/data-privacy-stack/presidio/blob/main/docs/project_transition.md

**Inference**: all of these detect PHI in text. None of them certifies a dataset as de-identified.
A detector's recall is a measured property on someone's test corpus; it is not a guarantee on
yours. Structured FHIR/HL7 fields are easier (you know which field is a name) but free-text fields
inside them (notes, comments, OBX-5 text, NTE segments) need the text tools.

### 3.4 Tokenization and masking (brief)

Masking and tokenization replace identifiers with consistent surrogates so joins still work.
**Inference**: this is pseudonymization. Under HIPAA, consistent tokens are allowed under (c) only
if not derived from patient data and the key stays secret; tokens built by hashing an MRN or SSN
are "derived from" the individual. For test environments this is the weakest of the options in
this note, because the clinical content stays real. I did not survey tokenization vendors in depth.

---

## 4. Decision table: which source for which job

All rows are **Inference** built from the sources above.

| Use case | Best first choice | Add or switch to | Why |
|---|---|---|---|
| Unit and integration tests of a FHIR API | Synthea FHIR R4 with US Core on, small seeded runs committed as fixtures | Inferno `uscore-data-script` style selection and hand-made edge cases | Synthea gives valid, linked resources; it will not give you the malformed and partial data real clients send. |
| US Core / (g)(10) certification prep | Inferno reference server patients 85 and 355, Inferno test kits | Synthea for volume | That is what the test kit itself uses. |
| HL7 v2 interface engine testing (Mirth, Rhapsody, Iguana) | Partner spec sample messages and a v2 faker | Synthea -> FHIR -> v2 mapping if you need clinical consistency | Synthea has no v2 and no ADT event history (#1011, #535). |
| Claims / RCM X12 (270/271, 837, 835, 276/277) | Clearinghouse test mode (for example Stedi) and X12 examples | Synthea CSV claims as the source for your own 837 builder | No public Synthea-to-X12 path found. Payer behaviour cannot be simulated by a generator. |
| Payer CMS-0057-F Patient Access (CARIN BB, PDex) | CMS BB2.0/BFD synthetic beneficiaries; Synthea CPCDS/EOB output | Inferno CARIN and PDex test kits | CMS's own synthetic set includes golden and collision cases. |
| Payer CMS-0057-F Prior Auth (CRD/DTR/PAS) | Inferno Da Vinci CRD, DTR, PAS test kits plus hand-written scenarios | Synthea patients as the clinical background, reshaped with Flexporter | Synthea does not model orders, questionnaires or auth decisions. |
| Load and performance testing | Synthea at scale (bulk ndjson, CSV) or SyntheticMass | Clone and perturb to reach volume | Free volume. Watch the 10-year history default and file sizes; check disk first. |
| Analytics and ML training | De-identified real data under Expert Determination, or MIMIC (credentialed) | Synthea only for pipeline plumbing | Synthea's FAQ itself says not for ML; Chen 2019 shows outcome rates far off. |
| Demos and sales | Synthea Coherent set or curated Synthea patients | EHR vendor sandbox for live-EHR demos | No PHI, images and genomics included, shareable. |
| EHR vendor app certification (Epic, Oracle, athena) | That vendor's sandbox test patients | Synthea for local dev before you reach the sandbox | Vendor tests run against vendor data; their terms forbid real PHI there. |
| Patient matching / EMPI | Synthea Fixed Records + split records; Synthetic Denver; ONC 2017 challenge set | Your own error injection | Built-in ground truth of who is who. |
| Benchmarking de-identification tools | Text with known, labelled PHI: synthetic notes with planted identifiers, or i2b2-style annotated corpora under DUA | Synthea notes are too formulaic alone | You need ground truth labels; you cannot benchmark a de-id tool on data with no PHI in it. |

---

## 5. How widely Synthea is used (evidence)

Citation counts for Walonoski et al. 2018, JAMIA (https://doi.org/10.1093/jamia/ocx079), read
3 Oct 2026. The three indexes disagree because they cover different literature:

| Index | Count | Source |
|---|---|---|
| Semantic Scholar | 492 | https://api.semanticscholar.org/graph/v1/paper/DOI:10.1093/jamia/ocx079?fields=citationCount |
| OpenAlex | 462 (2021: 35, 2022: 56, 2023: 70, 2024: 85, 2025: 75, 2026 to date: 73) | https://api.openalex.org/works/doi:10.1093/jamia/ocx079 |
| Crossref | 362 | https://api.crossref.org/works/10.1093/jamia/ocx079 |
| Google Scholar | 536 per a search-engine snippet | **Not verified**, no date |

Chen et al. 2019 validation study: 111 citations in OpenAlex.

Government use, each with the source that shows it:

- CMS: Blue Button 2.0, BCDA, DPC and AB2D sandboxes share a synthetic population produced by
  MITRE, with release folders named `synthea_releases`. https://github.com/CMSgov/beneficiary-fhir-data/wiki/Synthetic-Data-Guide
- CMS: 2023 Synthetic Medicare claims PUF described in search snippets as Synthea-generated
  (**Not verified** in the PDF).
- Synthea has a dedicated BFD RIF exporter (v3.1.0, 2022) and a "utility to map from BFD RIF export
  format to CCW RIF format" (v3.2.0, 2023). Source: releases page.
- ONC: funded a 2019-2023 project to extend Synthea (section 6). Inferno's US Core data is built
  from Synthea (`uscore-data-script`).
- SMART Health IT: R4 sample data folder is Synthea only.
- AWS and Google host Synthea datasets (AWS Open Data Registry entries; BigQuery `fhir_synthea`).
- AWS Entity Resolution blog (Feb 2025) uses Synthea split records.
- ONC's challenge webinar (part of the same PCOR project) drew "110 participants representing 78
  organizations from six different countries" (ASPE final report). This measures one webinar, not
  Synthea's user base.
- **Not found**: any official download or user count for Synthea. The MITRE impact story
  (https://www.mitre.org/news-insights/impact-story/patient-data-synthea-missing-piece-health-it)
  returned 403; it may contain such figures.

---

## 6. History: how synthetic and test patient data came about

### 6.1 Before Synthea: rules and de-identified files

| Date | Event | Source |
|---|---|---|
| 28 Dec 2000 | HIPAA Privacy Rule final rule published, including the de-identification standard. | Federal Register 65 FR 82462. **Not verified** online today (federalregister.gov API returned non-JSON); date from general knowledge. |
| 14 Aug 2002 | Privacy Rule modifications final rule, which set the current text of 164.514. | 67 FR 53182. **Not verified** online today, same reason. |
| Mar 2010 | HHS OCR workshop on de-identification that fed the later guidance. | https://www.ropesgray.com/... (Ropes & Gray alert; also search snippet) |
| 26 Nov 2012 | HHS OCR publishes "Guidance Regarding Methods for De-identification of PHI", required by the HITECH Act. | Ropes & Gray alert, 5 Dec 2012 (link in 3.1) |
| 11 Feb 2013 | CMS releases DE-SynPUF (2008-2010 claims, about 2.33M beneficiaries; NORC and IMPAQ). | https://www.norc.org/research/library/access-to-medicare-claims-data-increased-with-release-of-the-dat.html |
| 2015 | Published comparison of two methods for synthetic HL7 segments mirroring HIE traffic. | https://pmc.ncbi.nlm.nih.gov/articles/PMC4419874/ |

### 6.2 Synthea

| Date | Event | Source |
|---|---|---|
| By 1 Jun 2016 | Earliest Synthea commits visible ("Now writes encounters, height, and weight to fhir record", 1 Jun 2016). The JAMIA paper says development began as part of PULSE@MassChallenge, supported by the MITRE Innovation Program. | GitHub commits API; https://academic.oup.com/jamia/article/25/3/230/4098271 |
| 17 Jun 2016 | `synthetichealth/synthea` repository created on GitHub. | GitHub API `created_at` |
| 8 Dec 2016 | v1.0.0, "the first major release": birth-to-death lifecycle, Massachusetts census defaults, Generic Modules plus Ruby rules, C-CDA. | https://github.com/synthetichealth/synthea/releases/tag/v1.0.0 |
| 27 Feb 2017 | SyntheticMass v1 (FHIR 1.8.0, CSV, C-CDA, 28 GB). | Downloads page |
| 24 May 2017 | SyntheticMass v2 (FHIR 3.0.1, 21 GB, 1M patients per archive). The wiki calls SyntheticMass "a 1/7th scale simulated model of the Commonwealth of Massachusetts". | Downloads page; https://github.com/synthetichealth/synthea/wiki/HL7-FHIR |
| 30 Aug 2017 (online), Mar 2018 (print) | JAMIA paper: Walonoski J, Kramer M, Nichols J, Quina A, Moesel C, Hall D, Duffett C, Dube K, Gallagher T, McLachlan S. "Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record." JAMIA 25(3):230-238. doi:10.1093/jamia/ocx079. Received 10 May 2017, accepted 5 Jul 2017. | https://academic.oup.com/jamia/article/25/3/230/4098271 |
| 2017 | CMS loads 30,000 synthetic beneficiaries and about 1,000,000 claims for Blue Button 2.0. (The wiki does not name the generator for the 2017 load.) | BFD Synthetic Data Guide |
| 6 Jul 2018 | v2.0.0, "first full release of the Java version": FHIR STU3 and DSTU2, C-CDA R2.1, CSV. | Release notes |
| 27 Sep 2018 | v2.2.0 adds FHIR R4 (v3.5.0 ballot). | Release notes |
| 22 Jan 2019 | v2.4.0 adds Practitioner export and FHIR ndjson (bulk). | Release notes |
| 2019 | ONC launches "Synthetic Health Data Generation to Accelerate PCOR" (Patient-Centered Outcomes Research Trust Fund project) to extend Synthea. Five new modules: Cerebral Palsy, opioid prescribing and OUD treatment, Sepsis, Spina Bifida, Acute Myeloid Leukemia. | https://aspe.hhs.gov/reports/synthetic-health-data-generation-accelerate-pcor ; final report PDF. **Not verified**: the funding line "PCORTF" is my reading of the project name and ASPE hosting; the page summary I read did not quote the fund. |
| 2019 | Chen et al. validation study of Synthea quality measures. | https://doi.org/10.1186/s12911-019-0793-0 |
| 3 Sep 2020 | v2.6.0: COVID-19 module, CPCDS exporter, US Core updates. | Release notes |
| Nov 2020 | COVID-19 model and data set paper (124,150 patients simulated per the paper summary). | https://doi.org/10.1016/j.ibmed.2020.100007 |
| Early 2021 | CMS adds outpatient claims to sandbox data. | BFD guide |
| Oct 2021 | CMS adds 10,000 "enhanced" synthetic beneficiaries for BB2.0, BCDA, DPC, AB2D. | BFD guide |
| 9 Dec 2021 | v3.0.0: Generic Module Framework version 2, claims in CSV, COVID vaccines. | Release notes |
| Spring 2022 | CMS adds 10,000 more, nationwide, 143 more fields, includes the ONC-funded modules (sepsis, spina bifida, cerebral palsy, opioids). | BFD guide |
| Apr 2022 | Coherent Data Set paper (Electronics 11(8):1199). | https://doi.org/10.3390/electronics11081199 |
| 8 Sep 2022 | v3.1.0: BFD RIF exporter. | Release notes |
| 2023 (ASPE page dated 4 Apr 2023) | ONC/ASPE final report on the PCOR synthetic data project. | ASPE links above |
| May 2023 | CMS/MITRE Synthetic Medicare claims PUF user guide. | data.cms.gov PDF link (403 to me) |
| Jun 2023 onward | CMS "Rolling Claims" synthetic sets with weekly new claims. | BFD guide |
| 6 Sep 2024 | v3.3.0: Flexporter, US Core 3.1.1 and 6.1.0. | Release notes |
| Feb 2025 | AWS Entity Resolution blog uses Synthea split records. | AWS blog link above |
| 2025 | JAMIA Open paper on LLM-assisted Synthea module development. | https://doi.org/10.1093/jamiaopen/ooaf123 |
| 5 Nov 2025 | v3.4.0: ICD-10-CM mapping in FHIR R4, labs in notes, US Core 6 default. | Release notes |
| 5 Mar 2026 | v4.0.0: US Core 7, JDK 17 minimum (JDK 25 supported). | Release notes |

### 6.3 What the history says (Inference)

- Healthcare test data went from "strip identifiers from real records" (HIPAA 2000/2002, guidance
  2012) to "perturb real records and publish" (DE-SynPUF 2013) to "simulate from public statistics"
  (Synthea 2016 onward). Each step was driven by the same problem the Slack poster has.
- Synthea became infrastructure through government use: CMS sandboxes, ONC funding and Inferno.
  That is why "Synthea" is the reflexive answer, and why it is a good answer for API testing and a
  weak answer for anything statistical.

---

## 7. Buyer-facing facts (for a CTO / VP Eng / head of implementation reader)

Only citeable statements. Priority order. "Secondary" means I read a reliable outlet's report of
the primary source, not the primary itself (IBM, HHS and data.cms.gov all blocked automated reads).

### 7.1 Cost of a healthcare breach (IBM / Ponemon)

1. **2026 report (latest)**: healthcare "an average cost of $6.64 million per incident"; global
   costs "have risen by 12% in a year to almost $5 million"; "the average cost of a data breach in
   the United States was $11.5 million". HIPAA Journal, 29 Jul 2026,
   https://www.hipaajournal.com/2026-cost-data-breach-study-ibm/ (secondary). IBM's own page
   confirms the 2026 global figure of 4.99M USD and the IBM/Ponemon authorship:
   https://www.ibm.com/reports/data-breach . Rank: several secondary sites say healthcare is the
   most expensive industry again, but they disagree on the streak ("13th year" vs the 2025 report's
   "14th"). Use "most expensive industry" only after checking IBM's PDF; do not quote a streak.
2. **2025 report**: healthcare $7.42M, global $4.44M (secondary: https://www.bluefin.com/bluefin-news/ibms-2025-data-breach-report-key-findings-and-the-years-biggest-attacks/ ).
3. Any IBM figure specific to breaches of test or development environments: **not found**.

### 7.2 HHS OCR breach portal (500+ individual breaches)

1. **2025**: about 710 large breaches; "at least 61,556,256 individuals"; "128 data breaches were
   reported by business associates"; by where the breach occurred, "35.8% at business
   associates". OCR portal data as of 13 Feb 2026, HIPAA Journal,
   https://www.hipaajournal.com/2025-healthcare-data-breach-report/ (secondary; portal
   https://ocrportal.hhs.gov/ocr/breach/ not queried). Note the two BA figures count different
   things (who reported vs where it happened).
2. **2024**: "725 data breaches of 500 or more records", the third year above 700; 115 reported by
   business associates; the Change Healthcare breach, a business associate, about 190 million
   records. As of 28 Jan 2025, https://www.hipaajournal.com/2024-healthcare-data-breach-report/
   (secondary). HHS's 2024 report to Congress
   (https://www.hhs.gov/sites/default/files/breach-report-to-congress-2024.pdf) was 403 to me.
3. OCR breach counts specific to test, QA or development environments: **not found**. The portal
   classifies by breach type and location (for example "Network Server"), not by environment.

### 7.3 What HIPAA says that applies to vendors and non-production copies

Text from Cornell LII, read 3 Oct 2026.
1. Minimum necessary, 45 CFR 164.502(b)(1): "a covered entity or business associate must make
   reasonable efforts to limit protected health information to the minimum necessary to
   accomplish the intended purpose of the use, disclosure, or request."
   https://www.law.cornell.edu/cfr/text/45/164.502
2. Business associate contracts, 45 CFR 164.504(e)(2): the contract must "Establish the permitted
   and required uses and disclosures" and the BA must "Not use or further disclose the information
   other than as permitted or required by the contract". https://www.law.cornell.edu/cfr/text/45/164.504
3. Risk analysis, 45 CFR 164.308(a)(1)(ii)(A), Required: "Conduct an accurate and thorough
   assessment of the potential risks and vulnerabilities to the confidentiality, integrity, and
   availability of electronic protected health information held by the covered entity or business
   associate." https://www.law.cornell.edu/cfr/text/45/164.308
4. De-identified data is outside the rule only if it meets 164.514(b) (section 3.1).
5. A HIPAA provision or HHS guidance that names test or development environments explicitly:
   **not found**. **Inference**: PHI copied to a dev or QA system is still ePHI the vendor
   "holds", so it falls inside the risk analysis and the BAA's permitted uses; a vendor that uses
   synthetic data in non-production has no ePHI there to analyse.

### 7.4 Integration as a buying barrier

1. Peterson Health Technology Institute, "2026 State of Digital Health Purchasing" (n=321: 106
   health plans, 115 employers, 100 health systems; KRC Research): "45% of purchasers cite
   difficulty integrating vendor data with their own internal medical claims or electronic
   utilization records as a top barrier." Reported 29 Sep 2026,
   https://hitconsultant.net/2026/09/29/phti-survey-majority-employers-health-plans-use-performance-based-contracting-digital-health/
   (secondary).
2. CHIME / Xealth survey of CHIME executives, 15 May-20 Jun 2023 (n not stated): "the vast
   majority (81%) have integrated digital health applications into their EHR workflow"; barriers
   "financial pressures" 47.6%, "staff resource constraints" 19.1%.
   https://www.xealth.com/blog/chime-survey-finds-majority-healthcare-organizations-adopt-digital-health/
   (vendor-sponsored).
3. KLAS "Digital Health Most Wired: National Trends 2025" exists
   (https://klasresearch.com/report/digital-health-most-wired-national-trends-2025/3946) but the
   integration figures are behind its paywall: **not found** as a quotable number.

### 7.5 Timelines

1. Credible survey data on EHR integration or interface go-live duration for third-party
   vendors: **not found**. Search results were vendor blogs quoting "4-6 months" for Epic and
   similar, with no method. Do not use them.
2. How long hospital IT takes to approve a new interface or hand over test data: **not found**.
3. Vendor security questionnaire turnaround (for example "at least seven days"): only vendor
   marketing pages; **not found** in a survey.

---

## For whoever builds this (paths, commands, open checks)

- Synthea config lives in `src/main/resources/synthea.properties`; key flags:
  `exporter.fhir.transaction_bundle`, `exporter.practitioner.fhir.export`,
  `exporter.hospital.fhir.export`, `exporter.years_of_history`, `exporter.fhir.us_core_version`,
  `exporter.fhir.bulk_data`, `exporter.split_records`, `exporter.cpcds.export`,
  `exporter.bfd.export`.
- CLI flags seen in the wiki: `-p` population, `-s` seed, `-a` age range, `-g` gender,
  `-k` keep module, `-f` fixed records, `-fm` Flexporter mapping, `-ig` IG folder.
- Load order for transaction bundles: hospitalInformation, practitionerInformation, then patients.
- CMS synthetic IDs are negative; consider the same convention for our fixtures.
- Open checks before publishing the blog:
  1. Open the CMS 2023 synthetic RIF user guide in a real browser and confirm 8,671 and Synthea.
  2. Confirm Blue Button BBUser account ranges on bluebutton.cms.gov.
  3. Confirm Epic test patient count.
  4. Confirm athena sandbox practice ID in athena docs.
  5. Confirm the JAMIA "20% infants" and "4000 times amputation" quotes in the paper PDF.
  6. Confirm HIPAA Federal Register dates (65 FR 82462; 67 FR 53182).
  7. Check Syntegra's status before naming it.
  8. Read IBM's 2026 report itself for the healthcare figure and rank (section 7 uses HIPAA
     Journal's reading of it).
