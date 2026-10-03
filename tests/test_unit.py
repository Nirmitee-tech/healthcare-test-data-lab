import base64
import json
import random
import tempfile
import unittest
from pathlib import Path

from lab import fhirutil, messify, safety, scrub, to_hl7v2
from tests import fixtures


def _write(folder, name, bundle):
    fhirutil.write_bundle(Path(folder) / name, bundle)


class NpiTest(unittest.TestCase):
    def test_known_valid_npi(self):
        # CMS documentation example.
        self.assertTrue(fhirutil.npi_is_well_formed("1234567893"))
        self.assertFalse(fhirutil.npi_is_well_formed("1234567890"))
        self.assertFalse(fhirutil.npi_is_well_formed("12345"))

    def test_synthetic_npi_is_well_formed_and_never_issuable(self):
        for src in ["1013995133", "1588616742", "x"]:
            npi = scrub.synthetic_npi(src)
            self.assertTrue(fhirutil.npi_is_well_formed(npi), npi)
            self.assertEqual(npi[0], "9")
        self.assertEqual(scrub.synthetic_npi("1013995133"), scrub.synthetic_npi("1013995133"))


class SafetyTest(unittest.TestCase):
    def test_value_rules(self):
        self.assertTrue(safety._ssn_is_safe("999-12-3456"))
        self.assertTrue(safety._ssn_is_safe("666-12-3456"))
        self.assertFalse(safety._ssn_is_safe("123-45-6789"))
        self.assertTrue(safety._phone_is_safe("555-123-4567"))
        self.assertTrue(safety._phone_is_safe("(617) 555-0142"))
        self.assertFalse(safety._phone_is_safe("617-555-0200"))
        self.assertFalse(safety._phone_is_safe("978-342-9781"))
        self.assertTrue(safety._email_is_safe("a@example.com"))
        self.assertFalse(safety._email_is_safe("a@gmail.com"))
        self.assertFalse(safety._npi_is_safe("1234567893"))
        self.assertTrue(safety._npi_is_safe("9999868190"))

    def test_scan_flags_raw_and_passes_scrubbed(self):
        pb, hb = fixtures.fresh()
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as clean:
            _write(raw, "p.json", pb)
            _write(raw, "hospital.json", hb)
            result = safety.scan(raw)
            self.assertEqual(result["findings_by_rule"], {"npi-issuable": 1})
            self.assertEqual(safety.main([raw]), 1)
            scrub.scrub_folder(raw, clean)
            self.assertEqual(safety.scan(clean)["findings"], [])
            self.assertEqual(safety.main([clean]), 0)


class ScrubTest(unittest.TestCase):
    def setUp(self):
        pb, hb = fixtures.fresh()
        s = scrub.Scrubber()
        s.learn(pb)
        s.learn(hb)
        self.p = s.apply(pb)
        self.h = s.apply(hb)

    def _res(self, bundle, rtype):
        return [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == rtype]

    def test_person_names_lose_digits_everywhere(self):
        pat = self._res(self.p, "Patient")[0]
        self.assertEqual(pat["name"][0], {"use": "official", "family": "Doe", "given": ["Jane"]})
        enc = self._res(self.p, "Encounter")[0]
        # Tokens learned from the Practitioner resource are also fixed inside display strings.
        self.assertEqual(enc["participant"][0]["individual"]["display"], "Dr. Ann Smith")

    def test_unknown_letter_digit_tokens_untouched(self):
        # Only names learned from Patient/Practitioner change; codes such as L20859 or ICD10 stay.
        s = scrub.Scrubber()
        self.assertEqual(s._fix_string("L20859 ICD10 Jane123"), "L20859 ICD10 Jane123")

    def test_facility_replaced_consistently(self):
        org = self._res(self.h, "Organization")[0]
        enc = self._res(self.p, "Encounter")[0]
        self.assertNotEqual(org["name"], fixtures.REAL_LOOKING_HOSPITAL)
        self.assertEqual(enc["serviceProvider"]["display"], org["name"])
        self.assertEqual(org["identifier"][0]["value"][0], "9")
        self.assertRegex(org["telecom"][0]["value"], r"^555-555-01\d\d$")

    def test_note_text_is_fixed(self):
        doc = self._res(self.p, "DocumentReference")[0]
        note = base64.b64decode(doc["content"][0]["attachment"]["data"]).decode()
        self.assertIn("Jane Doe seen at", note)
        self.assertNotIn(fixtures.REAL_LOOKING_HOSPITAL, note)
        self.assertNotIn(fixtures.REAL_LOOKING_PHONE, note)

    def test_synthea_extensions_removed_others_kept(self):
        pat = self._res(self.p, "Patient")[0]
        self.assertEqual([x["url"] for x in pat["extension"]],
                         ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-birthsex"])
        self.assertNotIn("extension", self._res(self.h, "Organization")[0])


class MessifyTest(unittest.TestCase):
    def _run(self, only, rate=1.0, seed=1):
        pb, _ = fixtures.fresh()
        defects = {k: v for k, v in messify.STRICT.items() if k in only}
        manifest = messify.messify_bundle(pb, defects, rate, random.Random(seed), "p.json")
        return pb, manifest

    def _res(self, bundle, rid):
        return next(e["resource"] for e in bundle["entry"] if e["resource"]["id"] == rid)

    def test_rate_zero_changes_nothing(self):
        pb, manifest = self._run(list(messify.STRICT), rate=0.0)
        self.assertEqual(manifest, [])
        self.assertEqual(pb, fixtures.patient_bundle())

    def test_each_manifest_entry_matches_the_bundle(self):
        pb, manifest = self._run(list(messify.LOADABLE))
        self.assertEqual({m["defect"] for m in manifest}, set(messify.LOADABLE))
        for m in manifest:
            if m["defect"] == "lab_local_code":
                self.assertEqual(self._res(pb, m["id"])["code"]["coding"][0]["system"], messify.LOCAL_LAB_SYSTEM)
            if m["defect"] == "weight_in_lbs":
                self.assertEqual(self._res(pb, m["id"])["valueQuantity"]["code"], "[lb_av]")
                self.assertAlmostEqual(self._res(pb, m["id"])["valueQuantity"]["value"], 154.3, places=1)
            if m["defect"] == "missing_encounter_ref":
                self.assertNotIn("encounter", self._res(pb, m["id"]))

    def test_duplicate_patient_is_a_new_resource(self):
        pb, manifest = self._run(["duplicate_patient"])
        pats = [e["resource"] for e in pb["entry"] if e["resource"]["resourceType"] == "Patient"]
        self.assertEqual(len(pats), 2)
        self.assertNotEqual(pats[0]["id"], pats[1]["id"])
        self.assertEqual(pats[0]["birthDate"], pats[1]["birthDate"])
        self.assertNotEqual(pats[0]["name"][0]["family"], pats[1]["name"][0]["family"])
        self.assertEqual(manifest[0]["id"], pats[1]["id"])

    def test_same_seed_same_output(self):
        a, ma = self._run(list(messify.LOADABLE), rate=0.5, seed=3)
        b, mb = self._run(list(messify.LOADABLE), rate=0.5, seed=3)
        self.assertEqual(a, b)
        self.assertEqual(ma, mb)

    def test_non_patient_bundles_untouched(self):
        _, hb = fixtures.fresh()
        self.assertEqual(messify.messify_bundle(hb, messify.STRICT, 1.0, random.Random(1)), [])

    def test_folder_writes_manifest(self):
        pb, hb = fixtures.fresh()
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            _write(src, "p.json", pb)
            _write(src, "hospital.json", hb)
            summary = messify.messify_folder(src, dst, rate=1.0, seed=1)
            lines = (Path(dst) / "defects.manifest.jsonl").read_text().splitlines()
            self.assertEqual(sum(summary["defects_injected"].values()), len(lines))


class Hl7v2Test(unittest.TestCase):
    def test_escape_and_timestamps(self):
        self.assertEqual(to_hl7v2.esc("A|B^C&D~E\\F"), "A\\F\\B\\S\\C\\T\\D\\R\\E\\E\\F")
        self.assertEqual(to_hl7v2.v2_ts("1980-02-03"), "19800203")
        self.assertEqual(to_hl7v2.v2_ts("2020-05-01T10:00:00-04:00"), "20200501100000-0400")
        self.assertEqual(to_hl7v2.v2_ts("2020-05-01T10:00:00Z"), "20200501100000+0000")

    def _segments(self, msg):
        return [s.split("|") for s in msg.split("\r")]

    def test_messages_from_bundle(self):
        pb, _ = fixtures.fresh()
        msgs = to_hl7v2.bundle_to_messages(pb)
        self.assertEqual(len(msgs), 2)
        adt, oru = self._segments(msgs[0]), self._segments(msgs[1])
        self.assertEqual(adt[0][8], "ADT^A04^ADT_A01")
        pid = adt[2]
        self.assertEqual(pid[3], f"{fixtures.PATIENT_ID}^^^SYNTHEA^MR")
        self.assertEqual(pid[5], "Doe456^Jane123^")
        self.assertEqual(pid[7], "19800203")
        self.assertEqual(pid[8], "F")
        self.assertEqual(oru[0][8], "ORU^R01^ORU_R01")
        obx = [s for s in oru if s[0] == "OBX"]
        self.assertEqual([o[3] for o in obx], ["2093-3^Cholesterol^LN", "2571-8^Triglyceride^LN"])
        self.assertEqual(obx[0][5], "180.5")
        for m in msgs:
            self.assertLessEqual(len(self._segments(m)[0][9]), 20)

    def test_defects_carry_into_v2(self):
        pb, _ = fixtures.fresh()
        defects = {k: messify.LOADABLE[k] for k in ("lab_local_code", "mrn_missing_system", "birthdate_partial")}
        messify.messify_bundle(pb, defects, 1.0, random.Random(1))
        adt, oru = [self._segments(m) for m in to_hl7v2.bundle_to_messages(pb)]
        self.assertEqual(adt[2][3], f"{fixtures.PATIENT_ID}^^^^MR")
        self.assertEqual(adt[2][7], "198002")
        self.assertTrue(all(s[3].endswith("^L") for s in oru if s[0] == "OBX"))

    def test_obr3_fits_v251_length_and_stays_unique(self):
        a = to_hl7v2.filler_order_number("922fb35e-148d-9e82-761d-b2a2be8d6a4e")
        b = to_hl7v2.filler_order_number("922fb35e-148d-9e82-761d-b2a2be8d6a4f")
        self.assertLessEqual(len(a), 22)
        self.assertNotEqual(a, b)
        pb, _ = fixtures.fresh()
        oru = self._segments(to_hl7v2.bundle_to_messages(pb)[1])
        self.assertEqual(oru[2][3], to_hl7v2.filler_order_number(fixtures.REPORT_ID))

    def test_coded_result_uses_ce(self):
        obs = {"status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": "72166-2"}]},
               "valueCodeableConcept": {"coding": [{"system": "http://snomed.info/sct", "code": "266919005", "display": "Never smoker"}]}}
        self.assertEqual(to_hl7v2.obx_segment(1, obs).split("|")[2], "CE")

    def test_control_ids_unique_for_shared_prefix(self):
        a = to_hl7v2.control_id("ORU-", "922fb35e-148d-9e82-761d-b2a2be8d6a4e")
        b = to_hl7v2.control_id("ORU-", "922fb35e-148d-9e82-7aaa-b2a2be8d6a4e")
        self.assertNotEqual(a, b)
        self.assertLessEqual(len(a), 20)


if __name__ == "__main__":
    unittest.main()
