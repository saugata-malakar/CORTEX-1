"""
scratch_dryrun.py — End-to-End Validation Run of the Cortex Pipeline
=====================================================================
Creates synthetic UAV images with complete EXIF metadata, runs them
through the master pipeline, and verifies output generation.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
import numpy as np
import cv2
import piexif

from src.pipeline import CortexPipeline
from src.phase4_reporting.json_writer import JSONWriter

def create_exif_bytes() -> bytes:
    """Helper to construct DJI Phantom 4 Pro mock EXIF bytes."""
    gps_lat = ((22, 1), (18, 1), (3600, 100))  # 22 deg 18 min 36 sec
    gps_lon = ((87, 1), (19, 1), (4800, 100))  # 87 deg 19 min 48 sec
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"DJI",
            piexif.ImageIFD.Model: b"FC7303",
        },
        "Exif": {
            piexif.ExifIFD.ExposureTime: (1, 500),
            piexif.ExifIFD.FNumber: (28, 10),
            piexif.ExifIFD.FocalLength: (8800, 1000),  # 8.8 mm
            piexif.ExifIFD.DateTimeOriginal: b"2026:06:02 12:00:00",
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: gps_lat,
            piexif.GPSIFD.GPSLongitudeRef: b"E",
            piexif.GPSIFD.GPSLongitude: gps_lon,
            piexif.GPSIFD.GPSAltitudeRef: 0,
            piexif.GPSIFD.GPSAltitude: (15000, 1000),  # 15.0 m
        }
    }
    return piexif.dump(exif_dict)

def build_synthetic_dataset(raw_dir: Path) -> None:
    """Generates 3 synthetic DJI frames with rich features and EXIF tags."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    h, w = 480, 640
    
    # Base background gradient
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 0] = np.tile(np.linspace(50, 200, w, dtype=np.uint8), (h, 1))
    img[:, :, 1] = 100
    img[:, :, 2] = 150
    
    # Image 1: simple wall features
    img1 = img.copy()
    cv2.rectangle(img1, (100, 80), (540, 400), (255, 255, 255), 2)
    cv2.line(img1, (120, 100), (520, 380), (30, 30, 30), 2)
    
    # Image 2: slightly shifted for stitching matching
    img2 = img.copy()
    cv2.rectangle(img2, (120, 80), (560, 400), (255, 255, 255), 2)
    cv2.line(img2, (140, 100), (540, 380), (30, 30, 30), 2)
    
    # Image 3: another slightly shifted view
    img3 = img.copy()
    cv2.rectangle(img3, (140, 80), (580, 400), (255, 255, 255), 2)
    cv2.line(img3, (160, 100), (560, 380), (30, 30, 30), 2)
    
    frames = [img1, img2, img3]
    exif_bytes = create_exif_bytes()
    
    for idx, frame in enumerate(frames):
        filepath = raw_dir / f"frame_{idx:03d}.jpg"
        # Save BGR image
        cv2.imwrite(str(filepath), frame)
        # Insert EXIF
        piexif.insert(exif_bytes, str(filepath))
        print(f"Created synthetic drone image: {filepath}")

def main() -> None:
    print("--- Starting End-to-End Validation Run ---")
    
    workspace_root = Path(__file__).parent.resolve()
    raw_dir = workspace_root / "data" / "raw"
    reports_dir = workspace_root / "data" / "reports"
    
    # Clean old directories
    if raw_dir.exists():
        try:
            shutil.rmtree(raw_dir)
        except PermissionError:
            pass
    if reports_dir.exists():
        try:
            shutil.rmtree(reports_dir)
        except PermissionError:
            pass  # Windows lock — skip during live server run
        
    # Build raw input images
    build_synthetic_dataset(raw_dir)
    
    config_path = str(workspace_root / "config" / "pipeline_config.yaml")
    
    print("\nInitializing Master Pipeline Orchestrator...")
    pipeline = CortexPipeline(config_path)
    
    print("\nRunning End-to-End Pipeline on Raw Ingestion Directory...")
    pdf_path = pipeline.run(str(raw_dir), str(reports_dir))
    
    print("\nVerifying Generated Outputs...")
    json_path = reports_dir / "inspection_results.json"
    
    # 1. Check file existence
    if not json_path.exists():
        raise FileNotFoundError(f"Failed: {json_path} was not created!")
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"Failed: {pdf_path} was not created!")
        
    print(f"Success: JSON data generated at {json_path} (size: {json_path.stat().st_size} bytes)")
    print(f"Success: PDF Report compiled at {pdf_path} (size: {Path(pdf_path).stat().st_size} bytes)")
    
    # 2. Validate JSON with schema
    print("\nValidating output JSON against json_output_schema.json...")
    schema_path = workspace_root / "config" / "json_output_schema.json"
    writer = JSONWriter(str(schema_path))
    
    import json
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    writer.validate(data)
    print("JSON successfully validated against strict schema!")
    
    print("\n--- Dry-Run and Validation Finished Successfully! ---")

if __name__ == "__main__":
    main()
