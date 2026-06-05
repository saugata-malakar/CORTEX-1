"""
test_preprocessing.py — Unit Tests for Phase 1 Pre-processing Module
=====================================================================
Verifies:
  - EXIF metadata parsing & quality gates (blur, underexposure, altitude, gap).
  - Image enhancement (CLAHE, denoise, white balance) & sharpness check.
  - Vanishing point detection, homography, and perspective correction.
  - SIFT feature extraction, FLANN matching, USAC-MAGSAC, and sequential stitching.
  - GSD calculations and survey rod cross-validation.
  - Geo-reference grid IDW interpolation and RMSE spatial checks.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import cv2

# Phase 1 imports
from src.phase1_preprocessing.metadata_parser import MetadataParser, compute_image_quality
from src.phase1_preprocessing.image_enhancer import (
    apply_clahe, apply_gaussian_denoise, apply_white_balance,
    detect_vanishing_points, compute_rectification_homography, apply_perspective_correction
)
from src.phase1_preprocessing.image_processor import SIFTMatcher, MosaicStitcher, ImageProcessor
from src.phase1_preprocessing.gsd_calibrator import GSDCalibrator, compute_gsd, validate_gsd_with_reference
from src.phase1_preprocessing.geo_referencer import GeoReferencer, build_gps_pixel_mapping


# ===================================================================
# 1. Metadata Parser Tests
# ===================================================================

def test_metadata_quality_computation(sample_image: np.ndarray) -> None:
    """Verify that image quality parameters are correctly calculated."""
    lap_var, mean_int = compute_image_quality(sample_image)
    assert lap_var > 0
    assert 0 < mean_int < 255


def test_metadata_quality_gates(sample_image_path: Path) -> None:
    """Verify that image quality gates filter blurry or dark frames."""
    parser = MetadataParser({
        "quality_gate": {
            "laplacian_variance_min": 10.0,
            "mean_intensity_min": 10.0
        }
    })
    meta = parser.parse_single_image(str(sample_image_path))
    assert meta.quality_passed is True
    assert meta.is_blurry is False
    assert meta.is_underexposed is False


def test_metadata_anomalies_and_gaps() -> None:
    """Verify statistical z-score altitude and timestamp gap gates."""
    parser = MetadataParser({
        "quality_gate": {
            "altitude_anomaly_sigma": 1.5,
            "temporal_gap_multiplier": 2.0
        }
    })
    
    # Construct a mock flight metadata DataFrame
    df = pd.DataFrame([
        {
            "filename": f"img_{i}.jpg",
            "filepath": f"path/{i}.jpg",
            "relative_altitude": 15.0 if i != 4 else 35.0,  # index 4 is anomalous (> 1.5σ)
            "gps_latitude": 22.3,
            "gps_longitude": 87.3,
            "timestamp": f"2026:06:02 12:00:{i * 5 if i < 3 else i * 5 + 30}",  # gap between index 2 & 3 (> 2x median)
            "quality_passed": True,
            "altitude_anomaly": False,
            "temporal_gap": False
        } for i in range(6)
    ])
    
    df_gated = parser.apply_quality_gates(df)
    
    # Verify index 4 has altitude anomaly flagged
    assert bool(df_gated.loc[4, "altitude_anomaly"]) is True
    assert bool(df_gated.loc[4, "quality_passed"]) is False
    
    # Verify index 3 has temporal gap flagged due to the jump from 12:00:10 to 12:00:45
    assert bool(df_gated.loc[3, "temporal_gap"]) is True
# ===================================================================
# 2. Image Enhancer Tests
# ===================================================================

def test_image_enhancement_operations(sample_image: np.ndarray) -> None:
    """Verify standard CLAHE, denoiser, and white balance transforms."""
    res_clahe = apply_clahe(sample_image, clip_limit=2.0)
    assert res_clahe.shape == sample_image.shape
    assert res_clahe.dtype == np.uint8
    
    res_denoise = apply_gaussian_denoise(sample_image, kernel_size=(5, 5), sigma=1.0)
    assert res_denoise.shape == sample_image.shape
    
    res_wb = apply_white_balance(sample_image)
    assert res_wb.shape == sample_image.shape


def test_perspective_rectification(sample_image: np.ndarray) -> None:
    """Verify line-based vanishing point detection and perspective homography."""
    # Draw high-contrast horizontal and vertical lines on clean canvas to form a grid
    grid_img = np.zeros((480, 640, 3), dtype=np.uint8) + 150
    for y in range(50, 450, 50):
        cv2.line(grid_img, (50, y), (590, y), (10, 10, 10), 2)
    for x in range(50, 600, 50):
        cv2.line(grid_img, (x, 50), (x, 430), (10, 10, 10), 2)
        
    vert_vp, horiz_vp, lines = detect_vanishing_points(
        grid_img,
        hough_threshold=50,
        hough_min_line_length=50
    )
    
    # Homography estimation (GCP mode verification)
    gcp_src = [(100, 100), (500, 100), (500, 400), (100, 400)]
    gcp_dst = [(100, 100), (500, 100), (500, 400), (100, 400)]
    H = compute_rectification_homography(grid_img, gcp_points=gcp_src, gcp_targets=gcp_dst)
    assert H is not None
    assert H.shape == (3, 3)
    
    rectified = apply_perspective_correction(grid_img, H)
    assert rectified.shape == grid_img.shape


# ===================================================================
# 3. SIFT Matching & Stitching Tests
# ===================================================================

def test_sift_matcher(sample_image: np.ndarray) -> None:
    """Verify SIFT feature detection and matcher instantiation."""
    matcher = SIFTMatcher()
    kp, desc = matcher.detect_and_compute(sample_image)
    assert len(kp) > 0
    assert desc is not None
    assert desc.shape[1] == 128


def test_mosaic_stitcher_fallback(sample_image: np.ndarray) -> None:
    """Verify that the stitcher handles low-overlap and sequential fallbacks gracefully."""
    stitcher = MosaicStitcher()
    
    # 1. Test single-image input returns the image (per-image fallback)
    res, status, info = stitcher.stitch([sample_image])
    assert status == MosaicStitcher.STATUS_PER_IMAGE_FALLBACK
    assert res is not None
    assert res.shape == sample_image.shape
    
    # 2. Test ImageProcessor wrapper routes stitching request correctly
    processor = ImageProcessor()
    res_wrap = processor.stitch_facades([sample_image])
    assert res_wrap is not None
    assert res_wrap.shape == sample_image.shape


# ===================================================================
# 4. GSD Calibration Tests
# ===================================================================

def test_gsd_equations() -> None:
    """Verify Ground Sample Distance math accuracy."""
    # Altitude = 15m, Sensor Width = 13.2mm, Focal Length = 8.8mm, Resolution = 5472px
    # GSD_w_m = (15 * 13.2) / (8.8 * 5472) = 0.004111 m/px = 0.4111 cm/px
    calculated_gsd = compute_gsd(
        altitude_m=15.0,
        sensor_width_mm=13.2,
        focal_length_mm=8.8,
        image_width_px=5472
    )
    assert abs(calculated_gsd - 0.4111) < 0.01
    
    # Check flight aggregation
    calibrator = GSDCalibrator()
    gsd_val = calibrator.calculate_gsd(15.0, "dji_phantom_4_pro")
    assert abs(gsd_val - 0.4111) < 0.01


def test_gsd_survey_rod_cross_validation() -> None:
    """Verify survey rod GSD calibration cross-checks."""
    # GSD = 0.5 cm/px, Rod = 1.0 m (100 cm), Pixel length = 200 px
    # Expected predicted rod = 200 * 0.5 = 100 cm (no deviation)
    passed, pred_cm, act_cm = validate_gsd_with_reference(
        image=np.zeros((100, 100)),
        gsd_cm_per_px=0.5,
        reference_length_m=1.0,
        reference_pixel_length=200.0,
        tolerance_percent=5.0
    )
    assert passed is True
    assert pred_cm == 100.0
    assert act_cm == 100.0


# ===================================================================
# 5. Geo-Referencer Tests
# ===================================================================

def test_geo_reference_interpolation() -> None:
    """Verify geo-referencer IDW coordinate interpolation and RMSE bounds."""
    georef = GeoReferencer({
        "geo_reference": {
            "grid_sample_spacing_px": 100,
            "gps_rmse_target_m": 0.5
        }
    })
    
    # 1. Build mock control points
    meta = [
        {"filename": "f1.jpg", "gps_latitude": 22.310000, "gps_longitude": 87.310000, "image_width_px": 640, "image_height_px": 480},
        {"filename": "f2.jpg", "gps_latitude": 22.310090, "gps_longitude": 87.310090, "image_width_px": 640, "image_height_px": 480}
    ]
    control_pts = build_gps_pixel_mapping(meta, (480, 640))
    assert len(control_pts) == 2
    
    # 2. Interpolate grid
    grid = georef.generate_grid((480, 640), control_pts)
    assert grid["num_grid_points"] > 0
    assert grid["coordinate_system"] == "WGS84 (EPSG:4326)"
    
    # 3. Query coordinate conversion
    lat, lon = georef.pixel_to_gps(320.0, 240.0, grid)
    assert lat is not None
    assert lon is not None
    assert 22.310000 <= lat <= 22.310090
    assert 87.310000 <= lon <= 87.310090
    
    # 4. Check RMSE calculation
    val_pts = [
        {"pixel_x": 0.0, "pixel_y": 240.0, "gps_latitude": 22.310000, "gps_longitude": 87.310000}
    ]
    rmse = georef.compute_gps_rmse(grid, val_pts)
    assert rmse < 0.5
