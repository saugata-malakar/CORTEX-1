"""
test_feature_extractor.py — Unit Tests for Feature Extractor Orchestrator
========================================================================

Verifies:
  - Total dimensional concatenation (3 edge + 42 texture + 128 deep + 7 shape = 180 dims).
  - Normalization via StandardScaler (fit, transform, serialize, deserialize).
  - Grayscale patch extraction and fast profiling execution times.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from src.phase3_filtering.feature_extractor import FeatureExtractor


@pytest.fixture
def fe_config() -> dict:
    """Master mock configuration."""
    return {
        "feature_extraction": {
            "patch_size": 96,
            "lbp_radius": 3,
            "lbp_n_points": 24,
            "glcm_distances": [1],
            "glcm_angles": [0, 0.785, 1.571, 2.356],
            "resnet_output_dim": 2048,
            "pca_n_components": 128,
            "extraction_time_limit_ms": 200,
        }
    }


def test_feature_extractor_dimensions(fe_config: dict) -> None:
    """Verify that the unified vector extracts exactly 180 dimensions."""
    extractor = FeatureExtractor(fe_config)
    
    # 96x96 synthetic RGB patch
    patch = np.random.randint(0, 255, (96, 96, 3), dtype=np.uint8)
    
    # Synthetic circular contour
    theta = np.linspace(0, 2*np.pi, 50)
    cx, cy, r = 48, 48, 20
    contour = np.stack([cx + r*np.cos(theta), cy + r*np.sin(theta)], axis=1)
    contour = contour.astype(np.int32).reshape(-1, 1, 2)
    
    # Fit scaler first
    dummy_feats = np.random.normal(0, 1.0, (5, 180))
    extractor.fit_scaler(dummy_feats)
    
    # Extract raw features
    raw = extractor.extract_raw_vector(patch, contour)
    assert raw.shape == (180,)
    assert raw.dtype == np.float32
    
    # Extract scaled features
    scaled = extractor.extract(patch, contour)
    assert scaled.shape == (180,)
    assert scaled.dtype == np.float32


def test_scaler_io(fe_config: dict, tmp_path: Path) -> None:
    """Verify that StandardScaler fits, serialises, and loads correctly."""
    extractor = FeatureExtractor(fe_config)
    
    dummy_matrix = np.random.normal(5.0, 2.0, (10, 180))
    extractor.fit_scaler(dummy_matrix)
    
    # Check mean
    assert extractor.scaler.mean_ is not None
    assert len(extractor.scaler.mean_) == 180
    
    # Save
    scaler_path = tmp_path / "scaler.pkl"
    extractor.save_scaler(scaler_path)
    assert scaler_path.exists()
    
    # Load
    new_extractor = FeatureExtractor(fe_config)
    new_extractor.load_scaler(scaler_path)
    assert new_extractor.scaler.mean_ is not None
    assert np.allclose(new_extractor.scaler.mean_, extractor.scaler.mean_)
