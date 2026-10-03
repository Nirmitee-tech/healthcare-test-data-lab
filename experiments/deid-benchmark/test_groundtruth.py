"""Checks for the ground-truth builder. Run: cd experiments/deid-benchmark && python3 -m unittest test_groundtruth

Unit tests use hand-made notes. The data test reads out/run/fhir-clean and fails if the note set
or its duplication changes, which would make the numbers in RESULTS.md stale.
"""
import os
import unittest

from groundtruth import CLEAN, date_forms, find_spans, ground_truth_spans, load_notes


def note(text, **phi):
    base = {k: set() for k in ["given_name", "family_name", "maiden_name", "full_name", "birth_date",
                               "death_date", "encounter_date", "street_address", "city", "zip",
                               "phone_email", "record_ids", "facility", "practitioner"]}
    base.update({k: set(v) for k, v in phi.items()})
    return {"text": text, "phi": base}


class Unit(unittest.TestCase):
    def test_date_forms(self):
        f = date_forms("1986-12-18")
        self.assertIn("1986-12-18", f)
        self.assertIn("12/18/1986", f)
        self.assertIn("December 18, 1986", f)

    def test_find_spans_whole_token_only(self):
        self.assertEqual(find_spans("Ann and Annabel", "Ann"), [(0, 3)])
        self.assertEqual(find_spans("no match", "Ann"), [])

    def test_nested_name_kept_once(self):
        n = note("Agnes Laree is a 4 year-old female.", given_name={"Agnes", "Laree"},
                 full_name={"Agnes Laree"})
        types = [s[0] for s in ground_truth_spans(n)]
        self.assertEqual(types, ["full_name", "age_89_or_under"])

    def test_age_forms_and_threshold(self):
        n = note("Bo is a 92 year-old male. Patient quit smoking at age 16.", given_name={"Bo"})
        got = [(s[0], s[3]) for s in ground_truth_spans(n)]
        self.assertEqual(got, [("given_name", "Bo"), ("age_over_89", "92"), ("age_89_or_under", "16")])


@unittest.skipUnless(os.path.isdir(CLEAN), "needs out/run/fhir-clean")
class Data(unittest.TestCase):
    def test_note_set_matches_results(self):
        notes, stats = load_notes()
        self.assertEqual(stats["bundles"], 56)
        self.assertEqual(len(notes), 3147)
        self.assertEqual(stats["diagreport_identical"], stats["diagreport_copies"])
        # Every note names the patient exactly once (one or two given names, never the family name).
        for n in notes:
            names = [s for s in ground_truth_spans(n) if s[0] in ("given_name", "full_name", "family_name")]
            self.assertEqual(len(names), 1, n["id"])


if __name__ == "__main__":
    unittest.main()
