# Contributing

Issues and pull requests are welcome.

- Use synthetic data only. Never add real patient data, and check any 10-digit NPI you add against the
  NPPES registry (https://npiregistry.cms.hhs.gov/) before committing; it must not be registered.
- Every change ships with tests: a unit test in `tests/test_unit.py`, and an integration test in
  `tests/test_integration.py` when the change affects what a FHIR server or interface engine receives.
- Any number added to a README or RESULTS file must come from a script in this repository, with its scope,
  unit and date.
- Run `python3 -m unittest tests.test_unit` before opening a pull request.
