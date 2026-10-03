"""Safety scan: look for values in a test dataset that could point at real people or organizations.

What it catches: identifiers whose format means they could have been issued for real (SSNs outside
the never-issued 9xx range, NPIs starting 1 or 2, phone numbers outside the 555 area code, emails on
non-reserved domains). With --nppes it also asks the public NPPES registry whether an NPI is real.

What it does not catch: real names, real addresses or free-text notes copied from a chart. A clean
scan means "no real-looking identifiers found", which is weaker than "contains no PHI".
"""
import argparse
import json
import re
import sys
import time
import urllib.request

from lab.fhirutil import read_bundles

RESERVED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "test", "invalid")


def _ssn_is_safe(v):
    # SSA has never issued area numbers 000, 666 or 900-999.
    area = re.sub(r"\D", "", v)[:3]
    return area in ("000", "666") or area.startswith("9")


def _phone_is_safe(v):
    digits = re.sub(r"\D", "", v)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    # Area code 555 is unassigned; NXX-555-01XX numbers are reserved for fiction.
    return digits.startswith("555") or (digits[3:6] == "555" and digits[6:8] == "01")


def _email_is_safe(v):
    domain = v.rsplit("@", 1)[-1].lower()
    return any(domain == d or domain.endswith("." + d) for d in RESERVED_EMAIL_DOMAINS)


def _npi_is_safe(v):
    # Real NPIs start with 1 or 2. Anything else cannot be issued today.
    return not v[:1] in ("1", "2")


def scan_resource(r, findings, where):
    rt = r.get("resourceType")
    rid = r.get("id")
    for ident in r.get("identifier", []) or []:
        system = ident.get("system", "")
        value = str(ident.get("value", ""))
        if system.endswith("us-ssn") and not _ssn_is_safe(value):
            findings.append({"rule": "ssn-issuable", "resource": f"{rt}/{rid}", "value": value, "file": where})
        if system.endswith("us-npi") and not _npi_is_safe(value):
            findings.append({"rule": "npi-issuable", "resource": f"{rt}/{rid}", "value": value, "file": where})
    for t in r.get("telecom", []) or []:
        v = str(t.get("value", ""))
        if t.get("system") == "phone" and not _phone_is_safe(v):
            findings.append({"rule": "phone-real-format", "resource": f"{rt}/{rid}", "value": v, "file": where})
        if t.get("system") == "email" and not _email_is_safe(v):
            findings.append({"rule": "email-real-domain", "resource": f"{rt}/{rid}", "value": v, "file": where})


def nppes_hit(npi):
    url = f"https://npiregistry.cms.hhs.gov/api/?version=2.1&number={npi}"
    with urllib.request.urlopen(url, timeout=20) as r:
        return bool(json.load(r).get("result_count"))


def scan(folder, nppes=False):
    findings = []
    files = 0
    for path, bundle in read_bundles(folder):
        files += 1
        for e in bundle.get("entry", []):
            scan_resource(e.get("resource", {}), findings, path.name)
    if nppes:
        checked = {}
        for f in findings:
            if f["rule"] == "npi-issuable":
                if f["value"] not in checked:
                    checked[f["value"]] = nppes_hit(f["value"])
                    time.sleep(0.2)
                f["nppes_registered"] = checked[f["value"]]
    by_rule = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    return {"files": files, "findings_by_rule": by_rule, "findings": findings}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder")
    ap.add_argument("--nppes", action="store_true", help="look up issuable NPIs in the public NPPES registry")
    ap.add_argument("--report")
    args = ap.parse_args(argv)
    result = scan(args.folder, args.nppes)
    if args.report:
        with open(args.report, "w") as f:
            json.dump(result, f, indent=2)
    print(json.dumps({"files": result["files"], "findings_by_rule": result["findings_by_rule"]}, indent=2))
    # Fail loudly so a CI step cannot pass a dataset with findings.
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
