"""Send every HL7 v2 message in a folder to an MLLP listener and record the ACK for each.

  python3 send_mllp.py --port 6661 --src ../../out/run/hl7v2 --out results/strict-acks.jsonl [--controls]

MLLP framing: 0x0B + message + 0x1C 0x0D. One TCP connection, messages sent one at a time,
waiting for each ACK. --controls also sends hand-made bad messages (positive controls), so a run
that returns only AA can be told apart from a listener that accepts anything.
"""
import argparse
import json
import re
import socket
import sys
from pathlib import Path

SB, EB, CR = b"\x0b", b"\x1c", b"\x0d"


def split_messages(text):
    segs = [s for s in re.split(r"\r\n|\r|\n", text) if s.strip()]
    msgs, cur = [], []
    for s in segs:
        if s.startswith("MSH|") and cur:
            msgs.append("\r".join(cur) + "\r")
            cur = []
        cur.append(s)
    if cur:
        msgs.append("\r".join(cur) + "\r")
    return msgs


def field(msg, seg, n):
    for s in msg.split("\r"):
        if s.startswith(seg + "|"):
            parts = s.split("|")
            idx = n - 1 if seg == "MSH" else n  # MSH-1 is the separator itself
            return parts[idx] if idx < len(parts) else ""
    return ""


def send(sock, msg, timeout=30):
    sock.sendall(SB + msg.encode("utf-8") + EB + CR)
    sock.settimeout(timeout)
    buf = b""
    while not buf.endswith(EB + CR):
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    return buf.strip(SB).rstrip(CR).rstrip(EB).decode("utf-8", "replace")


BASE_ADT = ("MSH|^~\\&|SYNTHLAB|SYNTHETIC-FACILITY|RECEIVER|RECEIVER|20150409211346+0000||ADT^A04^ADT_A01|{cid}|P|2.5.1\r"
            "EVN|A04|20150409211346+0000\r"
            "PID|1||{mrn}^^^SYNTHEA^MR||Control^Case||{dob}|M\r"
            "PV1|1|O\r")
BASE_ORU = ("MSH|^~\\&|SYNTHLAB|SYNTHETIC-FACILITY|RECEIVER|RECEIVER|20181201181346+0000||ORU^R01^ORU_R01|{cid}|P|2.5.1\r"
            "PID|1||CTRL-1^^^SYNTHEA^MR||Control^Case||20021019|M\r"
            "OBR|1||RPT-1|58410-2^CBC panel^LN|||20181201181346+0000\r"
            "OBX|1|NM|6690-2^Leukocytes^LN||{value}|10*3/uL^10*3/uL^UCUM|||||F|||20181201181346+0000\r")

CONTROLS = [
    ("ctrl-good-adt", "valid ADT, should be AA", BASE_ADT.format(cid="CTRL-GOOD", mrn="CTRL-1", dob="20021019")),
    ("ctrl-dob-iso", "PID-7 as 2002-10-19 (not a v2 TS)", BASE_ADT.format(cid="CTRL-DOB", mrn="CTRL-2", dob="2002-10-19")),
    ("ctrl-nm-text", "OBX-2 NM with value 'abc'", BASE_ORU.format(cid="CTRL-NM", value="abc")),
    ("ctrl-no-mrn", "PID-3.1 empty, the filter should reject (AR)", BASE_ADT.format(cid="CTRL-NOMRN", mrn="", dob="20021019")),
    ("ctrl-bad-type", "MSH-9 ZZZ^Z99", BASE_ADT.format(cid="CTRL-TYPE", mrn="CTRL-3", dob="20021019").replace("ADT^A04^ADT_A01", "ZZZ^Z99")),
    ("ctrl-not-hl7", "plain text, not HL7", "hello, this is not an HL7 message\r"),
]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    work = []
    for p in sorted(Path(args.src).glob("*.hl7")):
        for m in split_messages(p.read_text()):
            work.append((p.name, "", m))
    if args.limit:
        work = work[:args.limit]
    if args.controls:
        work += [(name, note, m) for name, note, m in CONTROLS]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    counts = {}
    sock = socket.create_connection((args.host, args.port))
    with open(args.out, "w") as f:
        for src, note, m in work:
            try:
                ack = send(sock, m)
            except (socket.timeout, ConnectionError) as e:
                ack = f"__NO_ACK__ {e}"
                sock.close()
                sock = socket.create_connection((args.host, args.port))
            msa1 = field(ack, "MSA", 1) or ("NONE" if ack.startswith("__NO_ACK__") else "?")
            row = {"src": src, "note": note, "msh9": field(m, "MSH", 9), "msh10": field(m, "MSH", 10),
                   "ack_code": msa1, "ack_ctrl": field(ack, "MSA", 2), "ack_text": field(ack, "MSA", 3),
                   "err": field(ack, "ERR", 3) + " " + field(ack, "ERR", 8) if "ERR|" in ack else "",
                   "ack_raw": ack[:300]}
            f.write(json.dumps(row) + "\n")
            key = ("control:" + src if note else row["msh9"].split("^")[0] + "^" + row["msh9"].split("^")[1]
                   if "^" in row["msh9"] else row["msh9"])
            counts.setdefault(key, {}).setdefault(msa1, 0)
            counts[key][msa1] += 1
    sock.close()
    print(json.dumps({"port": args.port, "sent": len(work), "acks": counts}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
