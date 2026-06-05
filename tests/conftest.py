"""
Shared pytest fixtures for the Cortex Structural Defect Pipeline.

Provides reusable test fixtures that create synthetic images, masks,
metadata dicts, configuration objects, and temporary output directories.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Attempt to import project modules; tests still collect if deps are missing
# ---------------------------------------------------------------------------
try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore[assignment]

try:
    from src.utils.config_loader import PipelineConfig
except ImportError:
    PipelineConfig = None  # type: ignore[assignment,misc]


# ===================================================================
# Fixtures — synthetic images
# ===================================================================

@pytest.fixture
def sample_image() -> np.ndarray:
    """Create a synthetic 640×480 BGR test image with visual features.

    The image contains a gradient background, a white rectangle, and
    a diagonal line to give non-trivial texture for blur/feature tests.
    """
    h, w = 480, 640
    # Gradient background (blue channel ramp)
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 0] = np.tile(np.linspace(50, 200, w, dtype=np.uint8), (h, 1))
    img[:, :, 1] = 100
    img[:, :, 2] = 150

    if cv2 is not None:
        # White rectangle
        cv2.rectangle(img, (100, 80), (540, 400), (255, 255, 255), 2)
        # Diagonal line (simulates a crack)
        cv2.line(img, (120, 100), (520, 380), (30, 30, 30), 2)

    return img


@pytest.fixture
def sample_grayscale_image(sample_image: np.ndarray) -> np.ndarray:
    """Grayscale version of the sample image."""
    if cv2 is not None:
        return cv2.cvtColor(sample_image, cv2.COLOR_BGR2GRAY)
    return np.mean(sample_image, axis=2).astype(np.uint8)


@pytest.fixture
def sample_image_path(
    sample_image: np.ndarray,
    tmp_path: Path,
) -> Path:
    """Save the sample image to a temporary JPEG file and return its path."""
    p = tmp_path / "test_frame.jpg"
    if cv2 is not None:
        cv2.imwrite(str(p), sample_image)
    else:
        # Fallback: write raw bytes (won't be a valid JPEG, but path exists)
        p.write_bytes(sample_image.tobytes())
    return p


# ===================================================================
# Fixtures — masks
# ===================================================================

@pytest.fixture
def sample_mask() -> np.ndarray:
    """Create a synthetic 480×640 binary mask with a crack-like stripe.

    A diagonal stripe ~4 px wide simulates a detected crack region.
    """
    h, w = 480, 640
    mask = np.zeros((h, w), dtype=np.uint8)
    # Draw a diagonal stripe
    for offset in range(-2, 3):
        for i in range(min(h, w)):
            y = i
            x = i + offset
            if 0 <= x < w and 0 <= y < h:
                mask[y, x] = 255
    return mask


@pytest.fixture
def sample_spalling_mask() -> np.ndarray:
    """Create a synthetic spalling mask with an irregular blob."""
    h, w = 480, 640
    mask = np.zeros((h, w), dtype=np.uint8)
    if cv2 is not None:
        cv2.ellipse(mask, (320, 240), (80, 50), 30, 0, 360, 255, -1)
    else:
        # Simple rectangle fallback
        mask[200:280, 260:380] = 255
    return mask


# ===================================================================
# Fixtures — metadata
# ===================================================================

@pytest.fixture
def sample_metadata() -> Dict[str, Any]:
    """Return a mock EXIF metadata dictionary.

    Mimics the structure produced by ``piexif.load()`` with GPS IFD.
    """
    return {
        "0th": {
            271: b"DJI",                   # Make
            272: b"FC7303",                 # Model
        },
        "Exif": {
            33434: (1, 500),               # ExposureTime: 1/500 s
            33437: (28, 10),               # FNumber: 2.8
            37386: (8800, 1000),           # FocalLength: 8.8 mm
        },
        "GPS": {
            1: b"N",                       # GPSLatitudeRef
            2: ((22, 1), (18, 1), (3600, 100)),  # GPSLatitude: 22°18'36"
            3: b"E",                       # GPSLongitudeRef
            4: ((87, 1), (19, 1), (4800, 100)),  # GPSLongitude: 87°19'48"
            5: 0,                          # GPSAltitudeRef: above sea level
            6: (50000, 1000),              # GPSAltitude: 50.0 m
        },
        "1st": {},
        "thumbnail": None,
    }


@pytest.fixture
def sample_camera_params() -> Dict[str, float]:
    """Return mock camera intrinsic parameters for GSD computation."""
    return {
        "focal_length_mm": 8.8,
        "sensor_width_mm": 13.2,
        "image_width_px": 4056,
        "altitude_m": 50.0,
    }


# ===================================================================
# Fixtures — configuration
# ===================================================================

@pytest.fixture
def config(tmp_path: Path) -> "PipelineConfig | Dict[str, Any]":
    """Create a minimal pipeline configuration YAML and load it.

    Falls back to a plain dict if ``PipelineConfig`` is unavailable.
    """
    config_content = """\
quality_gate:
  blur_threshold: 100.0
  exposure_low: 40
  exposure_high: 220

enhancement:
  clahe_clip_limit: 2.0
  clahe_tile_grid: [8, 8]
  sharpen: true

stitching:
  detector: ORB
  match_ratio: 0.75
  ransac_threshold: 5.0

gsd:
  sensor_width_mm: 13.2
  focal_length_mm: 8.8
  default_altitude_m: 50.0

quantification:
  crack_width_bins: [0.1, 0.3, 0.5, 1.0]
  spalling_area_threshold_cm2: 100.0
  vindex_weights:
    crack_severity: 0.4
    spalling_extent: 0.3
    spatial_density: 0.3

filtering:
  confidence_threshold: 0.7
  xgboost:
    n_estimators: 200
    max_depth: 6
    learning_rate: 0.1
  shap:
    max_display: 15

reporting:
  output_format: pdf
  logo_path: null
"""
    cfg_path = tmp_path / "pipeline_config.yaml"
    cfg_path.write_text(config_content, encoding="utf-8")

    if PipelineConfig is not None:
        return PipelineConfig(str(cfg_path))

    # Fallback: return raw dict
    import yaml
    return yaml.safe_load(config_content)


# ===================================================================
# Fixtures — temporary directories
# ===================================================================

@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Create and return a temporary output directory for test artifacts."""
    out = tmp_path / "test_output"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture
def tmp_raw_dir(sample_image: np.ndarray, tmp_path: Path) -> Path:
    """Create a temporary ``raw/`` directory populated with sample images."""
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    if cv2 is not None:
        for i in range(3):
            cv2.imwrite(str(raw / f"frame_{i:03d}.jpg"), sample_image)
    return raw
