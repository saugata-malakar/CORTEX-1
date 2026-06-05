import urllib.request, json, sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8000"

endpoints = [
    "/api/health",
    "/api/defects",
    "/api/defects?type=crack",
    "/api/defects?severity=critical",
    "/api/inspections",
]

all_ok = True
for ep in endpoints:
    try:
        with urllib.request.urlopen(BASE + ep, timeout=5) as r:
            body = json.loads(r.read())
            print(f"✅ {ep}  →  {r.status}")
    except Exception as e:
        print(f"❌ {ep}  →  {e}")
        all_ok = False

sys.exit(0 if all_ok else 1)
