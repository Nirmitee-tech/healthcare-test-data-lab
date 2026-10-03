"""Scrub: replace the real-world facility details Synthea copies from public directories.

Synthea draws hospitals and clinics from public CMS facility files, so its FHIR output carries real
facility names, street addresses and phone numbers, and its CSV export carries their real NPIs.
That is public directory data, not PHI, but a test claim from a fake patient should not name a real
hospital. This step swaps those values for synthetic ones and strips the numeric suffixes Synthea
adds to person names ("Dian810" -> "Dian").

Mappings are derived from a hash of the original value, so the same facility gets the same synthetic
name in every bundle and on every run. City, state and ZIP are kept for geographic realism.
"""
import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

from lab.fhirutil import luhn_npi_check_digit, read_bundles, write_bundle

KINDS = ["Clinic", "Medical Center", "Health Center", "Family Practice", "Hospital", "Urgent Care"]


def _h(value, n=8):
    return int(hashlib.sha256(value.encode()).hexdigest()[:n], 16)


def synthetic_npi(original):
    # 9-prefixed so it can never be issued; check digit is valid so format validators still pass.
    first9 = "9" + str(_h(original) % 10**8).zfill(8)
    return first9 + luhn_npi_check_digit(first9)


def synthetic_phone(original):
    # NXX-555-01XX numbers are reserved for fictional use.
    return f"555-555-01{_h(original) % 100:02d}"


def synthetic_org_name(original, city):
    kind = KINDS[_h(original) % len(KINDS)]
    return f"{city.title() if city else 'Synthetic'} {kind} {_h(original, 6) % 1000:03d}"


def synthetic_street(original):
    return f"{_h(original) % 900 + 100} Test Street"


class Scrubber:
    def __init__(self):
        self.text_map = {}
        self.npi_map = {}

    def learn(self, bundle):
        """Collect every real value that must change, before rewriting anything."""
        for e in bundle.get("entry", []):
            r = e.get("resource", {})
            rt = r.get("resourceType")
            if rt in ("Patient", "Practitioner", "RelatedPerson"):
                for n in r.get("name", []) or []:
                    for part in (n.get("given") or []) + [n.get("family") or ""]:
                        clean = re.sub(r"\d+$", "", part)
                        if clean != part and clean:
                            self.text_map[part] = clean
            if rt in ("Organization", "Location"):
                city = ((r.get("address") or [{}])[0] if isinstance(r.get("address"), list) else (r.get("address") or {})).get("city", "")
                if r.get("name") and r["name"] not in self.text_map:
                    self.text_map[r["name"]] = synthetic_org_name(r["name"], city)
                addrs = r.get("address") if isinstance(r.get("address"), list) else [r.get("address") or {}]
                for a in addrs:
                    for line in a.get("line", []) or []:
                        self.text_map.setdefault(line, synthetic_street(line))
            if rt in ("Organization", "Location", "PractitionerRole"):
                for t in r.get("telecom", []) or []:
                    if t.get("system") == "phone" and t.get("value"):
                        self.text_map.setdefault(t["value"], synthetic_phone(t["value"]))
            for ident in r.get("identifier", []) or []:
                v = str(ident.get("value", ""))
                if ident.get("system", "").endswith("us-npi") and v[:1] in ("1", "2"):
                    self.npi_map.setdefault(v, synthetic_npi(v))

    # Name tokens as Synthea writes them: letters followed by a numeric suffix.
    _NAME_TOKEN = re.compile(r"[A-Za-z][A-Za-z'\-]*\d+\b")

    def _fix_string(self, s):
        if s in self.npi_map:
            return self.npi_map[s]
        if s in self.text_map:
            return self.text_map[s]
        # Display strings such as "Dr. Gabriel934 Reilly981" hold several name tokens.
        return self._NAME_TOKEN.sub(lambda m: self.text_map.get(m.group(0), m.group(0)), s)

    def _fix_note(self, text):
        text = self._NAME_TOKEN.sub(lambda m: self.text_map.get(m.group(0), m.group(0)), text)
        if not hasattr(self, "_facility_values"):
            self._facility_values = sorted(
                (k for k in self.text_map if not self._NAME_TOKEN.fullmatch(k) and len(k) >= 6),
                key=len, reverse=True)
        for k in self._facility_values:
            if k in text:
                text = text.replace(k, self.text_map[k])
        return text

    def _walk(self, node):
        if isinstance(node, dict):
            # Clinical notes travel as base64 text attachments; decode, fix, re-encode.
            if str(node.get("contentType", "")).startswith("text/") and isinstance(node.get("data"), str):
                note = base64.b64decode(node["data"]).decode("utf-8")
                out = {k: self._walk(v) for k, v in node.items() if k != "data"}
                out["data"] = base64.b64encode(self._fix_note(note).encode("utf-8")).decode("ascii")
                return out
            return {k: self._walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [self._walk(v) for v in node]
        if isinstance(node, str):
            return self._fix_string(node)
        return node

    def apply(self, bundle):
        # Structured fields: whole-string matches. Text attachments: substring matches.
        # Free text in other places (for example Annotation.text) gets the name-token pass only.
        return strip_synthea_extensions(self._walk(bundle))


SYNTHEA_EXT_PREFIX = "http://synthetichealth.github.io/synthea/"


def strip_synthea_extensions(bundle):
    """Drop Synthea's own extensions (DALY, QALY, utilization counts).

    No published StructureDefinition exists for them, so the HL7 validator rejects them on
    Patient, the Patient then fails US Core, and every reference to that Patient fails too.
    Measured on 3 bundles (seed 42, 3 Oct 2026, US Core 6.1.0, terminology checks off): 2,412
    errors before, 0 after. Codes were not checked against terminology servers.
    """
    for e in bundle.get("entry", []):
        r = e.get("resource", {})
        if "extension" in r:
            kept = [x for x in r["extension"] if not str(x.get("url", "")).startswith(SYNTHEA_EXT_PREFIX)]
            if kept:
                r["extension"] = kept
            else:
                del r["extension"]
    return bundle


def scrub_folder(src, dst):
    loaded = list(read_bundles(src))
    s = Scrubber()
    for _, b in loaded:
        s.learn(b)
    for path, b in loaded:
        write_bundle(Path(dst) / path.name, s.apply(b))
    return {"bundles": len(loaded), "text_replacements": len(s.text_map), "npi_replacements": len(s.npi_map)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src")
    ap.add_argument("dst")
    args = ap.parse_args(argv)
    print(json.dumps(scrub_folder(args.src, args.dst), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
