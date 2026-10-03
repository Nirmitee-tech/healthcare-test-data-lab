"""Small client for the Open Integration Engine (Mirth Connect fork) REST API on :8443.

Default admin/admin login of a fresh container. Self-signed certificate, so TLS checks are off;
use this only against the local experiment container.
"""
import os
import requests
import urllib3

urllib3.disable_warnings()

BASE = os.environ.get("OIE_BASE", "https://127.0.0.1:8443/api")
HDR = {"X-Requested-With": "OpenAPI"}


def session(user="admin", password="admin"):
    s = requests.Session()
    s.verify = False
    s.headers.update(HDR)
    r = s.post(f"{BASE}/users/_login", data={"username": user, "password": password})
    r.raise_for_status()
    if "SUCCESS" not in r.text:
        raise SystemExit("login failed: " + r.text)
    return s


def xml_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def set_deploy_script(s, js):
    """Replace the global Deploy script. It runs inside the engine on every deploy."""
    cur = s.get(f"{BASE}/server/globalScripts").text
    start = cur.index("<string>Deploy</string>")
    a = cur.index("<string>", start + 10)
    b = cur.index("</string>", a)
    new = cur[:a] + "<string>" + xml_escape(js) + cur[b:]
    r = s.put(f"{BASE}/server/globalScripts", data=new.encode(), headers={"Content-Type": "application/xml"})
    r.raise_for_status()
