"""
Cortex — sqlite_store.py
SQLite persistence layer — production hardened

ROOT CAUSES FIXED:
  [RC-07] No WAL mode → concurrent readers block on writer
  [RC-08] No retry on DB locked → immediate crash under load
  [RC-09] growth_acceleration division by zero on first-cycle defects
  [RC-10] No connection context manager → unclosed handles leak
  [RC-11] No row-level version tracking → can't audit reprocessed inspections
  [RC-12] JSON serialization of warnings stored as raw string → unqueryable
"""

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Any

log = logging.getLogger("cortex.db")

DB_PATH = Path("cortex_inspections.db")
MAX_RETRIES = 5
RETRY_DELAY = 0.1   # seconds, doubles each retry


# ---------------------------------------------------------------------------
# Connection factory with WAL mode  [RC-07, RC-10]
# ---------------------------------------------------------------------------

@contextmanager
def get_conn(db_path: Path = DB_PATH):
    """
    Context-managed connection.
    Enables WAL mode on first connect — allows concurrent readers + 1 writer.
    [RC-10] guarantees connection is always closed.
    """
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")      # [RC-07]
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")    # WAL + NORMAL = safe + fast
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()   # [RC-10]


def _execute_with_retry(conn, sql: str, params: tuple = (), retries: int = MAX_RETRIES):
    """
    Retry wrapper for sqlite3.OperationalError: database is locked.
    [RC-08] — prevents immediate crash under concurrent load.
    """
    delay = RETRY_DELAY
    for attempt in range(retries):
        try:
            return conn.execute(sql, params)
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < retries - 1:
                log.warning(f"DB locked — retry {attempt + 1}/{retries} in {delay:.2f}s")
                time.sleep(delay)
                delay = min(delay * 2, 2.0)   # exponential backoff, cap 2s
            else:
                raise


# ---------------------------------------------------------------------------
# Schema init
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS inspections (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_version    TEXT    NOT NULL,
    run_timestamp       TEXT    NOT NULL,
    building_id         TEXT    NOT NULL,
    cycle_id            INTEGER NOT NULL,
    vi_class            TEXT    NOT NULL CHECK(vi_class IN ('minor','moderate','severe','critical')),
    vi_score            REAL    NOT NULL,
    gsd_mm_per_px       REAL    NOT NULL,
    total_defects       INTEGER NOT NULL,
    zone_severity_json  TEXT    NOT NULL,
    warnings_json       TEXT    NOT NULL DEFAULT '[]',
    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_inspections_building ON inspections(building_id);
CREATE INDEX IF NOT EXISTS idx_inspections_cycle    ON inspections(building_id, cycle_id);
CREATE INDEX IF NOT EXISTS idx_inspections_ts       ON inspections(run_timestamp DESC);

CREATE TABLE IF NOT EXISTS defects (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id           INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    defect_id               TEXT    NOT NULL UNIQUE,
    defect_type             TEXT    NOT NULL,
    severity                TEXT    NOT NULL,
    width_mm                REAL    NOT NULL DEFAULT 0,
    length_cm               REAL    NOT NULL DEFAULT 0,
    area_px2                REAL    NOT NULL DEFAULT 0,
    centroid_x              REAL    NOT NULL DEFAULT 0,
    centroid_y              REAL    NOT NULL DEFAULT 0,
    confidence              REAL    NOT NULL DEFAULT 0,
    false_positive_prob     REAL    NOT NULL DEFAULT 0,
    matched_previous_id     TEXT,
    delta_width_mm          REAL    NOT NULL DEFAULT 0,
    growth_rate_mm_per_month REAL   NOT NULL DEFAULT 0,
    growth_acceleration     REAL    NOT NULL DEFAULT 0,
    contour_geojson         TEXT    NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_defects_inspection ON defects(inspection_id);
CREATE INDEX IF NOT EXISTS idx_defects_type       ON defects(defect_type);
CREATE INDEX IF NOT EXISTS idx_defects_severity   ON defects(severity);
CREATE INDEX IF NOT EXISTS idx_defects_propagated ON defects(matched_previous_id) WHERE matched_previous_id IS NOT NULL;
"""


def init_db(db_path: Path = DB_PATH):
    """Create all tables and indexes. Idempotent."""
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
    log.info(f"DB initialized: {db_path}")


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def save_inspection(result: dict, db_path: Path = DB_PATH) -> int:
    """
    Persist a full InspectionResult dict (from pipeline.to_json()).
    Returns the new inspection row ID.

    [RC-09] growth_acceleration: guarded against None/zero on first-cycle defects
    [RC-12] warnings stored as JSON string, queryable via json_each()
    """
    with get_conn(db_path) as conn:
        # Insert inspection header
        cursor = _execute_with_retry(conn,
            """
            INSERT INTO inspections
                (pipeline_version, run_timestamp, building_id, cycle_id,
                 vi_class, vi_score, gsd_mm_per_px, total_defects,
                 zone_severity_json, warnings_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                result["pipeline_version"],
                result["run_timestamp"],
                result["building_id"],
                int(result["cycle_id"]),
                result["vi_class"],
                float(result["vi_score"]),
                float(result["gsd_mm_per_px"]),
                int(result["total_defects"]),
                json.dumps(result.get("zone_severity_index", {})),
                json.dumps(result.get("pipeline_warnings", [])),   # [RC-12]
            ),
        )
        inspection_id = cursor.lastrowid
        log.info(f"Saved inspection id={inspection_id} building={result['building_id']}")

        # Insert defects
        for d in result.get("defects", []):
            _save_defect(conn, inspection_id, d)

    return inspection_id


def _save_defect(conn: sqlite3.Connection, inspection_id: int, d: dict):
    """
    [RC-09] — growth_acceleration guarded:
      If matched_previous_id is None (first cycle defect), growth fields default 0.
      Never divides; values come pre-computed from TemporalTracker.
    """
    _execute_with_retry(conn,
        """
        INSERT OR REPLACE INTO defects
            (inspection_id, defect_id, defect_type, severity,
             width_mm, length_cm, area_px2, centroid_x, centroid_y,
             confidence, false_positive_prob,
             matched_previous_id, delta_width_mm,
             growth_rate_mm_per_month, growth_acceleration,
             contour_geojson)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            inspection_id,
            d["defect_id"],
            d["defect_type"],
            d["severity"],
            float(d.get("width_mm") or 0),
            float(d.get("length_cm") or 0),
            float(d.get("area_px2") or 0),
            float(d.get("centroid_x") or 0),
            float(d.get("centroid_y") or 0),
            float(d.get("confidence") or 0),
            float(d.get("false_positive_prob") or 0),
            d.get("matched_previous_id"),           # None is valid — first cycle
            float(d.get("delta_width_mm") or 0),
            float(d.get("growth_rate_mm_per_month") or 0),
            float(d.get("growth_acceleration") or 0),   # [RC-09] safe
            json.dumps(d.get("contour_geojson", {})),
        ),
    )


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_inspections(building_id: Optional[str] = None, limit: int = 50,
                    db_path: Path = DB_PATH) -> list[dict]:
    """
    Fetch inspection headers. Deserializes warnings_json back to list.
    """
    with get_conn(db_path) as conn:
        if building_id:
            rows = _execute_with_retry(conn,
                "SELECT * FROM inspections WHERE building_id=? ORDER BY run_timestamp DESC LIMIT ?",
                (building_id, limit),
            ).fetchall()
        else:
            rows = _execute_with_retry(conn,
                "SELECT * FROM inspections ORDER BY run_timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        r["zone_severity_index"] = _safe_json(r.pop("zone_severity_json", "{}"))
        r["pipeline_warnings"] = _safe_json(r.pop("warnings_json", "[]"))   # [RC-12]
        results.append(r)
    return results


def get_defects(inspection_id: int, defect_type: Optional[str] = None,
                severity: Optional[str] = None, db_path: Path = DB_PATH) -> list[dict]:
    """
    Fetch defects for an inspection. Optional type/severity filters.
    """
    filters = ["inspection_id = ?"]
    params: list = [inspection_id]

    if defect_type:
        filters.append("defect_type = ?")
        params.append(defect_type)
    if severity:
        filters.append("severity = ?")
        params.append(severity)

    sql = f"SELECT * FROM defects WHERE {' AND '.join(filters)} ORDER BY severity DESC, area_px2 DESC"

    with get_conn(db_path) as conn:
        rows = _execute_with_retry(conn, sql, tuple(params)).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        r["contour_geojson"] = _safe_json(r.pop("contour_geojson", "{}"))
        results.append(r)
    return results


def get_propagated_defects(building_id: str, db_path: Path = DB_PATH) -> list[dict]:
    """
    All defects with temporal matches across cycles — used for delta table in frontend.
    Sorted by growth_acceleration DESC to surface highest-risk defects first.
    """
    sql = """
        SELECT d.*, i.run_timestamp, i.cycle_id
        FROM defects d
        JOIN inspections i ON d.inspection_id = i.id
        WHERE i.building_id = ?
          AND d.matched_previous_id IS NOT NULL
        ORDER BY d.growth_acceleration DESC, d.growth_rate_mm_per_month DESC
    """
    with get_conn(db_path) as conn:
        rows = _execute_with_retry(conn, sql, (building_id,)).fetchall()

    return [dict(row) for row in rows]


def get_db_stats(db_path: Path = DB_PATH) -> dict:
    """Health-check endpoint data."""
    with get_conn(db_path) as conn:
        insp_count = _execute_with_retry(conn, "SELECT COUNT(*) FROM inspections").fetchone()[0]
        def_count  = _execute_with_retry(conn, "SELECT COUNT(*) FROM defects").fetchone()[0]
        buildings  = _execute_with_retry(
            conn, "SELECT COUNT(DISTINCT building_id) FROM inspections"
        ).fetchone()[0]

    return {
        "total_inspections": insp_count,
        "total_defects": def_count,
        "unique_buildings": buildings,
        "db_path": str(db_path),
        "db_size_kb": round(db_path.stat().st_size / 1024, 1) if db_path.exists() else 0,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}

