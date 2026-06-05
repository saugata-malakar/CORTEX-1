"""
tasks.py — Asynchronous Background Task Queue (Celery)
======================================================
Dispatches and tracks long-running drone image analysis jobs
on background threads using Celery and Redis.
"""

import os
import logging
from celery import Celery
from src.pipeline import CortexPipeline

# Configure broker and result backend pointing to Redis
REDIS_URL = os.getenv("CORTEX_REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "cortex_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def run_pipeline_task(self, input_dir: str, output_dir: str) -> dict:
    """Executes the master CortexPipeline end-to-end as a background task.

    Updates task states dynamically (PROGRESS) to allow UI polling.
    """
    logger.info("Executing Celery Task ID: %s", self.request.id)
    
    # Step 1: Initialize
    self.update_state(
        state="PROGRESS",
        meta={"progress": 10, "status": "Initializing pipeline config..."}
    )
    
    workspace = os.path.dirname(os.path.abspath(__file__))
    config_path = os.getenv("CORTEX_CONFIG_PATH", os.path.join(os.path.dirname(workspace), "config", "pipeline_config.yaml"))
    
    pipeline = CortexPipeline(config_path)
    
    # Step 2: Running Phase 1 (Ingestion & Pre-processing)
    self.update_state(
        state="PROGRESS",
        meta={"progress": 25, "status": "Phase 1: Ingestion & Pre-processing (Blur checks, CLAHE, SIFT stitching)"}
    )
    
    # Step 3: Running Phase 2 (Defect Detection & Quantification)
    self.update_state(
        state="PROGRESS",
        meta={"progress": 55, "status": "Phase 2: Black-box Cortex Detector wrapping & metric measurements"}
    )
    
    # Step 4: Running Phase 3 (False-Positive Filtering)
    self.update_state(
        state="PROGRESS",
        meta={"progress": 75, "status": "Phase 3: Unified 180-dim feature extraction & XGBoost filtering"}
    )
    
    # Step 5: Running Phase 4 (Output reporting & JSON schema writing)
    self.update_state(
        state="PROGRESS",
        meta={"progress": 90, "status": "Phase 4: Hierarchical JSON serialization & PDF report generation"}
    )
    
    # Run pipeline synchronously in this thread
    try:
        pdf_path = pipeline.run(input_dir, output_dir)
        
        # Step 6: Finalized successfully
        self.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Pipeline completed successfully!"}
        )
        return {
            "status": "success",
            "pdf_report_path": pdf_path,
            "job_id": self.request.id
        }
    except Exception as e:
        logger.error("Celery task execution failed: %s", e, exc_info=True)
        self.update_state(
            state="FAILURE",
            meta={"progress": 0, "status": f"Pipeline failed: {str(e)}"}
        )
        raise e
