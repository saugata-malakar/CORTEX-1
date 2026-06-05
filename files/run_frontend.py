"""
Cortex — run_frontend.py
REST API server launcher — production hardened

ROOT CAUSES FIXED:
  [RC-13] No --port arg → always binds 8000, crashes if occupied
  [RC-14] No socket pre-check → silent bind failure, browser opens to blank
  [RC-15] No tile asset pre-validation → browser shows blank map, no error
  [RC-16] API returns raw exception string → exposes internals to client
  [RC-17] No CORS headers → frontend JS fetch blocked in modern browsers
  [RC-18] No /api/health endpoint → load balancer / uptime monitor has no probe
"""

import argparse
import json
import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sqlite_store import (
    DB_PATH,
    get_defects,
    get_db_stats,
    get_inspections,
    get_propagated_defects,
    init_db,
)

log = logging.getLogger("cortex.server")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

FRONTEND_DIR = Path(__file__).parent / "frontend"
TILE_DIR = FRONTEND_DIR / "tiles"
REQUIRED_TILE_ZOOM_LEVELS = [0, 1, 2]   # minimum zoom levels expected


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def check_port_available(port: int) -> bool:
    """[RC-13, RC-14] — check socket before binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) != 0


def validate_tile_assets() -> list[str]:
    """
    [RC-15] — verify tile pyramid exists before starting server.
    Returns list of validation errors (empty = all good).
    """
    errors = []

    if not TILE_DIR.exists():
        errors.append(f"Tile directory missing: {TILE_DIR}")
        return errors

    for zoom in REQUIRED_TILE_ZOOM_LEVELS:
        zoom_dir = TILE_DIR / str(zoom)
        if not zoom_dir.exists():
            errors.append(f"Missing tile zoom level: {zoom_dir}")
            continue
        tile_files = list(zoom_dir.rglob("*.png")) + list(zoom_dir.rglob("*.jpg"))
        if not tile_files:
            errors.append(f"Zoom level {zoom} has no tile files in {zoom_dir}")

    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        errors.append(f"index.html missing: {index}")

    for js_file in ["app.js", "style.css"]:
        p = FRONTEND_DIR / js_file
        if not p.exists():
            errors.append(f"Required frontend file missing: {p}")

    return errors


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class CortexRequestHandler(BaseHTTPRequestHandler):

    # Suppress default request log — we use structured logging instead
    def log_message(self, fmt, *args):
        log.info(f"{self.client_address[0]} {fmt % args}")

    def log_error(self, fmt, *args):
        log.error(f"{self.client_address[0]} {fmt % args}")

    def _send_json(self, data: dict | list, status: int = 200):
        """[RC-17] — always include CORS headers."""
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")     # [RC-17]
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, code: str, message: str):
        """[RC-16] — structured error, never raw exception strings."""
        self._send_json({"error": {"code": code, "message": message}}, status)

    def do_OPTIONS(self):
        """Preflight for CORS."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        try:
            # ----------------------------------------------------------------
            # API routes
            # ----------------------------------------------------------------
            if path == "/api/health":
                self._handle_health()

            elif path == "/api/inspections":
                self._handle_inspections(qs)

            elif path == "/api/defects":
                self._handle_defects(qs)

            elif path == "/api/propagated":
                self._handle_propagated(qs)

            elif path == "/api/db-stats":
                self._handle_db_stats()

            # ----------------------------------------------------------------
            # Static file serving
            # ----------------------------------------------------------------
            else:
                self._serve_static(path)

        except Exception as exc:
            log.error(f"Unhandled handler error: {exc}", exc_info=True)
            # [RC-16] — never leak traceback to client
            self._send_error_json(500, "INTERNAL_ERROR", "An unexpected error occurred.")

    # ----------------------------------------------------------------
    # API handlers
    # ----------------------------------------------------------------

    def _handle_health(self):
        """[RC-18] — liveness probe endpoint."""
        try:
            stats = get_db_stats()
            self._send_json({
                "status": "ok",
                "pipeline_version": os.getenv("CORTEX_VERSION", "1.4.0"),
                "db": stats,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        except Exception as exc:
            log.error(f"Health check DB error: {exc}")
            self._send_json({"status": "degraded", "error": "db_unreachable"}, 503)

    def _handle_inspections(self, qs: dict):
        building_id = qs.get("building_id", [None])[0]
        try:
            limit = int(qs.get("limit", ["50"])[0])
            limit = min(limit, 200)   # cap to prevent runaway queries
        except ValueError:
            limit = 50

        rows = get_inspections(building_id=building_id, limit=limit)
        self._send_json({"inspections": rows, "count": len(rows)})

    def _handle_defects(self, qs: dict):
        raw_id = qs.get("inspection_id", [None])[0]
        if not raw_id:
            self._send_error_json(400, "MISSING_PARAM", "inspection_id is required")
            return
        try:
            inspection_id = int(raw_id)
        except ValueError:
            self._send_error_json(400, "INVALID_PARAM", "inspection_id must be an integer")
            return

        defect_type = qs.get("type", [None])[0]
        severity = qs.get("severity", [None])[0]
        rows = get_defects(inspection_id, defect_type=defect_type, severity=severity)
        self._send_json({"defects": rows, "count": len(rows)})

    def _handle_propagated(self, qs: dict):
        building_id = qs.get("building_id", [None])[0]
        if not building_id:
            self._send_error_json(400, "MISSING_PARAM", "building_id is required")
            return
        rows = get_propagated_defects(building_id)
        self._send_json({"propagated_defects": rows, "count": len(rows)})

    def _handle_db_stats(self):
        self._send_json(get_db_stats())

    # ----------------------------------------------------------------
    # Static file serving
    # ----------------------------------------------------------------

    MIME = {
        ".html": "text/html",
        ".css":  "text/css",
        ".js":   "application/javascript",
        ".json": "application/json",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".svg":  "image/svg+xml",
        ".ico":  "image/x-icon",
    }

    def _serve_static(self, path: str):
        if path == "/" or path == "":
            path = "/index.html"

        # Security: block path traversal
        try:
            file_path = (FRONTEND_DIR / path.lstrip("/")).resolve()
            file_path.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            self._send_error_json(403, "FORBIDDEN", "Path traversal not allowed")
            return

        if not file_path.exists() or not file_path.is_file():
            self._send_error_json(404, "NOT_FOUND", f"Resource not found: {path}")
            return

        suffix = file_path.suffix.lower()
        mime = self.MIME.get(suffix, "application/octet-stream")
        content = file_path.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)


# ---------------------------------------------------------------------------
# Server launcher
# ---------------------------------------------------------------------------

def find_free_port(preferred: int) -> int:
    """[RC-13] — if preferred port is occupied, find next free port."""
    port = preferred
    while port < preferred + 20:
        if check_port_available(port):
            return port
        log.warning(f"Port {port} in use, trying {port + 1}")
        port += 1
    raise RuntimeError(f"No free port found in range {preferred}–{port}")


def main():
    parser = argparse.ArgumentParser(description="Cortex frontend server")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Skip auto-open browser")
    parser.add_argument("--skip-tile-check", action="store_true", help="Skip tile validation")
    args = parser.parse_args()

    # 1. Tile asset pre-validation  [RC-15]
    if not args.skip_tile_check:
        tile_errors = validate_tile_assets()
        if tile_errors:
            log.error("PREFLIGHT FAILED — tile assets invalid:")
            for err in tile_errors:
                log.error(f"  ✗ {err}")
            log.error("Fix tile assets or run with --skip-tile-check to bypass.")
            sys.exit(1)
        else:
            log.info("✓ Tile assets validated")

    # 2. DB init
    init_db(DB_PATH)
    log.info(f"✓ Database ready: {DB_PATH}")

    # 3. Port selection  [RC-13, RC-14]
    port = find_free_port(args.port)
    if port != args.port:
        log.warning(f"Preferred port {args.port} was occupied — using {port}")

    # 4. Start server
    server = HTTPServer(("0.0.0.0", port), CortexRequestHandler)
    url = f"http://localhost:{port}"
    log.info(f"✓ Cortex server running at {url}")
    log.info("  Endpoints:")
    log.info(f"  GET {url}/api/health")
    log.info(f"  GET {url}/api/inspections?building_id=<id>&limit=50")
    log.info(f"  GET {url}/api/defects?inspection_id=<id>&type=crack&severity=severe")
    log.info(f"  GET {url}/api/propagated?building_id=<id>")
    log.info(f"  GET {url}/api/db-stats")
    log.info("Press Ctrl+C to stop.")

    # 5. Open browser after 1s delay  [RC-14] — server is definitely up by then
    if not args.no_browser:
        def open_browser():
            time.sleep(1.0)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    # 6. Serve
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
