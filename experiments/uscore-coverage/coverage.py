"""Which US Core 6.1.0 profiles does a Synthea dataset populate? Read-only.
Usage: python3 experiments/uscore-coverage/coverage.py <bundle-folder> <us-core-package-dir>
Scope: every bundle in the folder. Unit: resource claiming the profile in meta.profile.
Claiming a profile in meta.profile is weaker than conforming to it; conformance is checked by the validator."""
import collections, glob, json, os, sys
folder, pkg = sys.argv[1], sys.argv[2]
profiles = {}
for f in glob.glob(os.path.join(pkg, "package", "StructureDefinition-*.json")):
    sd = json.load(open(f))
    if sd.get("kind") == "resource" and sd.get("derivation") == "constraint":
        profiles[sd["url"]] = (sd["type"], sd["name"])
seen = collections.Counter(); types = collections.Counter()
for f in glob.glob(os.path.join(folder, "*.json")):
    for e in json.load(open(f)).get("entry", []):
        r = e["resource"]; types[r["resourceType"]] += 1
        for p in r.get("meta", {}).get("profile", []):
            seen[p] += 1
present = sorted((v[1], seen[k]) for k, v in profiles.items() if seen[k])
missing = sorted((v[0], v[1]) for k, v in profiles.items() if not seen[k])
print(f"US Core resource profiles: {len(profiles)}; populated: {len(present)}; never populated: {len(missing)}")
print("\nNEVER POPULATED (resource type, profile):")
for t, n in missing: print(f"  {t:28s} {n}")
print("\nPOPULATED (profile, resources):")
for n, c in present: print(f"  {n:45s} {c}")
