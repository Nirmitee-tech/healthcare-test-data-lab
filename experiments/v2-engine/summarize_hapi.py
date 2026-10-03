"""Group results/hapi.jsonl by message type and issue pattern. Unit: message."""
import collections
import json
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "results/hapi.jsonl"
by = collections.defaultdict(collections.Counter)
pat = collections.defaultdict(collections.Counter)
for line in open(path):
    d = json.loads(line)
    t = d["type"]
    by[t]["checked"] += 1
    if "parse_error" in d:
        by[t]["parse_error"] += 1
        pat[t][re.sub(r"'[^']*'", "'…'", d["parse_error"])[:160]] += 1
    elif d["issues"]:
        by[t]["with_issues"] += 1
        for i in set(re.sub(r"\(\d+>", "(N>", x) for x in d["issues"]):
            pat[t][i] += 1
    else:
        by[t]["clean"] += 1
print(json.dumps({"by_type": by, "patterns_messages_affected": pat}, indent=1))
