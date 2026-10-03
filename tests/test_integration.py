"""End to end: Synthea in Docker -> scrub -> safety gate -> messify -> HL7 v2 -> a fresh HAPI FHIR server.

Needs Docker and tools/synthea-with-dependencies.jar. Starts its own HAPI container on port 8091 and
removes it afterwards, so counts are never polluted by an earlier load. Takes about two minutes.
"""
import json
import shutil
import subprocess
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from lab import load, messify, pipeline
from lab.fhirutil import read_bundles

PORT = 8091
BASE = f"http://localhost:{PORT}/fhir"
CONTAINER = "synthlab-hapi-itest"


def _wait_for(url, seconds=180):
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=5):
                return
        except Exception:
            time.sleep(3)
    raise RuntimeError(f"{url} did not come up in {seconds}s")


@unittest.skipUnless(shutil.which("docker"), "docker not available")
class PipelineIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
        subprocess.run(["docker", "run", "-d", "--name", CONTAINER, "-p", f"127.0.0.1:{PORT}:8080",
                        "hapiproject/hapi:latest"], check=True, capture_output=True)
        cls.tmp = tempfile.mkdtemp(prefix="synthlab-")
        _wait_for(f"{BASE}/metadata")
        cls.summary = pipeline.run(Path(cls.tmp) / "run", patients=5, seed=11, rate=0.5,
                                   profile="loadable", fhir_base=BASE)
        cls.out = Path(cls.tmp) / "run"

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_raw_synthea_has_real_facility_phones_and_clean_output_has_none(self):
        self.assertGreater(self.summary["raw_safety"].get("phone-real-format", 0), 0)
        self.assertEqual(self.summary["clean_safety"], {})

    def test_every_bundle_loads(self):
        self.assertEqual(self.summary["load"]["rejected"], [])
        self.assertEqual(self.summary["load"]["loaded"], len(list((self.out / "fhir-messy").glob("*.json"))))

    def test_server_holds_what_the_manifest_says(self):
        for row in self.summary["server_checks"]:
            self.assertTrue(row["ok"], row)
        self.assertGreater(sum(self.summary["messify"]["defects_injected"].values()), 0)

    def test_patient_names_on_server_have_no_digits(self):
        with urllib.request.urlopen(f"{BASE}/Patient?_count=100&_elements=name", timeout=30) as r:
            body = json.load(r)
        names = [p for e in body.get("entry", []) for n in e["resource"].get("name", [])
                 for p in n.get("given", []) + [n.get("family", "")]]
        self.assertTrue(names)
        self.assertFalse([n for n in names if any(c.isdigit() for c in n)])

    def test_hl7v2_files_match_patients(self):
        files = list((self.out / "hl7v2").glob("*.hl7"))
        self.assertEqual(len(files), self.summary["hl7v2"]["files"])
        msgs = files[0].read_text().strip().split("\r\n")
        self.assertTrue(all(m.startswith("MSH|^~\\&|") for m in msgs))

    def test_server_rejects_a_dangling_reference(self):
        # The "strict" defects exist to prove the receiving side refuses bad data.
        path, bundle = next((p, b) for p, b in read_bundles(self.out / "fhir-clean")
                            if b.get("type") == "transaction" and any(
                                e["resource"]["resourceType"] == "Observation" for e in b["entry"]))
        import random
        manifest = messify.messify_bundle(bundle, {"dangling_reference": messify.dangling_reference},
                                          1.0, random.Random(1))
        self.assertEqual(len(manifest), 1)
        status, _ = load._req("POST", BASE, bundle)
        self.assertGreaterEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
