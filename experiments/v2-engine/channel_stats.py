"""Print RECEIVED/FILTERED/SENT/ERROR counts per channel and connector, as the engine reports them."""
import json

from oie_api import BASE, session

s = session()
st = s.get(f"{BASE}/channels/statuses", headers={"Accept": "application/json"}).json()
out = {}
for d in st["list"]["dashboardStatus"]:
    def stats(x):
        return {e["com.mirth.connect.donkey.model.message.Status"]: e["long"] for e in x["statistics"]["entry"]}
    kids = d["childStatuses"]["dashboardStatus"]
    kids = kids if isinstance(kids, list) else [kids]
    out[d["name"]] = {"channel": stats(d), "connectors": {k["name"]: stats(k) for k in kids}}
print(json.dumps(out, indent=2))
