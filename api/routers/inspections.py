"""
Cortex — api/routers/inspections.py
Inspection jobs REST API.

Endpoints:
  POST   /inspections           → submit new inspection job (async)
  GET    /inspections           → list jobs for org (paginated)
  GET    /inspections/{job_id}  → get job + result if complete
  GET    /inspections/{job_id}/status  → lightweight status poll
  DELETE /inspections/{job_id}  → cancel pending job
  GET    /inspections/{job_id}/defects → paginated defect list
  GET    /inspections/{job_id}/geojson → full GeoJSON for map overlay

Flow:
  1. Client POSTs image to S3 (presigned URL from /api/v1/uploads/presign)
  2. Client POSTs {building_id, s3_key, cycle_id} here
  3. We create InspectionJob in DB, enqueue Celery task, return {job_id}
  4. Client polls /status → {status, progress_pct}
  5. On status=succeeded, client fetches full result
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import assert_org_access, get_current_user, require_engineer
from api.cache import (
    cache_delete,
    cache_get,
    cache_set,
    key_inspection_result,
    key_job_status,
)
from api.database import get_session
from api.models import (
    AuditLog,
    Building,
    Defect,
    InspectionJob,
    InspectionResult,
    JobStatus,
    User,
)

log = logging.getLogger("cortex.api.inspections")
router = APIRouter()


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class SubmitInspectionRequest(BaseModel):
    building_id:    UUID
    s3_image_key:   str = Field(..., description="S3 key of uploaded facade image")
    cycle_id:       int = Field(default=1, ge=1, le=100)
    gsd_mm_per_px:  float = Field(default=1.2, gt=0, le=10)
    elapsed_months: float = Field(default=6.0, ge=0)


class JobStatusResponse(BaseModel):
    job_id:       str
    status:       str
    progress_pct: int
    queued_at:    str
    started_at:   str | None
    completed_at: str | None
    error:        str | None


class InspectionSummary(BaseModel):
    job_id:        str
    building_id:   str
    cycle_id:      int
    status:        str
    vi_class:      str | None
    vi_score:      float | None
    total_defects: int | None
    run_timestamp: str | None
    pipeline_warnings: list | None


class DefectListItem(BaseModel):
    id:               str
    defect_ref:       str
    defect_type:      str
    severity:         str
    width_mm:         float
    length_cm:        float
    area_px2:         float
    confidence:       float
    false_positive_prob: float
    growth_rate_mm_per_month: float
    growth_acceleration: float
    matched_prev_defect_id: str | None


# ─── POST /inspections ────────────────────────────────────────────────────────

@router.post(
    "/inspections",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new inspection job",
)
async def submit_inspection(
    body: SubmitInspectionRequest,
    current_user: Annotated[User, Depends(require_engineer)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Enqueues an async pipeline run.
    Returns job_id immediately — client polls /inspections/{job_id}/status.
    """
    # 1. Verify building belongs to user's org
    building = await db.get(Building, str(body.building_id))
    if not building or building.deleted_at:
        raise HTTPException(status_code=404, detail="Building not found")
    assert_org_access(current_user, building.org_id)

    # 2. Check for duplicate in-flight job (idempotency)
    existing = await db.execute(
        select(InspectionJob).where(
            InspectionJob.building_id == str(body.building_id),
            InspectionJob.cycle_id == body.cycle_id,
            InspectionJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="An inspection for this building/cycle is already in progress.",
        )

    # 3. Create job record
    job = InspectionJob(
        org_id=str(current_user.org_id),
        building_id=str(body.building_id),
        submitted_by=str(current_user.id),
        cycle_id=body.cycle_id,
        raw_image_s3_key=body.s3_image_key,
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.flush()  # get job.id before task enqueue

    # 4. Enqueue Celery task
    from workers.tasks import run_inspection_pipeline
    task = run_inspection_pipeline.apply_async(
        kwargs={
            "job_id":         str(job.id),
            "org_id":         str(current_user.org_id),
            "building_id":    str(body.building_id),
            "s3_image_key":   body.s3_image_key,
            "cycle_id":       body.cycle_id,
            "gsd_mm_per_px":  body.gsd_mm_per_px,
            "elapsed_months": body.elapsed_months,
        },
        queue="pipeline",
        countdown=1,
    )
    job.celery_task_id = task.id

    # 5. Audit log
    db.add(AuditLog(
        org_id=str(current_user.org_id),
        user_id=str(current_user.id),
        action="inspection.submitted",
        resource="inspection_jobs",
        resource_id=str(job.id),
        ip_address=None,
        metadata_={"building_id": str(body.building_id), "cycle_id": body.cycle_id},
    ))

    log.info(f"Inspection job queued: {job.id} task={task.id}")

    return {
        "job_id":       str(job.id),
        "celery_task":  task.id,
        "status":       JobStatus.PENDING,
        "message":      "Inspection queued. Poll /status for progress.",
    }


# ─── GET /inspections ─────────────────────────────────────────────────────────

@router.get("/inspections", summary="List inspection jobs for org")
async def list_inspections(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    building_id: UUID | None = Query(None),
    status_filter: JobStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    q = select(InspectionJob).where(
        InspectionJob.org_id == str(current_user.org_id),
    )
    if building_id:
        q = q.where(InspectionJob.building_id == str(building_id))
    if status_filter:
        q = q.where(InspectionJob.status == status_filter)

    # Total count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginated results with result JOIN
    q = (
        q.options(selectinload(InspectionJob.result))
        .order_by(InspectionJob.queued_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()

    items = []
    for job in rows:
        r = job.result
        items.append(InspectionSummary(
            job_id=str(job.id),
            building_id=str(job.building_id),
            cycle_id=job.cycle_id,
            status=job.status.value,
            vi_class=r.vi_class.value if r else None,
            vi_score=r.vi_score if r else None,
            total_defects=r.total_defects if r else None,
            run_timestamp=r.run_timestamp.isoformat() if r else None,
            pipeline_warnings=r.pipeline_warnings if r else None,
        ))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


# ─── GET /inspections/{job_id}/status ────────────────────────────────────────

@router.get(
    "/inspections/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Lightweight status poll",
)
async def get_job_status(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    # Check Redis cache first (updates every 2s by worker)
    cached = await cache_get(key_job_status(str(job_id)))
    if cached:
        return JobStatusResponse(**cached)

    job = await db.get(InspectionJob, str(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    assert_org_access(current_user, job.org_id)

    resp = JobStatusResponse(
        job_id=str(job.id),
        status=job.status.value,
        progress_pct=job.progress_pct,
        queued_at=job.queued_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error_message,
    )
    # Cache for 5s
    await cache_set(key_job_status(str(job_id)), resp.model_dump(), ttl=5)
    return resp


# ─── GET /inspections/{job_id} ───────────────────────────────────────────────

@router.get("/inspections/{job_id}", summary="Full inspection result")
async def get_inspection(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    # Check cache
    cache_key = key_inspection_result(str(job_id))
    cached = await cache_get(cache_key)
    if cached:
        return cached

    job = await db.execute(
        select(InspectionJob)
        .where(InspectionJob.id == str(job_id))
        .options(selectinload(InspectionJob.result))
    )
    job_obj = job.scalar_one_or_none()
    if not job_obj:
        raise HTTPException(status_code=404, detail="Job not found")
    assert_org_access(current_user, job_obj.org_id)

    if job_obj.status != JobStatus.SUCCEEDED:
        return {
            "job_id": str(job_id),
            "status": job_obj.status.value,
            "progress_pct": job_obj.progress_pct,
            "result": None,
        }

    r = job_obj.result
    payload = {
        "job_id":           str(job_id),
        "status":           job_obj.status.value,
        "building_id":      str(job_obj.building_id),
        "cycle_id":         job_obj.cycle_id,
        "pipeline_version": r.pipeline_version,
        "run_timestamp":    r.run_timestamp.isoformat(),
        "vi_class":         r.vi_class.value,
        "vi_score":         r.vi_score,
        "gsd_mm_per_px":    r.gsd_mm_per_px,
        "total_defects":    r.total_defects,
        "zone_severity_index": r.zone_severity_index,
        "pipeline_warnings":   r.pipeline_warnings,
        "shap_features":       r.shap_features,
        "geojson_url":      _presign_s3(r.geojson_s3_key) if r.geojson_s3_key else None,
        "report_url":       _presign_s3(r.report_s3_key) if r.report_s3_key else None,
    }

    # Cache completed results for 10 min
    await cache_set(cache_key, payload, ttl=600)
    return payload


# ─── GET /inspections/{job_id}/defects ───────────────────────────────────────

@router.get("/inspections/{job_id}/defects", summary="Paginated defect list")
async def get_defects(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    defect_type: str | None = Query(None),
    severity: str | None = Query(None),
    propagated_only: bool = Query(False),
    sort_by: str = Query("severity", regex="^(severity|area|growth_rate)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    # Verify job access
    job = await db.get(InspectionJob, str(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    assert_org_access(current_user, job.org_id)

    if job.status != JobStatus.SUCCEEDED:
        return {"defects": [], "total": 0, "message": "Job not yet complete"}

    # Build query
    result_row = await db.execute(
        select(InspectionResult).where(InspectionResult.job_id == str(job_id))
    )
    result_obj = result_row.scalar_one_or_none()
    if not result_obj:
        raise HTTPException(status_code=404, detail="Result not found")

    q = select(Defect).where(Defect.inspection_id == str(result_obj.id))

    if defect_type:
        q = q.where(Defect.defect_type == defect_type)
    if severity:
        q = q.where(Defect.severity == severity)
    if propagated_only:
        q = q.where(Defect.matched_prev_defect_id.is_not(None))

    sort_map = {
        "severity":    Defect.area_px2.desc(),  # severity is enum, sort by area as proxy
        "area":        Defect.area_px2.desc(),
        "growth_rate": Defect.growth_rate_mm_per_month.desc(),
    }
    q = q.order_by(sort_map[sort_by])

    total = (await db.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar_one()

    offset = (page - 1) * page_size
    defects = (await db.execute(q.offset(offset).limit(page_size))).scalars().all()

    return {
        "defects": [
            DefectListItem(
                id=str(d.id),
                defect_ref=d.defect_ref,
                defect_type=d.defect_type.value,
                severity=d.severity.value,
                width_mm=d.width_mm,
                length_cm=d.length_cm,
                area_px2=d.area_px2,
                confidence=d.confidence,
                false_positive_prob=d.false_positive_prob,
                growth_rate_mm_per_month=d.growth_rate_mm_per_month,
                growth_acceleration=d.growth_acceleration,
                matched_prev_defect_id=str(d.matched_prev_defect_id)
                    if d.matched_prev_defect_id else None,
            )
            for d in defects
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ─── DELETE /inspections/{job_id} ────────────────────────────────────────────

@router.delete("/inspections/{job_id}", status_code=204)
async def cancel_inspection(
    job_id: UUID,
    current_user: Annotated[User, Depends(require_engineer)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    job = await db.get(InspectionJob, str(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    assert_org_access(current_user, job.org_id)

    if job.status not in (JobStatus.PENDING,):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job in status={job.status.value}",
        )

    # Revoke Celery task
    if job.celery_task_id:
        from workers.celery_app import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)

    job.status = JobStatus.CANCELLED
    await cache_delete(key_job_status(str(job_id)))

    log.info(f"Job cancelled: {job_id} by user={current_user.id}")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _presign_s3(s3_key: str, expires: int = 3600) -> str:
    """Generate a pre-signed S3 URL for temporary access."""
    import boto3
    from api.config import settings
    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
        ExpiresIn=expires,
    )


# ─── POST /upload-images ──────────────────────────────────────────────────────
from fastapi import UploadFile, File
import cv2
import numpy as np
import os
from typing import List
from src.civil_analysis import analyze_structural_image

@router.post(
    "/upload-images",
    summary="Upload multiple drone facade images",
)
async def upload_images(
    files: List[UploadFile] = File(...),
):
    """
    Endpoint for uploading multiple drone facade images.
    Performs real-time quality gate checks (blur and underexposure) and
    runs structural defect analysis on quality-passing frames.
    Saves the file to shared local storage (/tmp/cortex_uploads) so Celery can run on it.
    """
    results = []
    # Ensure dir exists
    os.makedirs("/tmp/cortex_uploads", exist_ok=True)
    
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
            
            # Threshold flags (matching metadata_parser.py defaults)
            is_blurry = lap_var < 100.0
            is_underexposed = mean_int < 30.0
            passed = not is_blurry and not is_underexposed
            
            warnings = []
            if is_blurry:
                warnings.append(f"Image is blurry (Laplacian variance {lap_var:.1f} < 100.0). Reshoot suggested.")
            if is_underexposed:
                warnings.append(f"Image is underexposed (Mean intensity {mean_int:.1f} < 30.0). Reshoot suggested.")
                
            # Perform civil analysis if passed
            analysis = None
            if passed:
                try:
                    analysis = analyze_structural_image(content, file.filename)
                except Exception as e:
                    warnings.append(f"Analysis error: {str(e)}")
            
            # Save file to /tmp/cortex_uploads for local pipeline access
            local_path = os.path.join("/tmp/cortex_uploads", file.filename)
            with open(local_path, "wb") as f:
                f.write(content)
                
            results.append({
                "filename": file.filename,
                "passed": passed,
                "laplacian_variance": round(lap_var, 2),
                "mean_intensity": round(mean_int, 2),
                "is_blurry": is_blurry,
                "is_underexposed": is_underexposed,
                "warnings": warnings,
                "analysis": analysis,
                "local_path": local_path  # returned to frontend so it can post it
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "passed": False,
                "error": str(e),
                "warnings": [f"Processing error: {str(e)}"]
            })
            
    return {"results": results}


# ─── POST /export-pdf ─────────────────────────────────────────────────────────
from fastapi import Response
from src.phase4_reporting.report_generator import generate_single_defect_pdf

@router.post(
    "/export-pdf",
    summary="Generate engineering diagnostic report PDF",
)
async def export_pdf(
    data: dict,
):
    """
    POST endpoint to generate and stream back a single-defect engineering diagnostic report PDF.
    """
    try:
        pdf_bytes = generate_single_defect_pdf(data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=Cortex_Repair_Specification_{data.get('filename', 'Defect')}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

