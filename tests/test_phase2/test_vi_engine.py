"""
test_vi_engine.py — Unit Tests for Vulnerability Index (VI) Engine
==================================================================

Verifies:
  - Defect-level individual score weighting and width multiplier logic.
  - Facade-level composite scoring and area normalization.
  - Aligned IS 13311 class and maintenance recommendation maps.
  - Spatial zone aggregation across the 4x4 coordinate grid.
"""

from __future__ import annotations

import pytest

from src.phase2_quantification.vi_engine import VulnerabilityIndexEngine


@pytest.fixture
def vi_config() -> dict:
    """Minimal mock configuration."""
    return {
        "vulnerability_index": {
            "defect_weights": {"crack": 1.0, "spalling": 0.8},
            "severity_multipliers": {"hairline": 0.3, "fine": 0.5, "medium": 0.8, "wide": 1.0},
            "width_thresholds_mm": {"hairline_max": 0.2, "fine_max": 1.0, "medium_max": 5.0},
            "class_thresholds": {"minor_max": 20, "moderate_max": 40, "significant_max": 60, "severe_max": 80},
            "facade_grid": "4x4",
        }
    }


def test_vi_calculations(vi_config: dict) -> None:
    """Verify individual and composite VI metrics compile correctly."""
    engine = VulnerabilityIndexEngine(vi_config)
    
    # 1. Defect level VI
    crack = {
        "type": "crack",
        "width_mm": 0.5,  # Fine crack
        "area_cm2": 10.0,
    }
    vi_contrib = engine.compute_defect_vi(crack)
    # wi (1.0) * si (0.5) * Ai (10) = 5.0
    assert vi_contrib == 5.0
    
    # 2. Facade level composite VI
    defects = [crack, crack]
    facade_area = 1000.0  # cm2
    score = engine.compute_facade_vi(defects, facade_area)
    # (5.0 + 5.0) / 1000 * 100 = 1.0
    assert score == 1.0


def test_vi_severity_recommendations(vi_config: dict) -> None:
    """Verify that IS 13311 condition mapping compiles properly."""
    engine = VulnerabilityIndexEngine(vi_config)
    
    c_class = engine.classify_vi(50.0)
    assert c_class == "Class III (Significant)"
    
    recs = engine.get_recommendations(c_class)
    assert "timeline" in recs
    assert "action" in recs


def test_zone_aggregation(vi_config: dict) -> None:
    """Verify spatial grid cell assignment (A1-D4)."""
    engine = VulnerabilityIndexEngine(vi_config)
    
    mosaic_shape = (1000, 1000)
    facade_area = 100000.0
    
    defects = [
        {"type": "crack", "centroid_px": [100, 100], "area_cm2": 5.0, "width_mm": 0.1}, # A1
        {"type": "spalling", "centroid_px": [900, 900], "area_cm2": 20.0, "width_mm": 6.0}, # D4
    ]
    
    zones = engine.aggregate_zones(mosaic_shape, defects, facade_area)
    
    assert zones["A1"]["defect_count"] == 1
    assert zones["D4"]["defect_count"] == 1
    assert zones["B2"]["defect_count"] == 0
    assert zones["A1"]["zone_vi"] > 0.0
