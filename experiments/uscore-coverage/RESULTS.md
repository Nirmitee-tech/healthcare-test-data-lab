# US Core 6.1.0 profile coverage of Synthea output (measured 3 Oct 2026)

Scope: out/run/fhir-clean (seed 42, 56 records). Unit: resource claiming a profile in meta.profile.
Rerun: `python3 experiments/uscore-coverage/coverage.py out/run/fhir-clean .fhircache/packages/hl7.fhir.us.core#6.1.0`.
Full list in output.txt.

37 of 49 US Core resource profiles are populated. Never populated (12): Condition Problems and
Health Concerns, Coverage, Goal, MedicationDispense, Body Temperature, Occupation, Pregnancy
Intent, generic Vital Signs, QuestionnaireResponse, RelatedPerson, ServiceRequest, Specimen.

Why it matters: a payer Patient Access API (CMS-0057-F) needs Coverage; order workflows need
ServiceRequest; lab workflows need Specimen. Teams testing those must add the data themselves.
Claiming a profile is not conforming to it; see FINDINGS.md item 3 for the validator results.
A population of 56 may miss rare profiles that a larger run produces (not checked).
