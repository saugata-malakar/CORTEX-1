"""
Cortex — workers/tasks.py
Celery task implementations.
"""

import logging
import time
from datetime import datetime

import redis
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from workers.celery_app import celery_app

log = logging.getLogger("cortex.worker")

# ─── Sync DB session for Celery (not async) ───────────────────────────────────

import os
_SYNC_DB_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://cortex:cortexpass@postgres:5432/cortex_db",
)
_engine = create_engine(
    _SYNC_DB_URL,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
    pool_pre_ping=True,
)
_SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)


def _get_db() -> Session:
    return _SessionFactory()


def _get_redis():
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    pw  = os.getenv("REDIS_PASSWORD", "")
    if pw:
        url = url.replace("redis://", f"redis://:{pw}@")
    return redis.from_url(url, decode_responses=True)


# ─── Progress helpers ─────────────────────────────────────────────────────────

def _update_progress(
    db: Session,
    r: redis.Redis,
    job_id: str,
    pct: int,
    status: str = "running",
    error: str | None = None,
):
    """
    Dual-write progress:
      1. DB for durability
      2. Redis for fast poll (<5ms response to frontend)
    """
    from api.models import InspectionJob, JobStatus

    job = db.get(InspectionJob, job_id)
    if not job:
        return

    job.status       = getattr(JobStatus, status.upper())
    job.progress_pct = pct
    if error:
        job.error_message = error
    if status == "running" and not job.started_at:
        job.started_at = datetime.utcnow()
    if status in ("succeeded", "failed", "cancelled"):
        job.completed_at = datetime.utcnow()

    db.commit()

    # Redis fast-path (5s TTL — frontend polls every 2s)
    r.setex(
        f"job:status:{job_id}",
        5,
        f'{{"job_id":"{job_id}","status":"{status}",'
        f'"progress_pct":{pct},"error":{repr(error) if error else "null"}}}',
    )


# ─── Main pipeline task ───────────────────────────────────────────────────────

@celery_app.task(
    name="workers.tasks.run_inspection_pipeline",
    bind=True,
    max_retries=2,
    soft_time_limit=600,
    time_limit=660,
    acks_late=True,
)
def run_inspection_pipeline(
    self: Task,
    job_id: str,
    org_id: str,
    building_id: str,
    s3_image_key: str,
    cycle_id: int,
    gsd_mm_per_px: float,
    elapsed_months: float,
):
    """
    Full inspection pipeline execution.

    Stages:
      [10%] Download image from S3
      [25%] Feature extraction (parallel ThreadPoolExecutor)
      [50%] Defect detection (blackbox API + local model)
      [65%] Temporal matching with previous cycle
      [80%] VI classification + zone heatmap
      [90%] Save results to DB
      [95%] Upload GeoJSON + report to S3
     [100%] Done
    """
    db = _get_db()
    r = _get_redis()
    tmp_image_path = None

    try:
        log.info(f"Pipeline start: job={job_id} building={building_id} cycle={cycle_id}")
        _update_progress(db, r, job_id, 5, "running")

        # ── Stage 1: Download image ─────────────────────────────────────────
        _update_progress(db, r, job_id, 10, "running")
        tmp_image_path = _download_from_s3(s3_image_key)
        log.info(f"Image downloaded: {tmp_image_path}")

        # ── Stage 2: Feature extraction ────────────────────────────────────
        _update_progress(db, r, job_id, 25, "running")
        from src.pipeline import CortexPipeline
        config = _build_config(gsd_mm_per_px=gsd_mm_per_px, elapsed_months=elapsed_months)
        pipeline = CortexPipeline(config_dict=config)

        # Load previous cycle defects for temporal tracking
        _update_progress(db, r, job_id, 40, "running")
        prev_defects = _load_previous_defects(db, building_id, cycle_id)

        # ── Stage 3: Run pipeline ──────────────────────────────────────────
        _update_progress(db, r, job_id, 50, "running")
        result = pipeline.run(
            image_path=tmp_image_path,
            building_id=building_id,
            cycle_id=cycle_id,
            previous_defects=prev_defects,
        )
        log.info(
            f"Pipeline complete: {result.total_defects} defects "
            f"vi={result.vi_class} warnings={len(result.pipeline_warnings)}"
        )

        # ── Stage 4: Save to DB ────────────────────────────────────────────
        _update_progress(db, r, job_id, 80, "running")
        import dataclasses
        result_dict = dataclasses.asdict(result)
        inspection_id = _save_result_to_db(db, job_id, org_id, building_id, result_dict)

        # ── Stage 5: Upload artifacts to S3 ───────────────────────────────
        _update_progress(db, r, job_id, 90, "running")
        geojson_key, report_key = _upload_artifacts(
            db, inspection_id, building_id, cycle_id, result_dict
        )

        # ── Stage 6: Done ─────────────────────────────────────────────────
        _update_progress(db, r, job_id, 100, "succeeded")
        log.info(f"Job {job_id} completed successfully")

        return {"status": "succeeded", "inspection_id": inspection_id}

    except SoftTimeLimitExceeded:
        msg = "Pipeline timed out after 10 minutes"
        log.error(f"Job {job_id} timeout")
        _update_progress(db, r, job_id, 0, "failed", error=msg)
        raise   # don't retry timeouts

    except Exception as exc:
        log.exception(f"Job {job_id} failed: {exc}")
        error_msg = _classify_error(exc)

        if self.request.retries < self.max_retries:
            _update_progress(db, r, job_id, 0, "running",
                             error=f"Retrying ({self.request.retries + 1}/{self.max_retries})...")
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))

        _update_progress(db, r, job_id, 0, "failed", error=error_msg)
        raise

    finally:
        db.close()
        if tmp_image_path:
            _cleanup_tmp(tmp_image_path)


# ─── Stage helpers ────────────────────────────────────────────────────────────

def _download_from_s3(s3_key: str) -> str:
    import os
    # Local file fallback for developers (avoids boto3 ClientError)
    if os.path.exists(s3_key):
        return s3_key
    local_name = os.path.join("/tmp/cortex_uploads", os.path.basename(s3_key))
    if os.path.exists(local_name):
        return local_name

    import boto3, tempfile, pathlib
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "ap-south-1"),
    )
    bucket = os.getenv("S3_BUCKET", "cortex-inspections")
    suffix = pathlib.Path(s3_key).suffix or ".jpg"
    tmp = tempfile.NamedTemporaryFile(
        suffix=suffix, dir="/tmp/cortex_uploads", delete=False
    )
    s3.download_fileobj(bucket, s3_key, tmp)
    tmp.close()
    return tmp.name



def _load_previous_defects(db: Session, building_id: str, cycle_id: int) -> list:
    """Load defect ORM rows from the previous cycle, if any."""
    if cycle_id <= 1:
        return []
    from sqlalchemy import select
    from api.models import Defect, InspectionJob, InspectionResult, JobStatus
    stmt = (
        select(Defect)
        .join(InspectionResult, Defect.inspection_id == InspectionResult.id)
        .join(InspectionJob, InspectionResult.job_id == InspectionJob.id)
        .where(
            InspectionJob.building_id == building_id,
            InspectionJob.cycle_id == cycle_id - 1,
            InspectionJob.status == JobStatus.SUCCEEDED,
        )
    )
    return list(db.execute(stmt).scalars().all())


def _build_config(gsd_mm_per_px: float, elapsed_months: float) -> dict:
    return {
        "gsd_mm_per_px": gsd_mm_per_px,
        "temporal_tolerance_px": 25.0,
        "elapsed_months": elapsed_months,
        "blackbox_api_endpoint": os.getenv("BLACKBOX_API_ENDPOINT", ""),
        "blackbox_api_key": os.getenv("BLACKBOX_API_KEY", ""),
        "bayesian_opt_iterations": 10,
    }


def _save_result_to_db(
    db: Session,
    job_id: str,
    org_id: str,
    building_id: str,
    result: dict,
) -> str:
    from api.models import Defect, InspectionResult, Severity, DefectType, VIClass

    vi_class_map = {
        "minor": VIClass.MINOR,
        "moderate": VIClass.MODERATE,
        "severe": VIClass.SEVERE,
        "critical": VIClass.CRITICAL,
    }

    inspection = InspectionResult(
        job_id=job_id,
        org_id=org_id,
        building_id=building_id,
        cycle_id=result["cycle_id"],
        pipeline_version=result["pipeline_version"],
        run_timestamp=datetime.fromisoformat(result["run_timestamp"].replace("Z", "")),
        gsd_mm_per_px=result["gsd_mm_per_px"],
        vi_class=vi_class_map[result["vi_class"]],
        vi_score=result["vi_score"],
        total_defects=result["total_defects"],
        zone_severity_index=result.get("zone_severity_index", {}),
        pipeline_warnings=result.get("pipeline_warnings", []),
        shap_features=result.get("shap_features"),
    )
    db.add(inspection)
    db.flush()

    type_map     = {v: getattr(DefectType, v.upper())   for v in ["crack","spall","delamination","efflorescence"]}
    severity_map = {v: getattr(Severity, v.upper())     for v in ["hairline","moderate","severe"]}

    for d in result.get("defects", []):
        defect = Defect(
            inspection_id=str(inspection.id),
            org_id=org_id,
            defect_ref=d["defect_id"],
            defect_type=type_map.get(d["defect_type"], DefectType.CRACK),
            severity=severity_map.get(d["severity"], Severity.HAIRLINE),
            width_mm=float(d.get("width_mm") or 0),
            length_cm=float(d.get("length_cm") or 0),
            area_px2=float(d.get("area_px2") or 0),
            centroid_x=float(d.get("centroid_x") or 0),
            centroid_y=float(d.get("centroid_y") or 0),
            confidence=float(d.get("confidence") or 0),
            false_positive_prob=float(d.get("false_positive_prob") or 0),
            delta_width_mm=float(d.get("delta_width_mm") or 0),
            growth_rate_mm_per_month=float(d.get("growth_rate_mm_per_month") or 0),
            growth_acceleration=float(d.get("growth_acceleration") or 0),
            contour_geojson=d.get("contour_geojson", {}),
        )
        db.add(defect)

    db.commit()
    log.info(f"Saved inspection {inspection.id} with {len(result.get('defects',[]))} defects")
    return str(inspection.id)


def _upload_artifacts(
    db: Session,
    inspection_id: str,
    building_id: str,
    cycle_id: int,
    result: dict,
) -> tuple[str, str]:
    import boto3, json
    s3 = boto3.client("s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "ap-south-1"),
    )
    bucket = os.getenv("S3_BUCKET", "cortex-inspections")
    base = f"results/{building_id}/cycle_{cycle_id}/{inspection_id}"

    # GeoJSON for Leaflet map overlay
    features = [d["contour_geojson"] for d in result.get("defects", []) if d.get("contour_geojson")]
    geojson = {"type": "FeatureCollection", "features": features}
    geojson_key = f"{base}/defects.geojson"
    s3.put_object(
        Bucket=bucket, Key=geojson_key,
        Body=json.dumps(geojson).encode(),
        ContentType="application/geo+json",
    )

    # Full result JSON for audit/export
    report_key = f"{base}/inspection_result.json"
    s3.put_object(
        Bucket=bucket, Key=report_key,
        Body=json.dumps(result, default=str).encode(),
        ContentType="application/json",
    )

    # Update InspectionResult with S3 keys
    from api.models import InspectionResult
    insp = db.get(InspectionResult, inspection_id)
    if insp:
        insp.geojson_s3_key = geojson_key
        insp.report_s3_key  = report_key
        db.commit()

    return geojson_key, report_key


def _classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "s3" in msg or "nosuchkey" in msg:
        return "Image file not found in storage. Please re-upload."
    if "timeout" in msg or "connection" in msg:
        return "External detection service unavailable. Please retry."
    if "memory" in msg or "oom" in msg:
        return "Image too large to process. Use a smaller image."
    return "An unexpected error occurred. The team has been notified."


def _cleanup_tmp(path: str):
    import os
    try:
        os.unlink(path)
    except OSError:
        pass


# ─── Scheduled tasks ──────────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Delete expired refresh tokens. Runs hourly."""
    from datetime import datetime
    db = _get_db()
    try:
        from api.models import RefreshToken
        from sqlalchemy import delete
        result = db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < datetime.utcnow())
        )
        db.commit()
        log.info(f"Cleaned up {result.rowcount} expired refresh tokens")
    finally:
        db.close()


@celery_app.task(name="workers.tasks.refresh_org_stats")
def refresh_org_stats():
    """Pre-compute and cache org-level stats. Runs every 5 min."""
    db = _get_db()
    r  = _get_redis()
    try:
        from sqlalchemy import func, select
        from api.models import InspectionJob, Organization, JobStatus
        orgs = db.execute(
            select(Organization.id).where(Organization.is_active.is_(True))
        ).scalars().all()

        for org_id in orgs:
            total = db.execute(
                select(func.count(InspectionJob.id))
                .where(InspectionJob.org_id == str(org_id))
            ).scalar_one()
            r.setex(f"org:{org_id}:stats", 360, f'{{"total_jobs":{total}}}')

        log.info(f"Refreshed stats cache for {len(orgs)} orgs")
    finally:
        db.close()
