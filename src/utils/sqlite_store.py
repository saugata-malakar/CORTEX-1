"""
sqlite_store.py — Async Database Storage & ORM Repository
===========================================================
Primary datastore abstraction layer. Uses SQLAlchemy 2.0 Async ORM
to connect to PostgreSQL (asyncpg), falling back to SQLite (aiosqlite)
if the PostgreSQL database is unreachable. Integrates boto3 S3 uploading.
"""

import os
import json
import logging
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import String, Float, Integer, ForeignKey, Text, select, delete, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.utils.s3_store import S3Store

logger = logging.getLogger(__name__)

DB_DIR = Path(__file__).parents[2] / "data" / "reports"
DB_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_DB_PATH = DB_DIR / "defects.db"

# [RC-08] Retry constants for database locked errors
MAX_RETRIES = 5
RETRY_DELAY = 0.1


async def _retry_on_locked(coro_factory, retries=MAX_RETRIES):
    """[RC-08] Retry wrapper for database locked errors."""
    delay = RETRY_DELAY
    for attempt in range(retries):
        try:
            return await coro_factory()
        except Exception as exc:
            if "locked" in str(exc).lower() and attempt < retries - 1:
                logger.warning("DB locked — retry %d/%d in %.2fs", attempt + 1, retries, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 2.0)
            else:
                raise


def _safe_json(raw: Optional[str]) -> list:
    """[RC-12] Robust JSON deserialization for warnings column."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("Malformed JSON in warnings column, returning empty list.")
        return []

# Declarative base class for SQLAlchemy
class Base(DeclarativeBase):
    pass

class ORMInspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    building_id: Mapped[str] = mapped_column(String, nullable=False)
    building_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inspection_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    vi_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vi_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pipeline_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    run_timestamp: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    warnings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    s3_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    geojson_s3_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # [RC-11]

    defects = relationship("ORMDefect", back_populates="inspection", cascade="all, delete-orphan")

class ORMDefect(Base):
    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    defect_id: Mapped[str] = mapped_column(String, nullable=False)
    inspection_id: Mapped[str] = mapped_column(String, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    length_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_cm2: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    centroid_y: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    severity_class: Mapped[str] = mapped_column(String, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_false_positive: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fp_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temporal_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parent_defect_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    delta_width_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    growth_rate_mm_per_month: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    growth_acceleration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    visible_bar_diameter_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_cover_loss_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity_reduction_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    orientation_angle: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    propagation_rate: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    delamination_area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grid_reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    member_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recommended_intervention: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reinspection_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    inspection = relationship("ORMInspection", back_populates="defects")

# Thread helper to execute async functions inside synchronous methods safely
def run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


class InspectionRepository:
    """Enterprise Repository pattern encapsulating database queries & mutations."""
    def __init__(self, session) -> None:
        self.session = session

    async def get_by_id(self, inspection_id: str) -> Optional[ORMInspection]:
        return await self.session.get(ORMInspection, inspection_id)

    async def add(self, inspection: ORMInspection) -> None:
        self.session.add(inspection)

    async def get_all(self) -> List[ORMInspection]:
        stmt = select(ORMInspection).order_by(ORMInspection.run_timestamp.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_defects(self, inspection_id: str) -> None:
        await self.session.execute(delete(ORMDefect).where(ORMDefect.inspection_id == inspection_id))

    async def add_defect(self, defect: ORMDefect) -> None:
        self.session.add(defect)

    async def get_defects(self, inspection_id: str) -> List[ORMDefect]:
        stmt = select(ORMDefect).where(ORMDefect.inspection_id == inspection_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class DefectStore:
    """Manages persistent database operations. Automatically targets PostgreSQL, falling back to SQLite."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.s3_store = S3Store()
        
        # Determine database endpoints
        raw_pg_dsn = dsn or os.getenv("CORTEX_DB_URL", "postgresql+asyncpg://cortex_user:cortex_password@localhost:5432/cortex_db")
        if raw_pg_dsn.startswith("postgres://"):
            pg_dsn = raw_pg_dsn.replace("postgres://", "postgresql+asyncpg://", 1)
        elif raw_pg_dsn.startswith("postgresql://") and "+asyncpg" not in raw_pg_dsn:
            pg_dsn = raw_pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            pg_dsn = raw_pg_dsn
        sqlite_dsn = f"sqlite+aiosqlite:///{SQLITE_DB_PATH.as_posix()}"
        
        self.is_postgres = False
        try:
            temp_engine = create_async_engine(pg_dsn, connect_args={"timeout": 2} if "postgresql" in pg_dsn else {})
            run_sync(self._test_connection(temp_engine))
            # Create production-hardened engine with connection pool parameters
            self.engine = create_async_engine(
                pg_dsn,
                pool_size=20,
                max_overflow=10,
                pool_recycle=1800,
                pool_pre_ping=True,
                connect_args={"timeout": 5} if "postgresql" in pg_dsn else {}
            )
            self.is_postgres = True
            logger.info("Connected successfully to PostgreSQL database engine with connection pooling.")
        except Exception as e:
            logger.warning("PostgreSQL database connection failed: %s. Falling back to local SQLite.", e)
            self.engine = create_async_engine(sqlite_dsn)
            self.is_postgres = False

        # [RC-07] Set SQLite-specific pragmas via event listener
        if not self.is_postgres:
            @event.listens_for(self.engine.sync_engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")      # [RC-07]
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA synchronous=NORMAL")    # WAL + NORMAL = safe + fast
                cursor.close()

        self.session_factory = async_sessionmaker(bind=self.engine, expire_on_commit=False)
        run_sync(self._init_db())

    async def _test_connection(self, engine) -> None:
        async with engine.connect() as conn:
            await conn.execute(select(1))

    async def _init_db(self) -> None:
        """Create database tables if they do not exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Auto-seed PostgreSQL from local SQLite backup if PostgreSQL is empty
        if self.is_postgres:
            try:
                async with self.session_factory() as session:
                    repo = InspectionRepository(session)
                    inspections = await repo.get_all()
                    if not inspections:
                        logger.info("PostgreSQL database is empty. Checking if local SQLite backup exists to seed...")
                        if SQLITE_DB_PATH.exists():
                            logger.info("Found local SQLite backup at %s. Seeding PostgreSQL...", SQLITE_DB_PATH)
                            sqlite_engine = create_async_engine(f"sqlite+aiosqlite:///{SQLITE_DB_PATH.as_posix()}")
                            sqlite_session_factory = async_sessionmaker(bind=sqlite_engine, expire_on_commit=False)
                            async with sqlite_session_factory() as sqlite_session:
                                sqlite_repo = InspectionRepository(sqlite_session)
                                sqlite_inspections = await sqlite_repo.get_all()
                                for item in sqlite_inspections:
                                    new_ins = ORMInspection(
                                        id=item.id,
                                        building_id=item.building_id,
                                        building_name=item.building_name,
                                        inspection_date=item.inspection_date,
                                        vi_score=item.vi_score,
                                        vi_class=item.vi_class,
                                        pipeline_version=item.pipeline_version,
                                        run_timestamp=item.run_timestamp,
                                        warnings=item.warnings,
                                        s3_key=item.s3_key,
                                        geojson_s3_key=item.geojson_s3_key,
                                        row_version=item.row_version
                                    )
                                    session.add(new_ins)
                                    
                                    defects = await sqlite_repo.get_defects(item.id)
                                    for d in defects:
                                        new_d = ORMDefect(
                                            defect_id=d.defect_id,
                                            inspection_id=d.inspection_id,
                                            type=d.type,
                                            length_cm=d.length_cm,
                                            width_mm=d.width_mm,
                                            area_cm2=d.area_cm2,
                                            centroid_x=d.centroid_x,
                                            centroid_y=d.centroid_y,
                                            severity_class=d.severity_class,
                                            confidence_score=d.confidence_score,
                                            is_false_positive=d.is_false_positive,
                                            fp_confidence=d.fp_confidence,
                                            temporal_status=d.temporal_status,
                                            parent_defect_id=d.parent_defect_id,
                                            delta_width_mm=d.delta_width_mm,
                                            growth_rate_mm_per_month=d.growth_rate_mm_per_month,
                                            growth_acceleration=d.growth_acceleration,
                                            visible_bar_diameter_mm=d.visible_bar_diameter_mm,
                                            estimated_cover_loss_mm=d.estimated_cover_loss_mm,
                                            capacity_reduction_pct=d.capacity_reduction_pct,
                                            orientation_angle=d.orientation_angle,
                                            propagation_rate=d.propagation_rate,
                                            delamination_area_m2=d.delamination_area_m2,
                                            grid_reference=d.grid_reference,
                                            member_type=d.member_type,
                                            recommended_intervention=d.recommended_intervention,
                                            reinspection_date=d.reinspection_date
                                        )
                                        session.add(new_d)
                                await session.commit()
                                logger.info("Successfully seeded PostgreSQL database with local SQLite data.")
                            await sqlite_engine.dispose()
            except Exception as seed_err:
                logger.warning("Failed to seed PostgreSQL database from local SQLite backup: %s", seed_err)

        # SQLite schema migration for civil engineering diagnostic columns
        if not self.is_postgres:
            import sqlite3
            try:
                conn_sync = sqlite3.connect(SQLITE_DB_PATH)
                cursor = conn_sync.cursor()
                cursor.execute("PRAGMA table_info(defects)")
                cols = [c[1] for c in cursor.fetchall()]
                new_cols = [
                    ("visible_bar_diameter_mm", "REAL"),
                    ("estimated_cover_loss_mm", "REAL"),
                    ("capacity_reduction_pct", "REAL"),
                    ("orientation_angle", "REAL"),
                    ("propagation_rate", "TEXT"),
                    ("delamination_area_m2", "REAL"),
                    ("grid_reference", "TEXT"),
                    ("member_type", "TEXT"),
                    ("recommended_intervention", "TEXT"),
                    ("reinspection_date", "TEXT")
                ]
                for col_name, col_type in new_cols:
                    if col_name not in cols:
                        cursor.execute(f"ALTER TABLE defects ADD COLUMN {col_name} {col_type}")
                        logger.info("Migrated SQLite database: added column %s to defects table.", col_name)
                conn_sync.commit()
                conn_sync.close()
            except Exception as migration_err:
                logger.warning("Local SQLite migration failed: %s", migration_err)
        logger.info("Database tables initialized successfully.")

    # --- Synchronous Facades for Backward Compatibility ---
    
    def save_inspection(self, payload: Dict[str, Any]) -> str:
        return run_sync(self.save_inspection_async(payload))

    def get_inspections(self) -> List[Dict[str, Any]]:
        return run_sync(self.get_inspections_async())

    def get_defects(self, inspection_id: str) -> List[Dict[str, Any]]:
        return run_sync(self.get_defects_async(inspection_id))

    # --- Asynchronous Core Implementation ---

    async def save_inspection_async(self, payload: Dict[str, Any]) -> str:
        """Save a complete pipeline run JSON payload into database, uploading reports to S3."""
        building = payload["buildings"][0]
        facade = building["facades"][0]
        
        # Unique inspection key
        inspection_id = f"{building['id']}_{building['inspection_date']}_C{building['cycle_number']}"
        run_ts = payload.get("generated_at", "")
        warnings_str = json.dumps(payload.get("pipeline_warnings", []))
        
        # Convert raw payload to GeoJSON and upload artifacts to object storage
        geojson = self.s3_store.convert_to_geojson(payload)
        s3_json_key = self.s3_store.upload_artifact(building["id"], run_ts, "inspection_results", payload)
        s3_geojson_key = self.s3_store.upload_artifact(building["id"], run_ts, "defects_geojson", geojson)

        async def _do_save():
            async with self.session_factory() as session:
                try:
                    async with session.begin():
                        repo = InspectionRepository(session)
                        # 1. Update or Insert inspection record
                        inspection = await repo.get_by_id(inspection_id)
                        if not inspection:
                            inspection = ORMInspection(id=inspection_id)
                            await repo.add(inspection)
                        else:
                            inspection.row_version += 1  # [RC-11] increment on upsert
                        
                        inspection.building_id = building["id"]
                        inspection.building_name = building["name"]
                        inspection.inspection_date = building["inspection_date"]
                        inspection.vi_score = facade["vi_score"]
                        inspection.vi_class = facade["vi_class"]
                        inspection.pipeline_version = building.get("inspector_module_version", "1.0.0")
                        inspection.run_timestamp = run_ts
                        inspection.warnings = warnings_str
                        inspection.s3_key = s3_json_key
                        inspection.geojson_s3_key = s3_geojson_key
                        
                        # 2. Clear old defects to prevent duplicates on overwrite runs
                        await repo.delete_defects(inspection_id)
                        
                        # 3. Add defects
                        for zone in facade["zones"]:
                            for d in zone["defects"]:
                                accel = float(d.get("growth_acceleration") or 0.0)  # [RC-09] NULL guard
                                
                                defect = ORMDefect(
                                    defect_id=d["defect_id"],
                                    inspection_id=inspection_id,
                                    type=d["type"],
                                    length_cm=d.get("length_cm"),
                                    width_mm=d.get("width_mm"),
                                    area_cm2=d["area_cm2"],
                                    centroid_x=d["centroid_px"]["x"],
                                    centroid_y=d["centroid_px"]["y"],
                                    severity_class=d["severity_class"],
                                    confidence_score=d["confidence_score"],
                                    is_false_positive=1 if d["is_false_positive"] else 0,
                                    fp_confidence=d.get("fp_confidence"),
                                    temporal_status=d.get("temporal_status"),
                                    parent_defect_id=d.get("parent_defect_id"),
                                    delta_width_mm=d.get("delta_width_mm"),
                                    growth_rate_mm_per_month=d.get("growth_rate_mm_per_month"),
                                    growth_acceleration=accel,
                                    visible_bar_diameter_mm=d.get("visible_bar_diameter_mm"),
                                    estimated_cover_loss_mm=d.get("estimated_cover_loss_mm"),
                                    capacity_reduction_pct=d.get("capacity_reduction_pct"),
                                    orientation_angle=d.get("orientation_angle"),
                                    propagation_rate=d.get("propagation_rate"),
                                    delamination_area_m2=d.get("delamination_area_m2"),
                                    grid_reference=d.get("grid_reference"),
                                    member_type=d.get("member_type"),
                                    recommended_intervention=d.get("recommended_intervention"),
                                    reinspection_date=d.get("reinspection_date")
                                )
                                await repo.add_defect(defect)
                except Exception as ex:
                    logger.error("Database session error: %s", str(ex))  # [RC-10]
                    raise

        # [RC-08] Wrap the save operation with retry-on-locked logic
        await _retry_on_locked(_do_save)

        logger.info("Saved inspection run %s to database storage.", inspection_id)
        return inspection_id

    async def get_inspections_async(self) -> List[Dict[str, Any]]:
        """Query and return all historical inspection runs."""
        async with self.session_factory() as session:
            repo = InspectionRepository(session)
            inspections = await repo.get_all()
            
            output = []
            for item in inspections:
                warns = _safe_json(item.warnings)  # [RC-12]
                row = {
                    "id": item.id,
                    "building_id": item.building_id,
                    "building_name": item.building_name,
                    "inspection_date": item.inspection_date,
                    "vi_score": item.vi_score,
                    "vi_class": item.vi_class,
                    "pipeline_version": item.pipeline_version,
                    "run_timestamp": item.run_timestamp,
                    "warnings": warns,
                    "s3_key": item.s3_key,
                    "geojson_s3_key": item.geojson_s3_key
                }
                output.append(row)
            return output

    async def get_defects_async(self, inspection_id: str) -> List[Dict[str, Any]]:
        """Query and return defects for a specific inspection run."""
        async with self.session_factory() as session:
            repo = InspectionRepository(session)
            defects = await repo.get_defects(inspection_id)
            
            output = []
            for item in defects:
                row = {
                    "id": item.id,
                    "defect_id": item.defect_id,
                    "inspection_id": item.inspection_id,
                    "type": item.type,
                    "length_cm": item.length_cm,
                    "width_mm": item.width_mm,
                    "area_cm2": item.area_cm2,
                    "centroid_x": item.centroid_x,
                    "centroid_y": item.centroid_y,
                    "severity_class": item.severity_class,
                    "confidence_score": item.confidence_score,
                    "is_false_positive": item.is_false_positive,
                    "fp_confidence": item.fp_confidence,
                    "temporal_status": item.temporal_status,
                    "parent_defect_id": item.parent_defect_id,
                    "delta_width_mm": item.delta_width_mm,
                    "growth_rate_mm_per_month": item.growth_rate_mm_per_month,
                    "growth_acceleration": item.growth_acceleration,
                    "visible_bar_diameter_mm": item.visible_bar_diameter_mm,
                    "estimated_cover_loss_mm": item.estimated_cover_loss_mm,
                    "capacity_reduction_pct": item.capacity_reduction_pct,
                    "orientation_angle": item.orientation_angle,
                    "propagation_rate": item.propagation_rate,
                    "delamination_area_m2": item.delamination_area_m2,
                    "grid_reference": item.grid_reference,
                    "member_type": item.member_type,
                    "recommended_intervention": item.recommended_intervention,
                    "reinspection_date": item.reinspection_date
                }
                output.append(row)
            return output
