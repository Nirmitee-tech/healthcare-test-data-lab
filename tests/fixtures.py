"""A small hand-built Synthea-shaped transaction bundle for unit tests. Every value is fictional."""
import base64
import copy

PATIENT_ID = "aaaa0000-0000-0000-0000-000000000001"
ENC_ID = "aaaa0000-0000-0000-0000-0000000000e1"
REPORT_ID = "aaaa0000-0000-0000-0000-0000000000d1"
LAB_IDS = ["aaaa0000-0000-0000-0000-0000000000b1", "aaaa0000-0000-0000-0000-0000000000b2"]
WEIGHT_ID = "aaaa0000-0000-0000-0000-0000000000c1"
REAL_LOOKING_HOSPITAL = "Example General Hospital Inc"
REAL_LOOKING_PHONE = "617-555-0100"  # the scrubber treats any facility phone as real


def _entry(resource, method="POST"):
    return {"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource,
            "request": {"method": method, "url": resource["resourceType"]}}


def _lab(oid, loinc, text, value):
    return {
        "resourceType": "Observation", "id": oid, "status": "final",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                  "code": "laboratory"}]}],
        "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": text}], "text": text},
        "subject": {"reference": f"urn:uuid:{PATIENT_ID}"},
        "encounter": {"reference": f"urn:uuid:{ENC_ID}"},
        "effectiveDateTime": "2020-05-01T10:00:00-04:00",
        "valueQuantity": {"value": value, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
    }


def patient_bundle():
    note = "Jane123 Doe456 seen at Example General Hospital Inc. Call 617-555-0100."
    patient = {
        "resourceType": "Patient", "id": PATIENT_ID,
        "extension": [
            {"url": "http://synthetichealth.github.io/synthea/disability-adjusted-life-years", "valueDecimal": 0.1},
            {"url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-birthsex", "valueCode": "F"},
        ],
        "identifier": [
            {"system": "https://github.com/synthetichealth/synthea", "value": PATIENT_ID},
            {"type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]},
             "system": "http://hospital.smarthealthit.org", "value": PATIENT_ID},
            {"type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "SS"}]},
             "system": "http://hl7.org/fhir/sid/us-ssn", "value": "999-12-3456"},
        ],
        "name": [{"use": "official", "family": "Doe456", "given": ["Jane123"]}],
        "telecom": [{"system": "phone", "value": "555-123-4567"}],
        "gender": "female", "birthDate": "1980-02-03",
        "address": [{"line": ["1 Fake Lane"], "city": "Boston", "state": "MA", "postalCode": "02101", "country": "US"}],
    }
    enc = {"resourceType": "Encounter", "id": ENC_ID, "status": "finished",
           "class": {"code": "AMB"}, "subject": {"reference": f"urn:uuid:{PATIENT_ID}"},
           "serviceProvider": {"display": REAL_LOOKING_HOSPITAL},
           "participant": [{"individual": {"display": "Dr. Ann789 Smith012"}}],
           "period": {"start": "2020-05-01T09:00:00-04:00", "end": "2020-05-01T10:30:00-04:00"}}
    labs = [_lab(LAB_IDS[0], "2093-3", "Cholesterol", 180.5), _lab(LAB_IDS[1], "2571-8", "Triglyceride", 120.0)]
    weight = {"resourceType": "Observation", "id": WEIGHT_ID, "status": "final",
              "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7"}]},
              "subject": {"reference": f"urn:uuid:{PATIENT_ID}"},
              "encounter": {"reference": f"urn:uuid:{ENC_ID}"},
              "effectiveDateTime": "2020-05-01T10:00:00-04:00",
              "valueQuantity": {"value": 70.0, "unit": "kg", "system": "http://unitsofmeasure.org", "code": "kg"}}
    report = {"resourceType": "DiagnosticReport", "id": REPORT_ID, "status": "final",
              "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0074", "code": "LAB"}]}],
              "code": {"coding": [{"system": "http://loinc.org", "code": "57698-3", "display": "Lipid panel"}]},
              "subject": {"reference": f"urn:uuid:{PATIENT_ID}"},
              "effectiveDateTime": "2020-05-01T10:00:00-04:00",
              "result": [{"reference": f"urn:uuid:{i}"} for i in LAB_IDS]}
    docref = {"resourceType": "DocumentReference", "id": "aaaa0000-0000-0000-0000-0000000000f1",
              "status": "current", "subject": {"reference": f"urn:uuid:{PATIENT_ID}"},
              "content": [{"attachment": {"contentType": "text/plain; charset=utf-8",
                                          "data": base64.b64encode(note.encode()).decode()}}]}
    return {"resourceType": "Bundle", "type": "transaction",
            "entry": [_entry(r) for r in [patient, enc, *labs, weight, report, docref]]}


def hospital_bundle():
    org = {"resourceType": "Organization", "id": "bbbb0000-0000-0000-0000-000000000001",
           "extension": [{"url": "http://synthetichealth.github.io/synthea/utilization-encounters-extension",
                          "valueInteger": 3}],
           "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "1234567893"}],
           "name": REAL_LOOKING_HOSPITAL,
           "telecom": [{"system": "phone", "value": REAL_LOOKING_PHONE}],
           "address": [{"line": ["60 Hospital Rd"], "city": "BOSTON", "state": "MA"}]}
    # Synthea writes practitioners to their own bundle; one batch is enough for these tests.
    prac = {"resourceType": "Practitioner", "id": "bbbb0000-0000-0000-0000-000000000002",
            "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "9999868190"}],
            "name": [{"family": "Smith012", "given": ["Ann789"], "prefix": ["Dr."]}]}
    return {"resourceType": "Bundle", "type": "batch", "entry": [_entry(org, "PUT"), _entry(prac, "PUT")]}


def fresh():
    return copy.deepcopy(patient_bundle()), copy.deepcopy(hospital_bundle())
