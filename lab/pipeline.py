"""One command: generate with Synthea, scrub, safety-gate, messify, write HL7 v2, optionally load.

  python3 -m lab.pipeline --patients 50 --seed 42 --out out/run [--fhir-base http://localhost:8090/fhir]

Synthea runs in Docker (eclipse-temurin:17-jre) so no local Java is needed. The same seed gives
the same patients, the same scrub mapping and the same injected defects.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from lab import load, messify, safety, scrub, to_hl7v2

ROOT = Path(__file__).resolve().parent.parent
SYNTHEA_JAR = "tools/synthea-with-dependencies.jar"
SYNTHEA_URL = "https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"


def generate(out, patients, seed, state="Massachusetts", reference_date="20261003"):
    jar = ROOT / SYNTHEA_JAR
    if not jar.exists():
        raise SystemExit(f"Missing {jar}. Download it from {SYNTHEA_URL}")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", "-v", f"{ROOT}:/w", "-v", f"{out}:/o", "-w", "/w", "eclipse-temurin:17-jre",
           "java", "-jar", SYNTHEA_JAR, "-s", str(seed), "-cs", str(seed), "-r", reference_date,
           "-p", str(patients), "--exporter.baseDirectory=/o/synthea", "--exporter.fhir.export=true",
           "--exporter.hospital.fhir.export=true", "--exporter.practitioner.fhir.export=true", state]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    return out / "synthea" / "fhir"


def run(out, patients, seed, rate, profile, fhir_base=None, skip_generate=False):
    out = Path(out)
    raw = out / "synthea" / "fhir"
    if not skip_generate:
        if out.exists():
            shutil.rmtree(out)
        raw = generate(out, patients, seed)
    summary = {"raw_safety": safety.scan(raw)["findings_by_rule"]}
    summary["scrub"] = scrub.scrub_folder(raw, out / "fhir-clean")
    gate = safety.scan(out / "fhir-clean")
    summary["clean_safety"] = gate["findings_by_rule"]
    if gate["findings"]:
        print(json.dumps(summary, indent=2))
        raise SystemExit("Safety gate failed on scrubbed data; nothing downstream was written.")
    summary["messify"] = messify.messify_folder(out / "fhir-clean", out / "fhir-messy", rate, seed, profile)
    summary["hl7v2"] = to_hl7v2.convert_folder(out / "fhir-messy", out / "hl7v2")
    if fhir_base:
        summary["load"] = load.load_folder(fhir_base, out / "fhir-messy")
        rows, ok = load.check_against_manifest(fhir_base, out / "fhir-messy")
        summary["server_checks"] = rows
        summary["server_checks_ok"] = ok
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--patients", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--rate", type=float, default=0.1)
    ap.add_argument("--profile", choices=["loadable", "strict"], default="loadable")
    ap.add_argument("--out", default="out/run")
    ap.add_argument("--fhir-base")
    ap.add_argument("--skip-generate", action="store_true", help="reuse <out>/synthea/fhir")
    args = ap.parse_args(argv)
    summary = run(args.out, args.patients, args.seed, args.rate, args.profile, args.fhir_base, args.skip_generate)
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("server_checks_ok", True) and not summary.get("load", {}).get("rejected") else 1


if __name__ == "__main__":
    sys.exit(main())
