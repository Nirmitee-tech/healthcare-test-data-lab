# Synthea size and speed by setting (measured 3 Oct 2026)

Scope: 200 patients requested (228 records incl. deceased), Massachusetts, seed 42, Docker
eclipse-temurin:17-jre with 3 GB heap on an Apple Silicon Mac, hospital/practitioner files off.
Unit: bytes of FHIR output; seconds wall clock for one run. Rerun: `experiments/scale/run_scale.sh 200`.

| Setting | Seconds | FHIR output | Files |
|---|---|---|---|
| default (`exporter.years_of_history=10`) | 27 | 756 MB | 228 |
| `exporter.pretty_print=false` | 22 | 756 MB | 228 |
| `exporter.years_of_history=0` (full lifetime) | 57 | 2,058 MB | 228 |
| `exporter.years_of_history=2` | 19 | 206 MB | 228 |
| `exporter.fhir.bulk_data=true` (NDJSON per resource type) | 19 | 502 MB | 21 |

- The history window is the main size lever: full history is 2.7x the default, 2 years is 0.27x.
- Pretty printing made no measurable size difference in this build (single runs; timing noise not measured).
- Rough guide (estimate, not measured): about 3.3 MB per patient at default settings, so 10,000
  patients is roughly 33 GB of FHIR JSON. Plan disk before a load test.
