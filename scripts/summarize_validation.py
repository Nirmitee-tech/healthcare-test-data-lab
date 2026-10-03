"""Group HL7 validator errors by message pattern (UUIDs and numbers normalized).
Usage: python3 scripts/summarize_validation.py out/validation
Scope: every *.outcome.json in the folder. Unit: validator issue of severity error/fatal."""
import collections, glob, json, re, sys
c = collections.Counter(); ex = {}
files = sorted(glob.glob(sys.argv[1] + "/*.outcome.json"))
for f in files:
    d = json.load(open(f))
    issues = d.get("issue", []) if d.get("resourceType") == "OperationOutcome" else [i for e in d.get("entry", []) for i in e["resource"].get("issue", [])]
    for i in issues:
        if i["severity"] not in ("error", "fatal"):
            continue
        msg = i.get("details", {}).get("text", "")
        key = re.sub(r"urn:uuid:[0-9a-f-]+", "urn:uuid:X", msg)
        key = re.sub(r"\d+", "N", key)[:220]
        c[key] += 1
        ex.setdefault(key, (i.get("expression") or [""])[0])
print(f"bundles={len(files)} errors={sum(c.values())} patterns={len(c)}")
for k, v in c.most_common(25):
    print(f"{v:6d}  {k}\n        at {ex[k][:140]}")
