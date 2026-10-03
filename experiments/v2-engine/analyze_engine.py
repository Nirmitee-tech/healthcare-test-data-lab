"""Compare three views of the injected defects, per hl7 file (= patient bundle):

  manifest : what messify says it injected (defects.manifest.jsonl)
  text     : what the .hl7 files carry, read with plain string splitting
  engine   : what the engine's transformer extracted from its parsed tree (results/engine-*.jsonl)

Unit: message for ACK counts, OBX segment for local codes, patient (hl7 file) for PID defects.
"""
import argparse
import collections
import json
from pathlib import Path

from send_mllp import split_messages


def seg_fields(msg, seg):
    return [s.split("|") for s in msg.split("\r") if s.startswith(seg + "|")]


def text_view(src):
    per_ctrl, per_file = {}, collections.defaultdict(lambda: collections.Counter())
    for p in sorted(Path(src).glob("*.hl7")):
        for m in split_messages(p.read_text()):
            msh = seg_fields(m, "MSH")[0]
            pid = seg_fields(m, "PID")[0]
            cx = pid[3].split("^")
            dob = pid[7]
            fam = pid[5].split("^")[0]
            local = sum(1 for o in seg_fields(m, "OBX") if o[3].split("^")[2:3] == ["L"])
            weights = sum(1 for o in seg_fields(m, "OBX") if o[3].split("^")[0] == "29463-7")
            per_ctrl[msh[9]] = {"file": p.name, "missing_authority": len(cx) < 4 or cx[3] == "",
                                "partial_dob": 0 < len(dob) < 8, "local": local, "family": fam}
            c = per_file[p.stem]
            c["messages"] += 1
            c["local_obx"] += local
            c["weight_obx"] += weights
            c["obx"] += len(seg_fields(m, "OBX"))
            if msh[8].startswith("ADT"):
                c["missing_authority"] += int(per_ctrl[msh[9]]["missing_authority"])
                c["partial_dob"] += int(per_ctrl[msh[9]]["partial_dob"])
                c["family_trailing_space"] += int(fam != fam.rstrip())
    return per_ctrl, per_file


def manifest_view(path):
    per_file = collections.defaultdict(collections.Counter)
    for line in open(path):
        d = json.loads(line)
        per_file[Path(d["bundle"]).stem][d["defect"]] += 1
    return per_file


def engine_view(path):
    rows = {}
    for line in open(path):
        line = line.strip()
        if line:
            d = json.loads(line)
            rows[d["control_id"]] = d
    return rows


def compare(engine, per_ctrl):
    agree = collections.Counter()
    disagree = []
    for cid, t in per_ctrl.items():
        e = engine.get(cid)
        if e is None:
            agree["missing_in_engine"] += 1
            continue
        checks = {"missing_authority": e["flag_missing_authority"] == t["missing_authority"],
                  "partial_dob": e["flag_partial_dob"] == t["partial_dob"],
                  "local": e["flag_local_lab_codes"] == t["local"],
                  "family_exact": e["pid5_family"] == t["family"]}
        for k, ok in checks.items():
            agree[k + ("_match" if ok else "_MISMATCH")] += 1
            if not ok and len(disagree) < 10:
                disagree.append({"control_id": cid, "check": k, "text": t, "engine": {
                    kk: e[kk] for kk in ("pid3_4_authority", "pid7_dob", "flag_local_lab_codes", "pid5_family")}})
    flagged = collections.Counter()
    for e in engine.values():
        if e["type"].startswith("ADT"):
            flagged["adt_missing_authority"] += int(e["flag_missing_authority"])
            flagged["adt_partial_dob"] += int(e["flag_partial_dob"])
        flagged["obx_local_code"] += e["flag_local_lab_codes"]
        flagged["obx_total"] += e["obx_count"]
        flagged["messages"] += 1
    return dict(agree), disagree, dict(flagged)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    per_ctrl, text_files = text_view(a.src)
    man = manifest_view(a.manifest)
    tot_text = collections.Counter()
    for c in text_files.values():
        tot_text.update(c)
    tot_man = collections.Counter()
    for stem in text_files:
        tot_man.update(man.get(stem, {}))
    stems_not_in_v2 = sorted(set(man) - set(text_files))
    # local codes the manifest injected in bundles that do reach v2, vs local codes present in v2 OBX
    out = {"text_totals": dict(tot_text), "manifest_totals_for_v2_patients": dict(tot_man),
           "manifest_bundles_without_hl7_file": stems_not_in_v2,
           "manifest_totals_all": dict(sum((collections.Counter(v) for v in man.values()), collections.Counter()))}
    for ch in ("strict", "lenient", "file"):
        p = Path(a.results) / f"engine-{ch}.jsonl"
        if p.exists():
            agree, disagree, flagged = compare(engine_view(p), per_ctrl)
            out[ch] = {"engine_flagged": flagged, "engine_vs_text": agree, "examples_of_mismatch": disagree}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
