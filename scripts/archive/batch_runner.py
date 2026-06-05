"""
batch_runner.py — Overnight Batch Inspection Job Runner
========================================================
Processes multiple building facade drone frames sequentially in a single batch,
generating structural reports and saving data stores for morning analysis.
"""

import os
import sys
import time
import argparse
from pathlib import Path
import structlog

from src.pipeline import CortexPipeline
from src.utils.logger import configure_logger

configure_logger()
logger = structlog.get_logger("batch_runner")


def run_batch(input_root: str, output_root: str):
    logger.info("Starting Cortex Structural Intelligence Batch Job Runner...")
    
    in_path = Path(input_root)
    out_path = Path(output_root)
    
    if not in_path.exists():
        logger.error("Batch input root directory does not exist", path=str(in_path))
        sys.exit(1)
        
    out_path.mkdir(parents=True, exist_ok=True)
    
    # Retrieve all subdirectories representing building runs
    building_dirs = [d for d in in_path.iterdir() if d.is_dir()]
    if not building_dirs:
        # If no subdirs exist, fall back to running on the root input dir as single run
        logger.warning("No subdirectories found in batch root. Processing input directory as single run.", input_dir=str(in_path))
        building_dirs = [in_path]
        
    logger.info("Found directories to process in batch", count=len(building_dirs), directories=[d.name for d in building_dirs])
    
    success_count = 0
    failure_count = 0
    config_path = os.path.abspath("config/pipeline_config.yaml")
    
    try:
        pipeline = CortexPipeline(config_path)
    except Exception as e:
        logger.critical("Failed to initialize pipeline orchestrator for batch runs", error=str(e))
        sys.exit(1)
        
    for idx, b_dir in enumerate(building_dirs):
        b_name = b_dir.name
        b_out = out_path / b_name
        b_out.mkdir(parents=True, exist_ok=True)
        
        logger.info("Processing batch job item", index=idx+1, total=len(building_dirs), building=b_name)
        start_ts = time.time()
        
        try:
            pdf_report = pipeline.run(str(b_dir), str(b_out))
            elapsed = time.time() - start_ts
            success_count += 1
            logger.info("Successfully processed batch item", building=b_name, elapsed_seconds=round(elapsed, 2), report_pdf=pdf_report)
        except Exception as e:
            elapsed = time.time() - start_ts
            failure_count += 1
            logger.error("Failed to process batch item", building=b_name, elapsed_seconds=round(elapsed, 2), error=str(e))
            
    logger.info("Cortex Batch Job Runner execution completed", processed=len(building_dirs), succeeded=success_count, failed=failure_count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cortex Overnight Batch Runner")
    parser.add_argument("--input-root", type=str, default="data/raw", help="Root directory containing subfolders for each building")
    parser.add_argument("--output-root", type=str, default="data/reports/batch", help="Output directory for generated reports")
    args = parser.parse_args()
    
    run_batch(args.input_root, args.output_root)
