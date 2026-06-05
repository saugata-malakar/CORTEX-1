"""
Cortex — api/models.py
SQLAlchemy ORM models — full production schema.

Design decisions:
  - UUID primary keys everywhere (no sequential ID leakage via API)
  - soft-delete on all user-facing tables (deleted_at nullable timestamp)
  - org_id FK on every tenant-scoped table → RLS enforced at query layer
  - JSON columns for flexible metadata (warnings, zone maps, SHAP values)
  - Enum types declared at DB level → data integrity without app validation
  - Composite indexes on (org_id, created_at) for paginated list queries
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Index, Integer, JSON, String, Text, UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from api.database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.utcnow()


# ─── Enums ───────────────────────────────────────────────────────────────────

class UserRole(str, PyEnum):
    ADMIN    = "admin"
    ENGINEER = "engineer"
    VIEWER   = "viewer"


class JobStatus(str, PyEnum):
    PENDING    = "pending"
    RUNNING    = "running"
    SUCCEEDED  = "succeeded"
    FAILED     = "failed"
    CANCELLED  = "cancelled"


class VIClass(str, PyEnum):
    MINOR    = "minor"
    MODERATE = "moderate"
    SEVERE   = "severe"
    CRITICAL = "critical"


class DefectType(str, PyEnum):
    CRACK          = "crack"
    SPALL          = "spall"
    DELAMINATION   = "delamination"
    EFFLORESCENCE  = "efflorescence"


class Severity(str, PyEnum):
    HAIRLINE = "hairline"
    MODERATE = "moderate"
    SEVERE   = "severe"


# ─── Organization (tenant root) ───────────────────────────────────────────────

class Organization(Base):
    __tablename__ = "organizations"

    id         = Column(UUID, primary_key=True, default=_uuid)
    name       = Column(String(200), nullable=False)
    slug       = Column(String(100), nullable=False, unique=True)   # URL-safe name
    plan       = Column(String(50), nullable=False, default="starter")  # starter|pro|enterprise
    is_active  = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    deleted_at = Column(DateTime, nullable=True)

    users     = relationship("User",     back_populates="org", lazy="select")
    buildings = relationship("Building", back_populates="org", lazy="select")

    __table_args__ = (
        Index("ix_org_slug", "slug"),
    )


# ─── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(UUID, primary_key=True, default=_uuid)
    org_id        = Column(UUID, ForeignKey("organizations.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    email         = Column(String(320), nullable=False)
    hashed_pw     = Column(String(200), nullable=False)
    full_name     = Column(String(200), nullable=True)
    role          = Column(ENUM(UserRole, name="user_role"), nullable=False,
                           default=UserRole.VIEWER)
    is_active     = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, nullable=False, default=_now)
    deleted_at    = Column(DateTime, nullable=True)

    org           = relationship("Organization", back_populates="users")
    refresh_tokens = relationship("RefreshToken", back_populates="user",
                                   cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_user_org_email"),
        Index("ix_user_org_created", "org_id", "created_at"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(UUID, primary_key=True, default=_uuid)
    user_id    = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    revoked    = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_now)

    user = relationship("User", back_populates="refresh_tokens")


# ─── Building (physical asset being inspected) ────────────────────────────────

class Building(Base):
    __tablename__ = "buildings"

    id          = Column(UUID, primary_key=True, default=_uuid)
    org_id      = Column(UUID, ForeignKey("organizations.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    name        = Column(String(300), nullable=False)
    address     = Column(Text, nullable=True)
    lat         = Column(Float, nullable=True)
    lng         = Column(Float, nullable=True)
    metadata_   = Column("metadata", JSON, nullable=False, default=dict)
    created_at  = Column(DateTime, nullable=False, default=_now)
    deleted_at  = Column(DateTime, nullable=True)

    org         = relationship("Organization", back_populates="buildings")
    inspections = relationship("InspectionJob", back_populates="building",
                               lazy="select")

    __table_args__ = (
        Index("ix_building_org_created", "org_id", "created_at"),
    )


# ─── InspectionJob (async task tracking) ─────────────────────────────────────

class InspectionJob(Base):
    """
    Represents one async Celery task.
    Frontend polls GET /api/v1/inspections/{job_id}/status.
    """
    __tablename__ = "inspection_jobs"

    id              = Column(UUID, primary_key=True, default=_uuid)
    org_id          = Column(UUID, ForeignKey("organizations.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    building_id     = Column(UUID, ForeignKey("buildings.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    submitted_by    = Column(UUID, ForeignKey("users.id"), nullable=False)
    cycle_id        = Column(Integer, nullable=False, default=1)

    # Task tracking
    celery_task_id  = Column(String(200), nullable=True)
    status          = Column(ENUM(JobStatus, name="job_status"), nullable=False,
                             default=JobStatus.PENDING)
    progress_pct    = Column(Integer, nullable=False, default=0)
    error_message   = Column(Text, nullable=True)

    # Input references (S3 paths)
    raw_image_s3_key = Column(String(500), nullable=True)

    # Timing
    queued_at    = Column(DateTime, nullable=False, default=_now)
    started_at   = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relations
    building  = relationship("Building", back_populates="inspections")
    result    = relationship("InspectionResult", back_populates="job",
                              uselist=False, lazy="select")

    __table_args__ = (
        Index("ix_job_org_status", "org_id", "status"),
        Index("ix_job_org_queued", "org_id", "queued_at"),
    )


# ─── InspectionResult (pipeline output) ───────────────────────────────────────

class InspectionResult(Base):
    __tablename__ = "inspection_results"

    id                = Column(UUID, primary_key=True, default=_uuid)
    job_id            = Column(UUID, ForeignKey("inspection_jobs.id", ondelete="CASCADE"),
                               nullable=False, unique=True, index=True)
    org_id            = Column(UUID, ForeignKey("organizations.id"), nullable=False, index=True)
    building_id       = Column(UUID, ForeignKey("buildings.id"), nullable=False, index=True)
    cycle_id          = Column(Integer, nullable=False)

    # Pipeline metadata
    pipeline_version  = Column(String(20), nullable=False)
    run_timestamp     = Column(DateTime, nullable=False)
    gsd_mm_per_px     = Column(Float, nullable=False)

    # VI output
    vi_class          = Column(ENUM(VIClass, name="vi_class"), nullable=False)
    vi_score          = Column(Float, nullable=False)
    total_defects     = Column(Integer, nullable=False, default=0)

    # Flexible JSON payloads
    zone_severity_index = Column(JSON, nullable=False, default=dict)
    pipeline_warnings   = Column(JSON, nullable=False, default=list)
    shap_features       = Column(JSON, nullable=True)

    # S3 output references
    geojson_s3_key    = Column(String(500), nullable=True)
    report_s3_key     = Column(String(500), nullable=True)

    created_at        = Column(DateTime, nullable=False, default=_now)

    job     = relationship("InspectionJob", back_populates="result")
    defects = relationship("Defect", back_populates="inspection",
                           cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        Index("ix_result_org_building", "org_id", "building_id"),
        Index("ix_result_vi_class", "vi_class"),
    )


# ─── Defect ───────────────────────────────────────────────────────────────────

class Defect(Base):
    __tablename__ = "defects"

    id            = Column(UUID, primary_key=True, default=_uuid)
    inspection_id = Column(UUID, ForeignKey("inspection_results.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    org_id        = Column(UUID, ForeignKey("organizations.id"), nullable=False, index=True)

    # Identity
    defect_ref    = Column(String(100), nullable=False)   # human-readable "B1_C2_0042"

    # Classification
    defect_type   = Column(ENUM(DefectType, name="defect_type"), nullable=False)
    severity      = Column(ENUM(Severity, name="severity"), nullable=False)

    # Measurements
    width_mm      = Column(Float, nullable=False, default=0)
    length_cm     = Column(Float, nullable=False, default=0)
    area_px2      = Column(Float, nullable=False, default=0)
    centroid_x    = Column(Float, nullable=False, default=0)
    centroid_y    = Column(Float, nullable=False, default=0)

    # Model outputs
    confidence         = Column(Float, nullable=False, default=0)
    false_positive_prob = Column(Float, nullable=False, default=0)

    # Temporal tracking
    matched_prev_defect_id       = Column(UUID, ForeignKey("defects.id"),
                                           nullable=True, index=True)
    delta_width_mm               = Column(Float, nullable=False, default=0)
    growth_rate_mm_per_month     = Column(Float, nullable=False, default=0)
    growth_acceleration          = Column(Float, nullable=False, default=0)

    # GeoJSON stored as JSON (avoid PostGIS dep for now; add later)
    contour_geojson  = Column(JSON, nullable=False, default=dict)

    created_at       = Column(DateTime, nullable=False, default=_now)

    inspection       = relationship("InspectionResult", back_populates="defects")
    prev_defect      = relationship("Defect", remote_side="Defect.id",
                                    foreign_keys=[matched_prev_defect_id])

    __table_args__ = (
        UniqueConstraint("inspection_id", "defect_ref", name="uq_defect_ref"),
        Index("ix_defect_type_severity", "defect_type", "severity"),
        Index("ix_defect_propagated", "matched_prev_defect_id"),
        Index("ix_defect_org_created", "org_id", "created_at"),
    )


# ─── AuditLog ─────────────────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Append-only audit trail.
    Never update or delete rows here.
    """
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    org_id      = Column(UUID, nullable=False, index=True)
    user_id     = Column(UUID, nullable=True)
    action      = Column(String(100), nullable=False)   # "inspection.submitted"
    resource    = Column(String(100), nullable=True)    # "inspection_jobs"
    resource_id = Column(UUID, nullable=True)
    ip_address  = Column(String(45), nullable=True)
    metadata_   = Column("metadata", JSON, nullable=False, default=dict)
    created_at  = Column(DateTime, nullable=False,
                          server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_audit_org_action", "org_id", "action"),
        Index("ix_audit_resource", "resource", "resource_id"),
    )
