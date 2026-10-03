"""Print per-message status and errors the engine stored for a channel (for debugging and evidence).

  python3 inspect_messages.py <channelId> [limit]
"""
import json
import sys

from oie_api import BASE, session

s = session()
cid = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
r = s.get(f"{BASE}/channels/{cid}/messages", params={"limit": limit, "includeContent": "true"},
          headers={"Accept": "application/json"})
msgs = r.json().get("list", {}).get("message", [])
if isinstance(msgs, dict):
    msgs = [msgs]
for m in msgs:
    entries = m["connectorMessages"]["entry"]
    if isinstance(entries, dict):
        entries = [entries]
    for e in entries:
        cm = e["connectorMessage"]
        raw = (cm.get("raw") or {}).get("content", "") or ""
        msh10 = raw.split("\r")[0].split("|")[9] if raw.startswith("MSH") else ""
        err = cm.get("processingError") or ""
        print(m["messageId"], cm["metaDataId"], cm["status"], msh10, err.splitlines()[0:3] if err else "")
