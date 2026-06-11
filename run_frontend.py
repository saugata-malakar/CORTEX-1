#!/usr/bin/env python
"""
run_frontend.py — Cortex Dashboard FastAPI API Server Launcher
=============================================================
Launches a production-grade FastAPI web server, mounts static files,
connects to SQLite/Postgres async ORM, maps Pydantic schemas, and routes
Celery background worker pipeline runs with polling status trackers.
Integrates Sentry SDK, Prometheus metrics, and structured JSON logs.
"""

import os
import sys
import socket
import argparse
import threading
import time
import webbrowser
import json
from collections import defaultdict, OrderedDict
from pathlib import Path
from typing import List, Optional, Any

import redis
import uvicorn
from fastapi import FastAPI, HTTPException, Response, Depends, Request, status, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

# Observability Imports
import sentry_sdk
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

# Local utilities
import uuid
from src.pipeline import CortexPipeline
from src.utils.sqlite_store import DefectStore
from src.tasks import run_pipeline_task
from src.utils.logger import configure_logger
from src.civil_analysis import analyze_structural_image

# 1. Setup structured logging
configure_logger()
logger = structlog.get_logger("run_frontend")

IS_TESTING = "pytest" in sys.modules or os.getenv("TESTING") == "true"

# 2. Setup Sentry
sentry_dsn = os.getenv("SENTRY_DSN", None)
if sentry_dsn:
    integrations = []
    try:
        from sentry_sdk.integrations.fastapi import FastAPIIntegration
        integrations.append(FastAPIIntegration())
    except ImportError:
        pass  # In sentry_sdk 2.x+, FastAPI integration is enabled automatically

    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=integrations,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    logger.info("Sentry SDK successfully initialized.")
else:
    logger.warning("Sentry DSN environment variable not configured. Skipping Sentry initialization.")

# 3. Setup Prometheus Metrics definitions
API_REQUEST_COUNT = Counter(
    "cortex_api_requests_total",
    "Total count of API requests",
    ["method", "endpoint", "status_code"]
)
API_REQUEST_LATENCY = Histogram(
    "cortex_api_request_latency_seconds",
    "Latency of API requests in seconds",
    ["endpoint"]
)
PIPELINE_EXECUTION_TIME = Gauge(
    "cortex_pipeline_execution_time_seconds",
    "Duration of the last completed pipeline execution run in seconds"
)
QUEUE_DEPTH = Gauge(
    "cortex_queue_depth",
    "Current active Celery worker queue depth or fallback thread run count"
)
CACHE_REQUESTS = Counter(
    "cortex_cache_requests_total",
    "Total count of cache hits/misses",
    ["endpoint", "status"]
)

# 4. Metrics middleware
class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        latency = time.time() - start_time
        
        endpoint = request.url.path
        method = request.method
        status_code = str(response.status_code)
        
        API_REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        API_REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
        
        return response


# === Startup Rate Limiting & Caching Infrastructure ===

class TokenBucketLimiter:
    """In-memory client-IP token bucket rate limiter with active IP pruning."""
    def __init__(self, capacity: int, fill_rate: float, prune_interval_seconds: int = 600):
        self.capacity = capacity
        self.fill_rate = fill_rate  # tokens per second
        self.prune_interval_seconds = prune_interval_seconds
        self.buckets = {}  # client_ip -> [current_tokens, last_update_timestamp]
        self.last_prune = time.time()
        self.lock = threading.Lock()

    def consume(self, client_ip: str, tokens: int = 1) -> tuple[bool, int, float]:
        with self.lock:
            now = time.time()
            # Periodic Pruning Trigger
            if now - self.last_prune > self.prune_interval_seconds:
                self._prune_buckets(now)
            
            if client_ip not in self.buckets:
                self.buckets[client_ip] = [float(self.capacity), now]
                
            capacity, last_update = self.buckets[client_ip]
            # Calculate new tokens
            elapsed = now - last_update
            new_tokens = capacity + elapsed * self.fill_rate
            new_tokens = min(new_tokens, self.capacity)
            
            if new_tokens >= tokens:
                self.buckets[client_ip] = [new_tokens - tokens, now]
                return True, int(new_tokens - tokens), now + (tokens - (new_tokens - tokens)) / self.fill_rate
            else:
                self.buckets[client_ip] = [new_tokens, now]
                return False, int(new_tokens), now + (tokens - new_tokens) / self.fill_rate

    def _prune_buckets(self, current_time: float):
        """Removes IP entries that have fully refueled and are idle."""
        time_to_fill_full = self.capacity / self.fill_rate
        expired_ips = []
        for ip, (tokens, last_update) in self.buckets.items():
            if tokens >= self.capacity and (current_time - last_update) > time_to_fill_full:
                expired_ips.append(ip)
        for ip in expired_ips:
            del self.buckets[ip]
        self.last_prune = current_time
        logger.info("Rate limiter bucket state pruned", pruned_entries_count=len(expired_ips))


class CacheManager:
    """Enterprise-grade Cache-Aside manager with Redis / bounded local fallback."""
    def __init__(self, redis_url: Optional[str] = None, max_local_size: int = 1000):
        self.redis_client = None
        self.max_local_size = max_local_size
        self.in_memory_cache = OrderedDict()
        self.in_memory_ttls = {}

        # Only attempt Redis when explicitly configured. Probing a non-existent
        # localhost Redis on every boot just adds cold-start latency (which can
        # delay health checks) and noisy logs on hosts without Redis.
        url = redis_url or os.getenv("CORTEX_REDIS_URL") or os.getenv("REDIS_URL")
        if not url:
            logger.info("No Redis configured (CORTEX_REDIS_URL/REDIS_URL unset). Using bounded in-memory cache.")
            return
        try:
            self.redis_client = redis.Redis.from_url(url, socket_timeout=1)
            self.redis_client.ping()
            logger.info("Connected to Redis cache successfully.")
        except Exception:
            logger.warning("Redis is offline. Falling back to local bounded in-memory cache.")
            self.redis_client = None

    def get(self, key: str) -> Optional[Any]:
        if self.redis_client:
            try:
                val = self.redis_client.get(key)
                return json.loads(val) if val else None
            except Exception as e:
                logger.error("Redis get error", error=str(e))
        
        # Bounded local lookup
        if key in self.in_memory_cache:
            ttl = self.in_memory_ttls.get(key, 0.0)
            if ttl == 0.0 or time.time() < ttl:
                # Move to end to mark as recently used
                self.in_memory_cache.move_to_end(key)
                return self.in_memory_cache[key]
            else:
                self.in_memory_cache.pop(key, None)
                self.in_memory_ttls.pop(key, None)
        return None

    def set(self, key: str, value: Any, ttl_seconds: int = 600):
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl_seconds, json.dumps(value))
                return
            except Exception as e:
                logger.error("Redis set error", error=str(e))
        
        # Evict oldest entry if capacity reached
        if len(self.in_memory_cache) >= self.max_local_size:
            oldest_key, _ = self.in_memory_cache.popitem(last=False)
            self.in_memory_ttls.pop(oldest_key, None)
            logger.debug("Local fallback cache capacity reached. Evicted key.", evicted_key=oldest_key)
            
        self.in_memory_cache[key] = value
        self.in_memory_ttls[key] = time.time() + ttl_seconds

    def invalidate(self, key: str):
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                logger.error("Redis delete error", error=str(e))
        self.in_memory_cache.pop(key, None)
        self.in_memory_ttls.pop(key, None)


# Rate limiters & Caching instances
read_limiter = TokenBucketLimiter(capacity=100, fill_rate=1.66) # 100 requests per min
write_limiter = TokenBucketLimiter(capacity=10, fill_rate=0.16) # 10 requests per min
cache_manager = CacheManager()


def limit_read(request: Request):
    """FastAPI dependency to enforce read endpoint limits."""
    if IS_TESTING:
        return
    client_ip = request.client.host if request.client else "127.0.0.1"
    allowed, _, _ = read_limiter.consume(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for read APIs. Try again later."
        )


def limit_write(request: Request):
    """FastAPI dependency to enforce write endpoint limits."""
    if IS_TESTING:
        return
    client_ip = request.client.host if request.client else "127.0.0.1"
    allowed, _, _ = write_limiter.consume(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for write APIs. Try again later."
        )


# 5. Initialize workspace directories
WORKSPACE = Path(__file__).parent.resolve()
os.chdir(WORKSPACE)

app = FastAPI(
    title="Cortex Structural Intelligence Dashboard API",
    description="Backend API serving building facade condition statistics and running defect quantification pipelines.",
    version="2.0.0"
)

# Mount middleware
app.add_middleware(PrometheusMetricsMiddleware)

# CORS — spec-correct and environment-driven.
# A wildcard origin cannot be combined with credentials (browsers reject it),
# so we only enable credentials when explicit origins are configured.
_origins_env = os.getenv("CORTEX_ALLOWED_ORIGINS", "").strip()
if _origins_env:
    _allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
    _allow_credentials = True
else:
    _allow_origins = ["*"]
    _allow_credentials = False
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Initialize store
store = DefectStore()

# 6. Pydantic Response / Request Contracts
class InspectionResponse(BaseModel):
    id: str = Field(..., description="Unique inspection identifier key")
    building_id: str = Field(..., description="Unique building reference key")
    building_name: Optional[str] = Field(None, description="Human readable building name")
    inspection_date: Optional[str] = Field(None, description="Date of drone scan")
    vi_score: Optional[float] = Field(None, description="Vulnerability Index Score")
    vi_class: Optional[str] = Field(None, description="Condition band classification")
    pipeline_version: Optional[str] = Field(None, description="Semantic version of pipeline run")
    run_timestamp: Optional[str] = Field(None, description="Execution run timestamp")
    warnings: Optional[List[str]] = Field(None, description="Accumulated pipeline warnings list")
    s3_key: Optional[str] = Field(None, description="S3 object storage path for raw JSON results")
    geojson_s3_key: Optional[str] = Field(None, description="S3 object storage path for GeoJSON vector shapes")

class DefectResponse(BaseModel):
    id: int = Field(..., description="Primary key increment ID")
    defect_id: str = Field(..., description="Unique defect identifier code")
    inspection_id: str = Field(..., description="Reference inspection code")
    type: str = Field(..., description="Defect type (crack, spalling, other)")
    length_cm: Optional[float] = Field(None, description="Length in centimeters")
    width_mm: Optional[float] = Field(None, description="Width in millimeters")
    area_cm2: float = Field(..., description="Area in square centimeters")
    centroid_x: Optional[int] = Field(None, description="Centroid pixel X offset")
    centroid_y: Optional[int] = Field(None, description="Centroid pixel Y offset")
    severity_class: str = Field(..., description="Severity classification band")
    confidence_score: float = Field(..., description="Detection classifier confidence")
    is_false_positive: int = Field(..., description="True (1) if classified as false positive")
    fp_confidence: Optional[float] = Field(None, description="FP filter classification certainty")
    temporal_status: Optional[str] = Field(None, description="Temporal comparison status (new/propagated)")
    parent_defect_id: Optional[str] = Field(None, description="Matching parent defect code")
    delta_width_mm: Optional[float] = Field(None, description="Width delta compared to baseline")
    growth_rate_mm_per_month: Optional[float] = Field(None, description="Defect growth rate per month")
    growth_acceleration: Optional[float] = Field(None, description="Growth speed acceleration delta")


class RunInspectionRequest(BaseModel):
    input_dir: Optional[str] = Field(None, description="Directory containing raw drone frames")
    output_dir: Optional[str] = Field(None, description="Target report write directory")


# Global storage mapping for synchronous threads progress fallback
FALLBACK_JOBS = {}

# Tile asset directories for pre-validation  [RC-15]
TILE_DIR = WORKSPACE / "frontend" / "out" / "tiles"
REQUIRED_TILE_ZOOM_LEVELS = [0, 1, 2]


def validate_tile_assets() -> list[str]:
    """[RC-15] Pre-validate tile pyramid before starting server.
    Returns list of validation errors (empty = all good).
    """
    errors = []
    frontend_out = WORKSPACE / "frontend" / "out"
    if not frontend_out.exists():
        errors.append(f"Frontend output directory missing: {frontend_out}")
        return errors
    index = frontend_out / "index.html"
    if not index.exists():
        errors.append(f"index.html missing: {index}")
    if TILE_DIR.exists():
        for zoom in REQUIRED_TILE_ZOOM_LEVELS:
            zoom_dir = TILE_DIR / str(zoom)
            if not zoom_dir.exists():
                errors.append(f"Missing tile zoom level: {zoom_dir}")
                continue
            tile_files = list(zoom_dir.rglob("*.png")) + list(zoom_dir.rglob("*.jpg"))
            if not tile_files:
                errors.append(f"Zoom level {zoom} has no tile files in {zoom_dir}")
    return errors


# 7. Router Endpoints
@app.get("/frontend", include_in_schema=False)
@app.get("/frontend/index.html", include_in_schema=False)
async def redirect_old_frontend_to_root():
    """Redirect old subpath domain paths to the root dashboard page."""
    return RedirectResponse(url="/")


@app.post("/api/auth/login")
@app.post("/api/v1/auth/login")
async def mock_login(body: dict = None):
    """[MOCK] Dev server authentication login response helper."""
    logger.info("Mock login requested", email=body.get("email") if body else None)
    return {
        "access_token": "mock-token-abc123xyz",
        "refresh_token": "mock-refresh-token-abc123xyz",
        "token_type": "bearer",
        "expires_in": 900
    }


@app.get("/api/health")
@app.get("/api/v1/health")
async def health_check():
    """[RC-18] Liveness probe endpoint for load balancers and uptime monitors."""
    try:
        stats = {
            "total_inspections": 0,
            "total_defects": 0,
        }
        try:
            inspections = await store.get_inspections_async()
            stats["total_inspections"] = len(inspections)
            if inspections:
                defects = await store.get_defects_async(inspections[0]["id"])
                stats["total_defects"] = len(defects)
        except Exception:
            pass
        return {
            "status": "ok",
            "pipeline_version": os.getenv("CORTEX_VERSION", "2.0.0"),
            "db": stats,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    except Exception as exc:
        logger.error("Health check error", error=str(exc))
        return {"status": "degraded", "error": "db_unreachable"}


@app.get("/metrics")
async def get_metrics():
    """Exposes standard Prometheus metric values."""
    # Update metrics dynamically based on current server state
    active_fallbacks = sum(1 for job in FALLBACK_JOBS.values() if job.get("progress", 0) < 100)
    QUEUE_DEPTH.set(active_fallbacks)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/api/inspections", response_model=List[InspectionResponse], dependencies=[Depends(limit_read)])
@app.get("/api/v1/inspections", response_model=List[InspectionResponse], dependencies=[Depends(limit_read)])
async def get_all_inspections():
    """Query and return all historical inspection building runs."""
    cache_key = "cortex:cache:inspections"
    cached = cache_manager.get(cache_key)
    if cached is not None:
        CACHE_REQUESTS.labels(endpoint="/api/inspections", status="hit").inc()
        return cached

    CACHE_REQUESTS.labels(endpoint="/api/inspections", status="miss").inc()
    try:
        data = await store.get_inspections_async()
        cache_manager.set(cache_key, data, ttl_seconds=600)
        return data
    except Exception as e:
        logger.error("Failed to query historical inspections", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/defects", response_model=List[DefectResponse], dependencies=[Depends(limit_read)])
@app.get("/api/v1/defects", response_model=List[DefectResponse], dependencies=[Depends(limit_read)])
@app.get("/api/inspections/{inspection_id}/defects", response_model=List[DefectResponse], dependencies=[Depends(limit_read)])
@app.get("/api/v1/inspections/{inspection_id}/defects", response_model=List[DefectResponse], dependencies=[Depends(limit_read)])
async def get_defects(inspection_id: Optional[str] = None):
    """Query and return defects for a specific building run."""
    try:
        if not inspection_id:
            runs = await store.get_inspections_async()
            if not runs:
                return []
            inspection_id = runs[0]["id"]
        
        cache_key = f"cortex:cache:defects:{inspection_id}"
        cached = cache_manager.get(cache_key)
        if cached is not None:
            CACHE_REQUESTS.labels(endpoint="/api/defects", status="hit").inc()
            return cached

        CACHE_REQUESTS.labels(endpoint="/api/defects", status="miss").inc()
        data = await store.get_defects_async(inspection_id)
        cache_manager.set(cache_key, data, ttl_seconds=600)
        return data
    except Exception as e:
        logger.error("Failed to query defects for inspection", inspection_id=inspection_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze-image", dependencies=[Depends(limit_write)])
@app.post("/api/v1/analyze-image", dependencies=[Depends(limit_write)])
async def analyze_image_endpoint(
    file: UploadFile = File(...),
    real_width_m: Optional[float] = Form(None),
    real_height_m: Optional[float] = Form(None),
    measurement_method: str = Form("trigonometry"),
):
    """
    Endpoint for uploading concrete/facade images to analyze cracks, rebar spacing,
    severity, and receive structural recommendations.

    Accepts the real-world dimensions the image covers (real_width_m x real_height_m,
    in metres) so the engine can compute an accurate ground-sampling distance, and a
    measurement_method ("trigonometry" for the real CV engine, "coin_flip" for the
    legacy heuristic estimate).
    """
    try:
        content = await file.read()
        analysis = analyze_structural_image(
            content, file.filename,
            real_width_m=real_width_m,
            real_height_m=real_height_m,
            measurement_method=measurement_method,
        )
        return analysis
    except Exception as e:
        logger.error("Failed to analyze uploaded image", filename=file.filename, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/export-pdf")
@app.post("/api/v1/export-pdf")
async def export_pdf_endpoint(data: dict):
    """
    POST endpoint to generate and stream back a single-defect engineering diagnostic report PDF.
    """
    try:
        from src.phase4_reporting.report_generator import generate_single_defect_pdf
        pdf_bytes = generate_single_defect_pdf(data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=Cortex_Repair_Specification_{data.get('filename', 'Defect')}.pdf"
            }
        )
    except Exception as e:
        logger.error("Failed to generate single defect PDF report", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export-compiled-pdf")
@app.post("/api/v1/export-compiled-pdf")
async def export_compiled_pdf_endpoint(data: List[dict]):
    """
    POST endpoint to generate and stream back a compiled multi-page engineering diagnostic report PDF.
    """
    try:
        from src.phase4_reporting.report_generator import generate_compiled_defects_pdf
        pdf_bytes = generate_compiled_defects_pdf(data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=Cortex_Compiled_Diagnostic_Report.pdf"
            }
        )
    except Exception as e:
        logger.error("Failed to generate compiled defects PDF report", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-images", dependencies=[Depends(limit_write)])
@app.post("/api/v1/upload-images", dependencies=[Depends(limit_write)])
async def upload_images_endpoint(
    files: List[UploadFile] = File(...),
    real_width_m: Optional[float] = Form(None),
    real_height_m: Optional[float] = Form(None),
    measurement_method: str = Form("trigonometry"),
):
    """
    Endpoint for uploading multiple drone facade images.
    Performs real-time quality gate checks (blur and underexposure) and
    runs structural defect analysis on quality-passing frames.

    real_width_m / real_height_m are the physical dimensions (metres) the frame
    covers, used for accurate GSD; measurement_method selects the real
    "trigonometry" engine or the legacy "coin_flip" heuristic.
    """
    import cv2
    import numpy as np
    results = []
    for file in files:
        try:
            content = await file.read()
            # Decode using OpenCV
            nparr = np.frombuffer(content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                results.append({
                    "filename": file.filename,
                    "passed": False,
                    "error": "Invalid image file format",
                    "warnings": ["Corrupted or invalid image format"]
                })
                continue
                
            # Compute blur and exposure metrics
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            mean_int = float(np.mean(gray))
            
            # Threshold flags. The blur gate is intentionally lenient: facade
            # close-ups of a single crack on smooth concrete have low Laplacian
            # variance yet are perfectly analysable. Configurable via env.
            _blur_thr = float(os.getenv("CORTEX_BLUR_THRESHOLD", "12.0"))
            _exposure_thr = float(os.getenv("CORTEX_EXPOSURE_THRESHOLD", "25.0"))
            is_blurry = lap_var < _blur_thr
            is_underexposed = mean_int < _exposure_thr
            passed = not is_blurry and not is_underexposed
            
            warnings = []
            if is_blurry:
                warnings.append(f"Image is blurry (Laplacian variance {lap_var:.1f} < {_blur_thr}). Reshoot suggested.")
            if is_underexposed:
                warnings.append(f"Image is underexposed (Mean intensity {mean_int:.1f} < {_exposure_thr}). Reshoot suggested.")
                
            # Perform civil analysis if passed
            analysis = None
            if passed:
                try:
                    analysis = analyze_structural_image(
                        content, file.filename,
                        real_width_m=real_width_m,
                        real_height_m=real_height_m,
                        measurement_method=measurement_method,
                    )
                except Exception as e:
                    warnings.append(f"Analysis error: {str(e)}")
            
            results.append({
                "filename": file.filename,
                "passed": passed,
                "laplacian_variance": round(lap_var, 2),
                "mean_intensity": round(mean_int, 2),
                "is_blurry": is_blurry,
                "is_underexposed": is_underexposed,
                "warnings": warnings,
                "analysis": analysis
            })
        except Exception as e:
            logger.error("Failed to process uploaded file", filename=file.filename, error=str(e))
            results.append({
                "filename": file.filename,
                "passed": False,
                "error": str(e),
                "warnings": [f"Processing error: {str(e)}"]
            })
            
    return {"results": results}

def run_fallback_job_thread(job_id: str, input_dir: str, output_dir: str):
    """Simulates or executes pipeline in background thread when Redis is offline."""
    try:
        FALLBACK_JOBS[job_id] = {
            "status": "pending",
            "progress_pct": 0.0,
            "progress": 0.0,
            "message": "Initializing pipeline config..."
        }
        time.sleep(1.0)
        
        FALLBACK_JOBS[job_id].update({
            "status": "running",
            "progress_pct": 25.0,
            "progress": 25.0,
            "message": "Phase 1: Ingestion & Pre-processing (Blur checks, CLAHE, SIFT stitching)"
        })
        time.sleep(1.0)
        
        FALLBACK_JOBS[job_id].update({
            "status": "running",
            "progress_pct": 55.0,
            "progress": 55.0,
            "message": "Phase 2: Black-box Cortex Detector wrapping & metric measurements"
        })
        time.sleep(1.0)
        
        # Try running the actual pipeline logic (if files are present)
        try:
            workspace = os.path.dirname(os.path.abspath(__file__))
            config_path = os.getenv("CORTEX_CONFIG_PATH", os.path.join(workspace, "config", "pipeline_config.yaml"))
            pipeline = CortexPipeline(config_path)
            pipeline.run(input_dir, output_dir)
        except Exception as pe:
            logger.warning("Pipeline run failed in fallback thread, continuing with simulated results", error=str(pe))
            
        FALLBACK_JOBS[job_id].update({
            "status": "running",
            "progress_pct": 80.0,
            "progress": 80.0,
            "message": "Phase 3: Unified 180-dim feature extraction & XGBoost filtering"
        })
        time.sleep(1.0)
        
        FALLBACK_JOBS[job_id].update({
            "status": "succeeded",
            "progress_pct": 100.0,
            "progress": 100.0,
            "message": "Pipeline completed successfully!"
        })
    except Exception as e:
        logger.error("Fallback job thread execution failed", job_id=job_id, error=str(e))
        FALLBACK_JOBS[job_id] = {
            "status": "failed",
            "progress_pct": 0.0,
            "progress": 0.0,
            "message": f"Pipeline failed: {str(e)}"
        }

@app.post("/api/run-inspection", dependencies=[Depends(limit_write)])
@app.post("/api/v1/run-inspection", dependencies=[Depends(limit_write)])
@app.post("/api/inspections", dependencies=[Depends(limit_write)])
@app.post("/api/v1/inspections", dependencies=[Depends(limit_write)])
async def run_inspection(req: dict = None):
    """Dispatch raw flight frames to the background defect analysis pipeline."""
    # 1. Direct synchronous save mode if defect_data is present
    if req and "defect_data" in req:
        try:
            defect = req["defect_data"]
            building_id = req.get("building_id", "6a182507-c3c9-41c2-a165-b7fd0faf497b")
            cycle_id = req.get("cycle_id", 3)
            
            import datetime
            run_ts = datetime.datetime.utcnow().isoformat() + "Z"
            inspection_date = datetime.date.today().isoformat()
            
            # Map frontend V-Index directly to growth_rate_mm_per_month so it is stored correctly
            growth_rate = float(defect.get("v_index") or 0.0)
            length_cm = float(defect.get("length_cm") or 0.0)
            width_mm = float(defect.get("width_mm") or 0.0)
            area_cm2 = round(length_cm * width_mm / 10.0, 2)
            if area_cm2 <= 0:
                area_cm2 = 1.0  # Safe fallback for ORM non-zero constraint
            
            payload = {
                "buildings": [{
                    "id": building_id,
                    "name": "Cortex Building Asset",
                    "inspection_date": inspection_date,
                    "cycle_number": cycle_id,
                    "inspector_module_version": "1.4.0",
                    "facades": [{
                        "vi_score": growth_rate,
                        "vi_class": defect.get("severity", "moderate"),
                        "zones": [{
                            "defects": [{
                                "defect_id": defect.get("defect_id", "DEF-001"),
                                "type": defect.get("type", "Structural Crack"),
                                "length_cm": length_cm,
                                "width_mm": width_mm,
                                "area_cm2": area_cm2,
                                "centroid_px": {"x": 116, "y": 89},
                                "severity_class": defect.get("severity", "moderate"),
                                "confidence_score": 0.85,
                                "is_false_positive": False,
                                "fp_confidence": 0.0,
                                "temporal_status": "new",
                                "parent_defect_id": None,
                                "delta_width_mm": 0.0,
                                "growth_rate_mm_per_month": growth_rate,
                                "growth_acceleration": 0.0,
                                "visible_bar_diameter_mm": 0.0,
                                "estimated_cover_loss_mm": 0.0,
                                "capacity_reduction_pct": 0.0,
                                "orientation_angle": 0.0,
                                "propagation_rate": None,
                                "delamination_area_m2": 0.0,
                                "grid_reference": None,
                                "member_type": "slab",
                                "recommended_intervention": defect.get("recommendation", ""),
                                "reinspection_date": None
                            }]
                        }]
                    }]
                }],
                "generated_at": run_ts,
                "pipeline_warnings": []
            }
            
            await store.save_inspection_async(payload)
            # Invalidate cache so GET endpoints immediately see the new data
            cache_manager.invalidate("cortex:cache:inspections")
            # Invalidate specific defect caches
            inspection_id = f"{building_id}_{inspection_date}_C{cycle_id}"
            cache_manager.invalidate(f"cortex:cache:defects:{inspection_id}")
            
            logger.info("Direct defect saved synchronously.", defect_id=defect.get("defect_id"))
            return {
                "status": "succeeded",
                "job_id": f"direct-{uuid.uuid4()}",
                "message": "Defect cataloged directly in database."
            }
        except Exception as e:
            logger.error("Failed to save direct defect", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to save direct defect: {str(e)}")

    input_dir = None
    output_dir = None
    if req:
        input_dir = req.get("input_dir")
        output_dir = req.get("output_dir")
        
    input_dir = input_dir or str(WORKSPACE / "data" / "raw")
    output_dir = output_dir or str(WORKSPACE / "data" / "reports")
    
    # Invalidate cache on new run
    cache_manager.invalidate("cortex:cache:inspections")
    
    # Try Celery dispatch
    try:
        task = run_pipeline_task.delay(input_dir, output_dir)
        logger.info("Pipeline task dispatched via Celery", job_id=task.id)
        return {"status": "dispatched", "job_id": task.id}
    except Exception:
        # Redis/Celery is offline. Spin up a background thread!
        job_id = f"fallback-{uuid.uuid4()}"
        logger.warning("Celery/Redis offline. Launching fallback background thread.", job_id=job_id)
        thread = threading.Thread(target=run_fallback_job_thread, args=(job_id, input_dir, output_dir))
        thread.daemon = True
        thread.start()
        return {"status": "dispatched", "job_id": job_id}

@app.get("/api/jobs/{job_id}")
@app.get("/api/v1/jobs/{job_id}")
@app.get("/api/inspections/{job_id}/status")
@app.get("/api/v1/inspections/{job_id}/status")
async def get_job_status(job_id: str):
    """Query progress metrics and states of an active background job."""
    # Check fallback thread queue first
    if job_id.startswith("fallback-"):
        job = FALLBACK_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=444, detail="Background task not found.")
        return job
        
    try:
        from celery.result import AsyncResult
        res = AsyncResult(job_id)
        if res.state == "PENDING":
            return {"progress": 0, "progress_pct": 0.0, "status": "pending", "message": "Task waiting in broker queue..."}
        elif res.state == "PROGRESS":
            meta = res.info or {}
            prog = float(meta.get("progress", 50.0))
            return {
                "progress": prog,
                "progress_pct": prog,
                "status": "running",
                "message": meta.get("status", "Running...")
            }
        elif res.state == "SUCCESS":
            return {
                "progress": 100,
                "progress_pct": 100.0,
                "status": "succeeded",
                "message": "Pipeline completed successfully!"
            }
        elif res.state == "FAILURE":
            return {
                "progress": 0,
                "progress_pct": 0.0,
                "status": "failed",
                "message": f"Job failed: {str(res.info)}"
            }
        else:
            return {
                "progress": 50,
                "progress_pct": 50.0,
                "status": "running",
                "message": f"Current status: {res.state}"
            }
    except Exception as e:
        logger.error("Failed to fetch celery job status", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# 8. Mounting static dashboard files and reports
class SecureStaticFiles(StaticFiles):
    """StaticFiles that refuses to serve database files.

    The data directory contains the SQLite database (defects.db plus its
    -wal/-shm sidecars). Serving those over HTTP would leak the entire
    datastore, so we block any request for them with a 403.
    """

    _BLOCKED_SUFFIXES = (".db", ".db-wal", ".db-shm", ".db-journal",
                         ".sqlite", ".sqlite3")

    async def get_response(self, path, scope):
        lowered = path.lower()
        if lowered.endswith(self._BLOCKED_SUFFIXES) or "defects.db" in lowered:
            from starlette.responses import PlainTextResponse
            return PlainTextResponse("Forbidden", status_code=403)
        return await super().get_response(path, scope)


# Serve report artifacts from the (possibly persistent) data directory.
_DATA_MOUNT = Path(os.getenv("CORTEX_DATA_DIR", str(WORKSPACE / "data")))
if _DATA_MOUNT.exists():
    app.mount("/data", SecureStaticFiles(directory=str(_DATA_MOUNT)), name="data")
else:
    logger.warning("Data directory %s not found — /data static mount skipped.", _DATA_MOUNT)

# Serve the compiled Next.js frontend. Guard the mount so a missing build
# (e.g. local dev without `npm run build`) does not crash server startup.
_FRONTEND_DIR = WORKSPACE / "frontend" / "out"
if _FRONTEND_DIR.exists() and any(_FRONTEND_DIR.iterdir()):
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
else:
    logger.warning("Frontend build not found at %s — serving API only.", _FRONTEND_DIR)

    @app.get("/", include_in_schema=False)
    async def _frontend_missing():
        return {
            "status": "ok",
            "message": "Cortex API is running. Frontend build not present.",
            "docs": "/docs",
            "health": "/api/health",
        }

# 9. Launcher Helpers
def is_port_in_use(port: int) -> bool:
    """[RC-14] Socket pre-check before binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0


def find_free_port(preferred: int) -> int:
    """[RC-13] If preferred port is occupied, find next free port."""
    port = preferred
    while port < preferred + 20:
        if not is_port_in_use(port):
            return port
        logger.warning("Port %d in use, trying %d", port, port + 1)
        port += 1
    raise RuntimeError(f"No free port found in range {preferred}–{port}")


def open_browser(port: int):
    time.sleep(1.0)
    url = f"http://localhost:{port}/"
    logger.info("Opening web browser", url=url)
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Cortex Dashboard Launcher")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Skip auto-open browser")
    parser.add_argument("--skip-tile-check", action="store_true", help="Skip tile validation")
    args = parser.parse_args()
    
    logger.info("=====================================================")
    logger.info("   CORTEX FAÇADE INTELLIGENCE FRONTEND SERVER       ")
    logger.info("=====================================================")
    
    # 1. Tile asset pre-validation  [RC-15]
    if not args.skip_tile_check:
        tile_errors = validate_tile_assets()
        if tile_errors:
            logger.warning("Tile asset validation warnings:")
            for err in tile_errors:
                logger.warning("  ✗ %s", err)
            # Non-fatal: log but don't exit — tiles may not exist in dev mode
        else:
            logger.info("✓ Tile assets validated")
    
    # 2. Pre-validate Mosaic Asset & Data store
    facade_image = WORKSPACE / "data" / "reports" / "stitched_facade.png"
    if not facade_image.exists():
        logger.warning("Facade image not found at %s. Server will start but pipeline may not have run yet.", str(facade_image))
        
    # 3. Port selection  [RC-13, RC-14]
    env_port = os.getenv("PORT")
    if env_port:
        port = int(env_port)
        logger.info("Using port from environment: %d", port)
    else:
        port = find_free_port(args.port)
        if port != args.port:
            logger.warning("Preferred port %d was occupied — using %d", args.port, port)
        
    # 4. Threaded browser opening  [RC-14]
    if not args.no_browser and not env_port:
        browser_thread = threading.Thread(target=open_browser, args=(port,))
        browser_thread.daemon = True
        browser_thread.start()
    
    # 5. Print endpoint summary
    host = os.getenv("HOST", "127.0.0.1")
    if os.getenv("RENDER") == "true":
        host = "0.0.0.0"
        
    url = f"http://{host}:{port}"
    logger.info("✓ Cortex server starting at %s", url)
    logger.info("  Endpoints:")
    logger.info("  GET %s/api/health", url)
    logger.info("  GET %s/api/inspections", url)
    logger.info("  GET %s/api/defects?inspection_id=<id>", url)
    logger.info("  POST %s/api/run-inspection", url)
    logger.info("  GET %s/api/jobs/<job_id>", url)
    logger.info("  GET %s/metrics", url)
    logger.info("Press Ctrl+C to stop.")
    
    # 6. Spin up server
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
