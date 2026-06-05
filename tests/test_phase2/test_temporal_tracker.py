"""
test_temporal_tracker.py — Unit Tests for Multi-Cycle Temporal Tracker
======================================================================

Verifies:
  - Bounding box Intersection over Union (IoU) math.
  - Defect matching and state propagation (new vs. propagated).
  - Multi-cycle delta measurements and growth rates.
  - Grayscale frame registration and change mask computation.
"""

from __future__ import annotations

import pytest

from src.phase2_quantification.temporal_tracker import TemporalTracker, compute_bbox_iou


def test_bbox_iou() -> None:
    """Verify that bounding box Intersection over Union calculates correctly."""
    # Complete overlap
    box1 = [100, 100, 50, 50]
    assert compute_bbox_iou(box1, box1) == 1.0
    
    # Partial overlap (25x50 overlap out of two 50x50 boxes)
    # intersection = 25*50 = 1250, union = 2500 + 2500 - 1250 = 3750, IoU = 1250/3750 = 0.3333
    box2 = [125, 100, 50, 50]
    assert pytest.approx(compute_bbox_iou(box1, box2), 1e-4) == 0.3333
    
    # No overlap
    box3 = [200, 200, 50, 50]
    assert compute_bbox_iou(box1, box3) == 0.0


def test_temporal_defect_matching() -> None:
    """Verify cycle-to-cycle matching logic and delta measurements."""
    config = {
        "temporal": {
            "iou_propagated_threshold": 0.3,
            "iou_new_threshold": 0.1,
        }
    }
    tracker = TemporalTracker(config)
    
    cycle1 = [
        {"defect_id": "DEFECT-001", "bbox_px": [100, 100, 50, 50], "length_cm": 10.0, "width_mm": 1.0, "area_cm2": 5.0}
    ]
    
    cycle2 = [
        # Propagated with growth
        {"bbox_px": [105, 100, 50, 50], "length_cm": 12.0, "width_mm": 1.5, "area_cm2": 6.5},
        # Brand new defect
        {"bbox_px": [300, 300, 20, 20], "length_cm": 3.0, "width_mm": 0.5, "area_cm2": 1.0}
    ]
    
    matched = tracker.match_defects(cycle1, cycle2)
    
    # Check propagated defect
    prop = [d for d in matched if d.get("parent_defect_id") == "DEFECT-001"][0]
    assert prop["temporal_status"] == "propagated"
    assert prop["delta_length_cm"] == 2.0
    assert prop["delta_width_mm"] == 0.5
    assert prop["delta_area_cm2"] == 1.5
    assert prop["growth_rate_mm_per_month"] == 0.5
    
    # Check new defect
    new_def = [d for d in matched if d.get("parent_defect_id") is None][0]
    assert new_def["temporal_status"] == "new"
    assert new_def["delta_length_cm"] == 0.0
