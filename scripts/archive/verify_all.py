import subprocess, sys, os

sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"

import os as _os

# ── Pre-flight: warn if server is running (Windows DB lock) ──
def _server_running():
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
        return True
    except Exception:
        return False

if _server_running():
    print("ℹ️  Server is live on :8000 — ci_check will run in read-only mode")
    _os.environ["CI_SKIP_CLEANUP"] = "1"
    _os.environ["CI_SKIP_E2E_IMAGES"] = "1"

checks = [
    ("DB WAL mode",        ["python", "check_db.py"]),
    ("API endpoints",      ["python", "check_api.py"]),
    ("Frontend pages",     ["python", "check_frontend.py"]),
    ("Pipeline dry-run",   ["python", "run_pipeline_dryrun.py"]),
    ("Full test suite",    ["python", "ci_check.py"]),
]

child_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

results = []
for name, cmd in checks:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=child_env)
    status = "✅ PASS" if r.returncode == 0 else "❌ FAIL"
    results.append((name, status, r.stdout, r.stderr))
    print(f"{status}  {name}")

print("\n--- Summary ---")
for name, status, out, err in results:
    print(f"{status}  {name}")
    if "FAIL" in status:
        print(f"       stdout: {out.strip()[:10000]}")
        print(f"       stderr: {err.strip()[:10000]}")

failed = [r for r in results if "FAIL" in r[1]]
print(f"\n{'All checks passed ✅' if not failed else f'{len(failed)} check(s) failed ❌'}")
print("\nLocal URL → http://127.0.0.1:8000")
sys.exit(0 if not failed else 1)