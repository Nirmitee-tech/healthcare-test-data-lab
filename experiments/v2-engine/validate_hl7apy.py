"""Validate every message with hl7apy (VALIDATION_LEVEL.STRICT, v2.5.1) and group errors.

  python3 validate_hl7apy.py ../../out/run/hl7v2 > results/hl7apy.json

hl7apy strict checks message structure against its 2.5.1 reference (segment order, required
segments, cardinality) and datatype lengths and formats. It does not check code systems or
vocabulary. Unit: message. Also runs the same positive controls as send_mllp.py.
"""
import collections
import json
import re
import sys
from pathlib import Path

from hl7apy.consts import VALIDATION_LEVEL
from hl7apy.parser import parse_message

from send_mllp import CONTROLS, split_messages


def check(m):
    try:
        msg = parse_message(m, validation_level=VALIDATION_LEVEL.STRICT, find_groups=True)
        msg.validate()
        return None
    except Exception as e:  # hl7apy raises several exception classes; we record the message text
        return f"{type(e).__name__}: {e}"


def normalize(err):
    # strip values so identical problems group together
    return re.sub(r"'[^']*'", "'…'", err)[:200]


def main():
    src = Path(sys.argv[1])
    by_type = collections.defaultdict(collections.Counter)
    patterns = collections.defaultdict(collections.Counter)
    examples = {}
    for p in sorted(src.glob("*.hl7")):
        for m in split_messages(p.read_text()):
            mtype = m.split("\r")[0].split("|")[8]
            err = check(m)
            by_type[mtype]["checked"] += 1
            if err:
                by_type[mtype]["failed"] += 1
                key = normalize(err)
                patterns[mtype][key] += 1
                examples.setdefault(key, {"file": p.name, "control_id": m.split("\r")[0].split("|")[9], "error": err[:400]})
            else:
                by_type[mtype]["passed"] += 1
    # positive controls: the send_mllp.py set plus controls/*.hl7 (adds an ADT with no PV1)
    ctrl = {name: m for name, _, m in CONTROLS}
    for p in sorted(Path(__file__).parent.joinpath("controls").glob("*.hl7")):
        ctrl[p.stem] = p.read_bytes().decode()
    controls = {name: (check(m) or "PASS")[:200] for name, m in ctrl.items()}
    print(json.dumps({"by_message_type": by_type, "error_patterns": patterns, "examples": examples,
                      "controls": controls}, indent=2, default=dict))


if __name__ == "__main__":
    main()
