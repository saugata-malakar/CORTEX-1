import sqlite3, glob, sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

dbs = glob.glob("**/*.db", recursive=True) + glob.glob("*.db")
if not dbs:
    print("❌ No SQLite DB found"); sys.exit(1)

for path in set(dbs):
    con = sqlite3.connect(path)
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    pool = con.execute("PRAGMA busy_timeout").fetchone()[0]
    print(f"DB: {path}")
    print(f"  journal_mode = {mode}  ({'✅' if mode == 'wal' else '❌ expected wal'})")
    con.close()
