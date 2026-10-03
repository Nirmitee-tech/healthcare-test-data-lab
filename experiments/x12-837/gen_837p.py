"""Minimal 837P (005010X222A1) from a handful of Synthea professional Claims, for syntax testing only.

  python3 gen_837p.py ../../out/run/fhir-clean out/sample-837p.x12 [n_claims]

What Synthea does not provide and this script fills in (each one labelled below):
  - ICD-10-CM diagnoses: Synthea codes Conditions in SNOMED CT. DX_MAP is a hand-picked crosswalk
    for five SNOMED codes. These are candidate mappings written for this test, not reviewed by a
    certified coder; do not reuse them for real billing.
  - CPT procedure codes: Synthea codes the visit in SNOMED. PROC_MAP maps two "encounter" SNOMED
    codes to CPT 99213. The visit level (13) cannot be derived from Synthea data; it is a fixed guess.
  - Member id, payer id, billing provider tax id and address: absent in Synthea Claim/EOB; filled
    with obviously synthetic values.
  - Billing NPI: Synthea's practitioner NPI from the EOB (9999-prefixed, valid check digit, not
    registered in NPPES per FINDINGS.md). It is an individual NPI used on an organization loop.
Claims are picked when their first diagnosis and first item are both in the maps and the payer is
not NO_INSURANCE.
"""
import hashlib
import json
import sys
from pathlib import Path

DX_MAP = {  # SNOMED CT -> ICD-10-CM (candidate, unreviewed)
    "444814009": "J0190",   # Viral sinusitis -> Acute sinusitis, unspecified
    "195662009": "J029",    # Acute viral pharyngitis -> Acute pharyngitis, unspecified
    "10509002": "J209",     # Acute bronchitis -> Acute bronchitis, unspecified
    "66383009": "K0510",    # Gingivitis -> Chronic gingivitis, plaque induced
    "73595000": "Z733",     # Stress -> Stress, not elsewhere classified
}
PROC_MAP = {  # SNOMED CT -> CPT (candidate; visit level is a guess)
    "185345009": "99213",   # Encounter for symptom
    "185347001": "99213",   # Encounter for problem
}


def h(s, n):
    return hashlib.sha1(s.encode()).hexdigest()[:n].upper()


def pick(src, n):
    out = []
    for p in sorted(Path(src).glob("*.json")):
        b = json.loads(p.read_text())
        by = {e.get("fullUrl"): e["resource"] for e in b["entry"]}
        pat = next((e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Patient"), None)
        eobs = {e["resource"].get("claim", {}).get("reference"): e["resource"] for e in b["entry"]
                if e["resource"]["resourceType"] == "ExplanationOfBenefit"}
        for e in b["entry"]:
            r = e["resource"]
            if r["resourceType"] != "Claim" or r["type"]["coding"][0]["code"] != "professional" or not r.get("diagnosis"):
                continue
            payer = r["insurance"][0]["coverage"].get("display", "")
            if payer == "NO_INSURANCE":
                continue
            dx = [by[d["diagnosisReference"]["reference"]]["code"]["coding"][0]["code"] for d in r["diagnosis"]]
            item = r["item"][0]
            proc = item["productOrService"]["coding"][0]["code"]
            if dx[0] not in DX_MAP or proc not in PROC_MAP or "net" not in item:
                continue
            eob = eobs.get(e.get("fullUrl"), {})
            npi = eob.get("provider", {}).get("reference", "").rsplit("|", 1)[-1]
            out.append({"claim": r, "patient": pat, "dx": [d for d in dx if d in DX_MAP], "proc": proc,
                        "payer": payer, "npi": npi, "pos": (eob.get("item", [{}])[0].get("locationCodeableConcept", {})
                                                             .get("coding", [{}])[0].get("code", "11"))})
            if len(out) >= n:
                return out
    return out


def segs_for(c, i):
    cl, pat = c["claim"], c["patient"]
    name = pat["name"][0]
    addr = pat["address"][0]
    amt = f'{cl["item"][0]["net"]["value"]:.2f}'
    dos = cl["billablePeriod"]["start"][:10].replace("-", "")
    hi = "*".join(("ABK:" if k == 0 else "ABF:") + DX_MAP[d] for k, d in enumerate(c["dx"][:12]))
    member = "SYN" + h(pat["id"], 9)          # synthetic member id: Synthea has none
    payer_id = "SYN" + h(c["payer"], 5)       # synthetic payer id
    clm_id = h(cl["id"], 20)
    return [
        f"HL*{2 * i + 1}**20*1", f"NM1*85*2*SYNTHETIC BILLING PROVIDER*****XX*{c['npi']}",
        "N3*100 TEST STREET", "N4*BOSTON*MA*021100000", "REF*EI*999999999",
        f"HL*{2 * i + 2}*{2 * i + 1}*22*0", "SBR*P*18*******CI",
        f"NM1*IL*1*{name['family'].upper()}*{name['given'][0].upper()}****MI*{member}",
        f"N3*{' '.join(addr.get('line', ['UNKNOWN'])).upper()[:55]}",
        f"N4*{addr.get('city', 'BOSTON').upper()}*{addr.get('state', 'MA')}*{(addr.get('postalCode') or '02110').ljust(5, '0')[:5]}",
        f"DMG*D8*{pat['birthDate'].replace('-', '')}*{'F' if pat.get('gender') == 'female' else 'M'}",
        f"NM1*PR*2*{c['payer'].upper()}*****PI*{payer_id}",
        f"CLM*{clm_id}*{amt}***{c['pos'] if c['pos'] in ('11', '19', '20', '21', '22') else '11'}:B:1*Y*A*Y*Y",
        f"HI*{hi}", "LX*1", f"SV1*HC:{PROC_MAP[c['proc']]}*{amt}*UN*1***1", f"DTP*472*D8*{dos}",
    ]


def build(claims):
    body = ["BHT*0019*00*SYNTH0001*20261003*1200*CH", "NM1*41*2*SYNTHLAB SUBMITTER*****46*SYNSUB01",
            "PER*IC*TEST CONTACT*TE*5555550100", "NM1*40*2*SYNTHLAB RECEIVER*****46*SYNRCV01"]
    for i, c in enumerate(claims):
        body += segs_for(c, i)
    st = ["ST*837*0001*005010X222A1"] + body
    st.append(f"SE*{len(st) + 1}*0001")
    isa = "ISA*00*          *00*          *ZZ*SYNSUB01       *ZZ*SYNRCV01       *261003*1200*^*00501*000000001*0*T*:"
    return "~\n".join([isa, "GS*HC*SYNSUB01*SYNRCV01*20261003*1200*1*X*005010X222A1"] + st +
                      ["GE*1*1", "IEA*1*000000001"]) + "~\n"


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    claims = pick(src, n)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(build(claims))
    print(json.dumps([{"claim_id": c["claim"]["id"], "snomed_dx": c["dx"], "icd10cm": [DX_MAP[d] for d in c["dx"]],
                       "snomed_proc": c["proc"], "cpt": PROC_MAP[c["proc"]], "payer": c["payer"], "pos": c["pos"]}
                      for c in claims], indent=1))
