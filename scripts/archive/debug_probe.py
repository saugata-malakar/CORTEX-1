"""
Cortex — debug_probe.py
Production root-cause analysis & health check tool

Run this FIRST when investigating any production issue.
Probes every system layer and reports exactly where failures occur.

Usage:
    python debug_probe.py                     # full probe
    python debug_probe.py --layer db          # DB only
    python debug_probe.py --layer api         # API only
    python debug_probe.py --layer tiles       # tile assets only
    python debug_probe.py --layer pipeline    # pipeline smoke test
    python debug_probe.py --layer schema      # JSON schema validation
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
import traceback
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

log = logging.getLogger("cortex.probe")
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Paths — relative to project root
PROJECT_ROOT = Path(__file__).parent.resolve()
DB_PATH      = PROJECT_ROOT / "data" / "reports" / "defects.db"
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "out"
SCHEMA_PATH  = PROJECT_ROOT / "config" / "json_output_schema.json"
API_BASE     = os.getenv("CORTEX_API_BASE", "http://localhost:8000")

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"


# ---------------------------------------------------------------------------
# Result collector
# ---------------------------------------------------------------------------

class ProbeReport:
    def __init__(self):
        self.results: list[dict] = []

    def record(self, layer: str, check: str, status: str, detail: str = ""):
        icon = PASS if status == "pass" else (FAIL if status == "fail" else WARN)
        self.results.append({
            "layer": layer, "check": check,
            "status": status, "detail": detail,
        })
        line = f"  [{icon}] {check}"
        if detail:
            line += f"\n         → {detail}"
        log.info(line)

    def summary(self) -> dict:
        total  = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "pass")
        failed = sum(1 for r in self.results if r["status"] == "fail")
        warned = sum(1 for r in self.results if r["status"] == "warn")
        return {"total": total, "passed": passed, "failed": failed, "warned": warned}

    def has_failures(self) -> bool:
        return any(r["status"] == "fail" for r in self.results)


report = ProbeReport()


# ---------------------------------------------------------------------------
# Layer 1 — Database
# ---------------------------------------------------------------------------

def probe_db():
    log.info("\n═══ Layer: Database ═══")

    # 1a. File exists
    if not DB_PATH.exists():
        report.record("db", "DB file exists", "warn", f"{DB_PATH} not found — pipeline may not have run yet")
        return
    report.record("db", "DB file exists", "pass", f"{DB_PATH} ({DB_PATH.stat().st_size // 1024} KB)")

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.row_factory = sqlite3.Row

        # 1b. WAL mode active  [RC-07]
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        if mode == "wal":
            report.record("db", "WAL mode active [RC-07]", "pass")
        else:
            report.record("db", "WAL mode active [RC-07]", "warn",
                          f"journal_mode={mode} — concurrent reads may block writers")

        # 1c. Tables exist
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        for t in ("inspections", "defects"):
            if t in tables:
                report.record("db", f"Table '{t}' exists", "pass")
            else:
                report.record("db", f"Table '{t}' exists", "fail", "Table missing — run init_db()")

        # 1d. Row counts
        if "inspections" in tables:
            n = conn.execute("SELECT COUNT(*) FROM inspections").fetchone()[0]
            report.record("db", "Inspections row count", "pass" if n > 0 else "warn",
                          f"{n} rows" + (" — DB empty, no inspections run yet" if n == 0 else ""))

        if "defects" in tables:
            n = conn.execute("SELECT COUNT(*) FROM defects").fetchone()[0]
            report.record("db", "Defects row count", "pass" if n > 0 else "warn", f"{n} rows")

        # 1e. Integrity check
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result == "ok":
            report.record("db", "Integrity check", "pass")
        else:
            report.record("db", "Integrity check", "fail", result)

        # 1f. Foreign key violations
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                report.record("db", "Foreign key violations", "fail",
                              f"{len(violations)} violations found")
            else:
                report.record("db", "Foreign key violations", "pass")
        except sqlite3.OperationalError:
            report.record("db", "Foreign key violations", "warn", "Could not run FK check")

        # 1g. growth_acceleration NULL check  [RC-09]
        if "defects" in tables:
            nulls = conn.execute(
                "SELECT COUNT(*) FROM defects WHERE growth_acceleration IS NULL"
            ).fetchone()[0]
            if nulls > 0:
                report.record("db", "growth_acceleration NULL rows [RC-09]", "warn",
                              f"{nulls} rows have NULL — [RC-09] not fully applied")
            else:
                report.record("db", "growth_acceleration NULL rows [RC-09]", "pass")

        # 1h. warnings parseable  [RC-12]
        if "inspections" in tables:
            # Check if warnings column exists
            cols = {row[1] for row in conn.execute("PRAGMA table_info(inspections)").fetchall()}
            warn_col = "warnings" if "warnings" in cols else "warnings_json" if "warnings_json" in cols else None
            if warn_col:
                bad_json = 0
                for row in conn.execute(f"SELECT id, {warn_col} FROM inspections").fetchall():
                    val = row[1]
                    if val:
                        try:
                            json.loads(val)
                        except (json.JSONDecodeError, TypeError):
                            bad_json += 1
                if bad_json:
                    report.record("db", f"warnings parseable [RC-12]", "fail",
                                  f"{bad_json} rows have malformed JSON")
                else:
                    report.record("db", f"warnings parseable [RC-12]", "pass")

        conn.close()

    except sqlite3.Error as exc:
        report.record("db", "DB connection", "fail", str(exc))


# ---------------------------------------------------------------------------
# Layer 2 — API server
# ---------------------------------------------------------------------------

def probe_api():
    log.info("\n═══ Layer: API Server ═══")

    endpoints = [
        ("/api/health",       "Health endpoint [RC-18]"),
        ("/api/inspections",  "Inspections list"),
    ]

    for path, label in endpoints:
        url = f"{API_BASE}{path}"
        try:
            start = time.time()
            with urlopen(url, timeout=5) as resp:
                latency = round((time.time() - start) * 1000)
                body = resp.read().decode()
                data = json.loads(body)
                status_code = resp.status

            if status_code == 200:
                report.record("api", label, "pass", f"HTTP 200 in {latency}ms")
            else:
                report.record("api", label, "fail", f"HTTP {status_code}")

            # Health-specific checks
            if path == "/api/health":
                if data.get("status") == "ok":
                    report.record("api", "Health status=ok", "pass")
                elif data.get("status") == "degraded":
                    report.record("api", "Health status", "warn", "Status=degraded — check DB")
                else:
                    report.record("api", "Health status", "fail", f"Unexpected: {data.get('status')}")

        except HTTPError as exc:
            report.record("api", label, "fail", f"HTTP {exc.code}: {exc.reason}")
        except URLError as exc:
            report.record("api", label, "fail",
                          f"Connection refused — is server running? ({exc.reason})")
        except json.JSONDecodeError as exc:
            report.record("api", label, "fail", f"Response is not valid JSON: {exc}")
        except Exception as exc:
            report.record("api", label, "fail", traceback.format_exc().splitlines()[-1])

    # CORS header check  [RC-17]
    try:
        req = Request(f"{API_BASE}/api/health")
        req.add_header("Origin", "http://localhost:3000")
        with urlopen(req, timeout=5) as resp:
            cors = resp.headers.get("Access-Control-Allow-Origin", "")
            if cors:
                report.record("api", "CORS header present [RC-17]", "pass", f"Allow-Origin: {cors}")
            else:
                report.record("api", "CORS header present [RC-17]", "fail",
                              "[RC-17] CORS missing — frontend JS fetch will be blocked")
    except Exception:
        report.record("api", "CORS header check [RC-17]", "warn", "Could not verify — server may be down")


# ---------------------------------------------------------------------------
# Layer 3 — Tile assets
# ---------------------------------------------------------------------------

def probe_tiles():
    log.info("\n═══ Layer: Tile Assets ═══")

    if not FRONTEND_DIR.exists():
        report.record("tiles", "frontend/ directory", "warn", f"{FRONTEND_DIR} not found")
        return
    report.record("tiles", "frontend/ directory", "pass")

    tile_dir = FRONTEND_DIR / "tiles"
    if not tile_dir.exists():
        report.record("tiles", "tiles/ directory", "warn",
                      "[RC-15] Tile directory missing — facade map may be blank")
    else:
        report.record("tiles", "tiles/ directory", "pass")
        for zoom in range(3):
            zoom_dir = tile_dir / str(zoom)
            if not zoom_dir.exists():
                report.record("tiles", f"Zoom level {zoom}", "warn",
                              f"{zoom_dir} missing — [RC-15] map may fail at zoom {zoom}")
                continue
            tiles = list(zoom_dir.rglob("*.png")) + list(zoom_dir.rglob("*.jpg"))
            if tiles:
                report.record("tiles", f"Zoom level {zoom}", "pass", f"{len(tiles)} tiles")
            else:
                report.record("tiles", f"Zoom level {zoom}", "warn", f"No tile files in {zoom_dir}")

    for fname in ["index.html"]:
        p = FRONTEND_DIR / fname
        status = "pass" if p.exists() else "warn"
        detail = "" if p.exists() else f"{p} not found"
        report.record("tiles", f"Frontend file: {fname}", status, detail)


# ---------------------------------------------------------------------------
# Layer 4 — Pipeline smoke test
# ---------------------------------------------------------------------------

def probe_pipeline():
    log.info("\n═══ Layer: Pipeline ═══")

    # Module imports
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.pipeline import CortexPipeline
        report.record("pipeline", "pipeline.py importable", "pass")
    except ImportError as exc:
        report.record("pipeline", "pipeline.py importable", "fail", str(exc))
        return

    # Config file
    config_path = PROJECT_ROOT / "config" / "pipeline_config.yaml"
    if not config_path.exists():
        report.record("pipeline", "pipeline_config.yaml exists", "warn", "Config not found")
    else:
        report.record("pipeline", "pipeline_config.yaml exists", "pass")

    # Check for PIPELINE_VERSION constant
    try:
        from src.pipeline import PIPELINE_VERSION
        report.record("pipeline", "PIPELINE_VERSION constant [RC-05]", "pass",
                      f"version={PIPELINE_VERSION}")
    except ImportError:
        report.record("pipeline", "PIPELINE_VERSION constant [RC-05]", "warn",
                      "Not found — audit trail may be incomplete")

    # Check for MAX_WORKERS constant  [RC-01]
    try:
        from src.pipeline import MAX_WORKERS
        cpu = os.cpu_count() or 2
        expected_max = max(1, cpu - 1)
        if MAX_WORKERS <= expected_max:
            report.record("pipeline", "ThreadPoolExecutor worker cap [RC-01]", "pass",
                          f"MAX_WORKERS={MAX_WORKERS}, CPUs={cpu}")
        else:
            report.record("pipeline", "ThreadPoolExecutor worker cap [RC-01]", "fail",
                          f"MAX_WORKERS={MAX_WORKERS} > CPU-1={expected_max}")
    except ImportError:
        report.record("pipeline", "MAX_WORKERS constant [RC-01]", "warn", "Not found in pipeline.py")

    # Check for SIFTCache class  [RC-02]
    try:
        from src.pipeline import SIFTCache
        report.record("pipeline", "SIFTCache class [RC-02]", "pass", "SHA-256 keyed cache available")
    except ImportError:
        report.record("pipeline", "SIFTCache class [RC-02]", "warn", "Not found — SIFT cache may use filename keys")


# ---------------------------------------------------------------------------
# Layer 5 — JSON schema
# ---------------------------------------------------------------------------

def probe_schema():
    log.info("\n═══ Layer: JSON Schema ═══")

    if not SCHEMA_PATH.exists():
        report.record("schema", "json_output_schema.json exists", "warn",
                      f"{SCHEMA_PATH} not found")
        return
    report.record("schema", "json_output_schema.json exists", "pass")

    try:
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        report.record("schema", "Schema is valid JSON", "pass")
    except json.JSONDecodeError as exc:
        report.record("schema", "Schema is valid JSON", "fail", str(exc))
        return

    # vi_class enum check
    try:
        vi_enum = schema["properties"]["vi_class"]["enum"]
        expected = {"minor", "moderate", "severe", "critical"}
        actual = set(vi_enum)
        if actual == expected:
            report.record("schema", "vi_class enum lowercase", "pass", str(vi_enum))
        else:
            diff = expected.symmetric_difference(actual)
            report.record("schema", "vi_class enum lowercase", "warn",
                          f"Mismatch: {diff}")
    except KeyError:
        report.record("schema", "vi_class enum in schema", "warn", "Could not locate vi_class.enum")

    # pipeline_warnings array in schema
    try:
        if "pipeline_warnings" in schema.get("properties", {}):
            report.record("schema", "pipeline_warnings in schema", "pass")
        else:
            report.record("schema", "pipeline_warnings in schema", "warn",
                          "Not in schema — frontend warning banner may fail schema validation")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

LAYER_MAP = {
    "db":       probe_db,
    "api":      probe_api,
    "tiles":    probe_tiles,
    "pipeline": probe_pipeline,
    "schema":   probe_schema,
}


def main():
    global API_BASE
    parser = argparse.ArgumentParser(description="Cortex production debug probe")
    parser.add_argument("--layer", choices=list(LAYER_MAP.keys()),
                        help="Probe a single layer only (default: all)")
    parser.add_argument("--api-base", default=API_BASE,
                        help=f"API base URL (default: {API_BASE})")
    args = parser.parse_args()

    API_BASE = args.api_base

    log.info("╔══════════════════════════════════════╗")
    log.info("║   Cortex Production Debug Probe      ║")
    log.info("╚══════════════════════════════════════╝")

    if args.layer:
        LAYER_MAP[args.layer]()
    else:
        for fn in LAYER_MAP.values():
            fn()

    # Summary
    s = report.summary()
    log.info("\n═══ Summary ═══")
    log.info(f"  Total checks : {s['total']}")
    log.info(f"  Passed       : {s['passed']}")
    log.info(f"  Failed       : {s['failed']}")
    log.info(f"  Warnings     : {s['warned']}")

    if report.has_failures():
        log.info("\n  ❌ PROBE FAILED — fix failures above before deploying")
        sys.exit(1)
    else:
        log.info("\n  ✅ All critical checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
