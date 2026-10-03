"""Load Synthea notes and build per-note ground truth from the same bundle's structured data.

Stdlib only, so it runs under the system Python 3.9 and inside the Presidio venv.

Unit = note. Synthea writes each note twice: once in DocumentReference.content and once, with
identical text, in DiagnosticReport.presentedForm. load_notes() keeps the DocumentReference copy
only and reports how many DiagnosticReport copies matched it, so no note is counted twice.

Ground truth = every occurrence in the note text of a string taken from that patient's structured
record (plus the bundle's facilities and practitioners). A string match proves the value is there;
it does not prove every PHI mention is found. A mention written in a form not listed here (for
example a nickname or "Dec 18") would be missed by this ground truth. profile_notes.py searches for
such forms separately.
"""
import base64
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CLEAN = os.path.join(ROOT, "out", "run", "fhir-clean")

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def date_forms(iso):
    """The written forms of one YYYY-MM-DD date that the profile searches for."""
    y, m, d = iso[:10].split("-")
    mi, di = int(m), int(d)
    return {
        iso[:10],
        f"{m}/{d}/{y}", f"{mi}/{di}/{y}", f"{mi}/{di}/{y[2:]}",
        f"{MONTHS[mi-1]} {di}, {y}", f"{MONTHS[mi-1][:3]} {di}, {y}", f"{di} {MONTHS[mi-1]} {y}",
    }


def _decode(data):
    return base64.b64decode(data).decode("utf-8")


def _names(resource):
    out = []
    for n in resource.get("name", []) or []:
        given = [g for g in (n.get("given") or []) if g]
        out.append((given, n.get("family") or "", n.get("use") or ""))
    return out


def bundle_files(folder=CLEAN):
    # Patient bundles start with the name; hospital/practitioner info files start lower case.
    return sorted(f for f in glob.glob(os.path.join(folder, "*.json"))
                  if os.path.basename(f)[0].isupper())


def shared_directory(folder=CLEAN):
    """Facility and practitioner names from Synthea's shared info bundles."""
    orgs, practs = set(), set()
    for f in glob.glob(os.path.join(folder, "*Information*.json")):
        b = json.load(open(f))
        for e in b.get("entry", []):
            r = e["resource"]
            if r["resourceType"] in ("Organization", "Location") and r.get("name"):
                orgs.add(r["name"])
            if r["resourceType"] == "Practitioner":
                for given, family, _ in _names(r):
                    practs.add(" ".join(given + [family]).strip())
    return orgs, practs


def load_notes(folder=CLEAN):
    """Return (notes, stats). Each note: dict(id, patient, text, phi) where phi maps type -> set of strings."""
    orgs_all, practs_all = shared_directory(folder)
    notes = []
    stats = {"bundles": 0, "docref_notes": 0, "diagreport_copies": 0, "diagreport_identical": 0}
    for f in bundle_files(folder):
        b = json.load(open(f))
        stats["bundles"] += 1
        res = [e["resource"] for e in b.get("entry", [])]
        pat = next(r for r in res if r["resourceType"] == "Patient")
        phi = {k: set() for k in TYPES}
        for given, family, use in _names(pat):
            for g in given:
                phi["given_name"].add(g)
            if family:
                phi["maiden_name" if use == "maiden" else "family_name"].add(family)
            if given and family:
                phi["full_name"].add(" ".join(given + [family]))
                phi["full_name"].add(f"{given[0]} {family}")
        phi["full_name"].update(" ".join(g) for g, _, _ in _names(pat) if len(g) > 1)
        if pat.get("birthDate"):
            phi["birth_date"].update(date_forms(pat["birthDate"]))
        for a in pat.get("address", []) or []:
            phi["street_address"].update(a.get("line", []) or [])
            if a.get("city"):
                phi["city"].add(a["city"])
            if a.get("postalCode"):
                phi["zip"].add(a["postalCode"])
        for t in pat.get("telecom", []) or []:
            if t.get("value"):
                phi["phone_email"].add(t["value"])
        for i in pat.get("identifier", []) or []:
            if i.get("value"):
                phi["record_ids"].add(str(i["value"]))  # MRN, SSN, licence, passport
        if pat.get("deceasedDateTime"):
            phi["death_date"].update(date_forms(pat["deceasedDateTime"]))
        enc_dates = set()
        for r in res:
            if r["resourceType"] == "Encounter":
                p = r.get("period", {})
                for k in ("start", "end"):
                    if p.get(k):
                        enc_dates.update(date_forms(p[k]))
            if r["resourceType"] in ("Organization", "Location") and r.get("name"):
                phi["facility"].add(r["name"])
            if r["resourceType"] == "Practitioner":
                for given, family, _ in _names(r):
                    phi["practitioner"].add(" ".join(given + [family]).strip())
        phi["encounter_date"] = enc_dates
        # Facilities and practitioners referenced from this bundle by display text.
        for s in re.findall(r'"display": "Dr\. ([^"]+)"', json.dumps(b)):
            phi["practitioner"].add(s)
        for r in res:
            for key in ("serviceProvider",):
                d = (r.get(key) or {}).get("display")
                if d:
                    phi["facility"].add(d)
            if r["resourceType"] == "DocumentReference":
                d = (r.get("custodian") or {}).get("display")
                if d:
                    phi["facility"].add(d)
        phi["facility"].update(orgs_all)
        phi["practitioner"].update(practs_all)
        drtexts = []
        for r in res:
            if r["resourceType"] == "DiagnosticReport":
                for c in r.get("presentedForm", []) or []:
                    if c.get("data"):
                        drtexts.append(_decode(c["data"]))
        doc_texts = set()
        for r in res:
            if r["resourceType"] != "DocumentReference":
                continue
            for c in r.get("content", []) or []:
                a = c.get("attachment", {})
                if a.get("data") and str(a.get("contentType", "")).startswith("text/"):
                    text = _decode(a["data"])
                    doc_texts.add(text)
                    notes.append({"id": r["id"], "patient": pat["id"], "text": text,
                                  "phi": phi, "birth": pat.get("birthDate")})
                    stats["docref_notes"] += 1
        stats["diagreport_copies"] += len(drtexts)
        stats["diagreport_identical"] += sum(t in doc_texts for t in drtexts)
    return notes, stats


# Order matters only for display. All are HIPAA Safe Harbor identifiers except where noted.
TYPES = ["given_name", "family_name", "maiden_name", "full_name", "birth_date", "death_date",
         "encounter_date", "street_address", "city", "zip", "phone_email", "record_ids",
         "facility", "practitioner"]


def find_spans(text, value):
    """Case-sensitive whole-token matches of value in text."""
    if not value or len(value) < 2 or value not in text:
        return []
    pat = r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])"
    return [(m.start(), m.end()) for m in re.finditer(pat, text)]


# Ages as Synthea writes them: "4 year-old" and "quit smoking at age 16".
AGE_RE = re.compile(r"\b(\d{1,3})(?= year-old\b)|\bage (\d{1,3})\b")


def ground_truth_spans(note):
    """List of (type, start, end, text). Ages are added as type 'age' (PHI only when over 89)."""
    text = note["text"]
    spans = []
    for t in TYPES:
        for v in note["phi"][t]:
            for s, e in find_spans(text, v):
                spans.append((t, s, e, text[s:e]))
    for m in AGE_RE.finditer(text):
        g = 1 if m.group(1) else 2
        t = "age_over_89" if int(m.group(g)) > 89 else "age_89_or_under"
        spans.append((t, m.start(g), m.end(g), m.group(g)))
    # One mention, one span: drop a span lying inside a longer one ("Agnes" inside "Agnes Laree").
    spans.sort(key=lambda x: (x[1], -(x[2] - x[1])))
    kept = []
    for sp in spans:
        if any(k[1] <= sp[1] and sp[2] <= k[2] and (k[1], k[2]) != (sp[1], sp[2]) for k in kept):
            continue
        if any((k[1], k[2]) == (sp[1], sp[2]) for k in kept):
            continue
        kept.append(sp)
    return kept
