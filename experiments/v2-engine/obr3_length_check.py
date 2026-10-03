"""OBR-3 (filler order number) length and what truncation to the v2.5.1 maximum would do.
Unit: ORU^R01 message. Max length 22 is what HAPI 2.3's v2.5.1 OBR class reports for OBR-3."""
import collections
import sys
from pathlib import Path

from send_mllp import split_messages

src = Path(sys.argv[1] if len(sys.argv) > 1 else "../../out/run/hl7v2")
vals = []
for p in sorted(src.glob("*.hl7")):
    for m in split_messages(p.read_text()):
        for s in m.split("\r"):
            if s.startswith("OBR|"):
                vals.append(s.split("|")[3])
lengths = collections.Counter(len(v) for v in vals)
t22 = collections.Counter(v[:22] for v in vals)
print("OBR-3 values:", len(vals), "distinct:", len(set(vals)), "lengths:", dict(lengths))
print("distinct after truncation to 22:", len(t22), "values sharing a truncated key:",
      sum(c for c in t22.values() if c > 1))
