import urllib.request, sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8000"

pages = [
    ("/",                           "text/html"),     # main dashboard
    ("/_next/static/chunks/0cz1d0mv5g_q7.js", "application/javascript"),  # a real static chunk
]

all_ok = True
for url, expected_type in pages:
    try:
        with urllib.request.urlopen(BASE + url, timeout=5) as r:
            print(f"✅ {url}  →  {r.status}")
    except Exception as e:
        print(f"❌ {url}  →  {e}")
        all_ok = False

sys.exit(0 if all_ok else 1)
