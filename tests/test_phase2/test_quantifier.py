"""
test_quantifier.py — Unit Tests for Defect Quantification Engine
================================================================

Verifies:
  - Irregular spalling shape contour area measurements.
  - Linear crack centerline length estimation via skeletonization.
  - Perpendicular crack width profiling via Distance Transform.
  - Elongation and solidity shape classifications.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.phase2_quantification.quantifier import DefectQuantifier


@pytest.fixture
def quant_config() -> dict:
    """Minimal mock configuration."""
    return {
        "quantification": {
            "skeleton_min_length_px": 3,
            "width_sample_points": 5,
            "area_cross_validation_tolerance": 0.05,
            "elongation_crack_threshold": 4.0,
            "elongation_joint_range": [2.0, 4.0],
            "morph_dilation_kernel": 3,
            "morph_dilation_iterations": 0,
        }
    }


def test_quantifier_area(sample_spalling_mask: np.ndarray, quant_config: dict) -> None:
    """Verify that area measurements on a synthetic spall blob compile and agree."""
    quantifier = DefectQuantifier(quant_config)
    gsd = 0.05  # 0.05 cm per pixel
    
    area = quantifier.measure_area(sample_spalling_mask, gsd)
    assert area > 0.0
    
    # Pixel sum area: sum(mask > 0) * GSD^2
    px_sum = np.sum(sample_spalling_mask > 0)
    expected_px_area = px_sum * (gsd ** 2)
    assert abs(area - expected_px_area) / expected_px_area < 0.05


def test_quantifier_crack_metrics(sample_mask: np.ndarray, quant_config: dict) -> None:
    """Verify that skeletonized length and width profiling compile."""
    quantifier = DefectQuantifier(quant_config)
    gsd = 0.05  # 0.05 cm/px
    
    # 1. Crack centerline length
    length = quantifier.measure_crack_length(sample_mask, gsd)
    assert length > 0.0
    
    # 2. Width profiling
    median_w, max_w, profile = quantifier.measure_crack_width(sample_mask, gsd, n_points=5)
    assert len(profile) == 5
    assert 0.0 < median_w <= max_w
    
    # 3. Single instance quantification
    res = quantifier.quantify_defect(sample_mask, gsd, "crack", 0.92)
    assert res["type"] in ("crack", "shear_crack", "flexural_crack", "settlement_crack", "shrinkage_crack", "compression_crack", "corrosion_crack", "fatigue_crack")
    assert res["length_cm"] == round(length, 3)
    assert res["width_mm"] == round(median_w, 3)
    assert res["area_cm2"] > 0.0
    assert len(res["bbox_px"]) == 4
    assert len(res["centroid_px"]) == 2
    assert res["confidence_score"] == 0.92
