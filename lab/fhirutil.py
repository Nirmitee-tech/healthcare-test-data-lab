"""Small helpers shared by the lab steps. Stdlib only."""
import json
from pathlib import Path


def read_bundles(folder):
    """Yield (path, bundle) for every *.json bundle in folder, sorted by name."""
    for p in sorted(Path(folder).glob("*.json")):
        yield p, json.loads(p.read_text())


def write_bundle(path, bundle):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(bundle, indent=1))


def resources(bundle, rtype=None):
    for e in bundle.get("entry", []):
        r = e.get("resource", {})
        if rtype is None or r.get("resourceType") == rtype:
            yield r


def luhn_npi_check_digit(first9):
    """NPI check digit: Luhn over the prefix 80840 plus the first 9 digits."""
    digits = [int(c) for c in "80840" + first9]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def npi_is_well_formed(npi):
    # Format and check digit only. A well-formed NPI can still belong to a real provider.
    return len(npi) == 10 and npi.isdigit() and luhn_npi_check_digit(npi[:9]) == npi[9]
