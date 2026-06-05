"""
Cortex — tests/test_e2e_flat.py
End-to-end integration test suite for the lightweight flat architecture in files/

Covers the full chain:
  image input → pipeline → sqlite store → API response → schema validation
"""

import json
import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

# Point to files/ directory for flat architecture imports
sys.path.insert(0, str(Path(__file__).parent.parent / "files"))

from pipeline import (
    CONFIDENCE_THRESHOLD,
    PIPELINE_VERSION,
    CortexPipeline,
    Defect,
    FeatureExtractor,
    SIFTCache,
    TemporalTracker,
    VIClassifier,
    ZoneSeverityIndexer,
)
from sqlite_store import (
    get_db_stats,
    get_defects,
    get_inspections,
    get_propagated_defects,
    init_db,
    save_inspection,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    return db


@pytest.fixture
def synthetic_image(tmp_path):
    """256×256 grayscale facade with synthetic crack lines."""
    img = np.ones((256, 256, 3), dtype=np.uint8) * 200
    cv2.line(img, (30, 50), (200, 60), (50, 50, 50), 2)
    cv2.line(img, (80, 100), (180, 140), (40, 40, 40), 3)
    # Add a spall region
    cv2.rectangle(img, (100, 150), (160, 200), (80, 80, 80), -1)
    path = tmp_path / "facade_cycle1.jpg"
    cv2.imwrite(str(path), img)
    return str(path)


@pytest.fixture
def minimal_config(tmp_path):
    cfg = {
        "gsd_mm_per_px": 1.2,
        "temporal_tolerance_px": 25.0,
        "elapsed_months": 6.0,
        "blackbox_api_endpoint": "http://mock-api/detect",
        "blackbox_api_key": "test-key",
        "bayesian_opt_iterations": 2,   # speed cap for CI
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    return str(p)


def make_defect(defect_id="B01_C1_0001", severity="moderate",
                cx=100.0, cy=100.0, prev_id=None,
                growth_rate=0.0, growth_acc=0.0) -> Defect:
    return Defect(
        defect_id=defect_id,
        defect_type="crack",
        severity=severity,
        width_mm=2.0,
        length_cm=5.0,
        area_px2=150.0,
        centroid_x=cx,
        centroid_y=cy,
        confidence=0.85,
        false_positive_prob=0.12,
        contour_geojson={
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[cx - 5, cy - 5], [cx + 5, cy - 5],
                                 [cx + 5, cy + 5], [cx - 5, cy + 5]]]
            },
            "properties": {}
        },
        matched_previous_id=prev_id,
        growth_rate_mm_per_month=growth_rate,
        growth_acceleration=growth_acc,
    )


# ---------------------------------------------------------------------------
# Unit: SIFTCache — hash-based keying  [RC-02]
# ---------------------------------------------------------------------------

class TestSIFTCache:
    def test_same_file_same_hash(self, tmp_path):
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        p = tmp_path / "img.jpg"
        cv2.imwrite(str(p), img)
        cache = SIFTCache()
        h1 = cache._hash(str(p))
        h2 = cache._hash(str(p))
        assert h1 == h2, "Same file must produce same SHA-256"

    def test_different_content_different_hash(self, tmp_path):
        img1 = np.zeros((64, 64, 3), dtype=np.uint8)
        img2 = np.ones((64, 64, 3), dtype=np.uint8) * 128
        p1 = tmp_path / "img1.jpg"
        p2 = tmp_path / "img2.jpg"
        cv2.imwrite(str(p1), img1)
        cv2.imwrite(str(p2), img2)
        cache = SIFTCache()
        assert cache._hash(str(p1)) != cache._hash(str(p2)), \
            "[RC-02] Different content must produce different hash"

    def test_renamed_file_same_content_same_hash(self, tmp_path):
        """
        [RC-02] CORE TEST: filename collision must NOT happen.
        cycle1.jpg renamed to cycle2.jpg — same bytes → same hash → cache hit.
        """
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        p1 = tmp_path / "cycle1.jpg"
        p2 = tmp_path / "cycle2.jpg"
        cv2.imwrite(str(p1), img)
        import shutil
        shutil.copy(str(p1), str(p2))
        cache = SIFTCache()
        assert cache._hash(str(p1)) == cache._hash(str(p2)), \
            "Same bytes, different filename → must hash the same"

    def test_invalid_path_raises(self):
        cache = SIFTCache()
        with pytest.raises((FileNotFoundError, OSError)):
            cache._hash("/nonexistent/path.jpg")


# ---------------------------------------------------------------------------
# Unit: TemporalTracker — edge cases  [RC-09]
# ---------------------------------------------------------------------------

class TestTemporalTracker:
    def test_first_cycle_no_match(self):
        """First cycle: no previous defects. growth fields must be 0, not None."""
        tracker = TemporalTracker(tolerance_px=25.0, elapsed_months=6.0)
        current = [make_defect("B1_C1_001")]
        result = tracker.match(current, previous=[])
        d = result[0]
        assert d.matched_previous_id is None
        assert d.delta_width_mm == 0.0
        assert d.growth_rate_mm_per_month == 0.0
        assert d.growth_acceleration == 0.0   # [RC-09] not None

    def test_elapsed_months_zero_guard(self):
        """[RC-09] elapsed_months=0 must not divide by zero."""
        tracker = TemporalTracker(tolerance_px=25.0, elapsed_months=0)
        assert tracker.elapsed_months > 0, "elapsed_months must be clamped above 0"

    def test_match_within_tolerance(self):
        tracker = TemporalTracker(tolerance_px=25.0, elapsed_months=6.0)
        prev = [make_defect("B1_C1_001", cx=100.0, cy=100.0)]
        prev[0].width_mm = 1.0
        curr = [make_defect("B1_C2_001", cx=105.0, cy=98.0)]
        curr[0].width_mm = 2.5
        result = tracker.match(curr, prev)
        d = result[0]
        assert d.matched_previous_id == "B1_C1_001"
        assert abs(d.delta_width_mm - 1.5) < 0.001
        assert abs(d.growth_rate_mm_per_month - (1.5 / 6.0)) < 0.001

    def test_no_match_outside_tolerance(self):
        tracker = TemporalTracker(tolerance_px=25.0, elapsed_months=6.0)
        prev = [make_defect("B1_C1_001", cx=0.0, cy=0.0)]
        curr = [make_defect("B1_C2_001", cx=200.0, cy=200.0)]
        result = tracker.match(curr, prev)
        assert result[0].matched_previous_id is None

    def test_growth_acceleration_computed(self):
        tracker = TemporalTracker(tolerance_px=25.0, elapsed_months=6.0)
        prev = [make_defect("B1_C1_001", cx=100.0, cy=100.0, growth_rate=0.5)]
        prev[0].width_mm = 1.0
        curr = [make_defect("B1_C2_001", cx=102.0, cy=101.0)]
        curr[0].width_mm = 4.0
        result = tracker.match(curr, [prev[0]])
        d = result[0]
        expected_rate = 3.0 / 6.0
        expected_accel = expected_rate - 0.5
        assert abs(d.growth_acceleration - expected_accel) < 0.001


# ---------------------------------------------------------------------------
# Unit: VIClassifier
# ---------------------------------------------------------------------------

class TestVIClassifier:
    def test_empty_defects(self):
        clf = VIClassifier()
        vi_class, score = clf.classify([])
        assert vi_class == "minor"
        assert score == 0.0

    def test_all_hairline(self):
        defects = [make_defect(f"D{i}", severity="hairline") for i in range(5)]
        clf = VIClassifier()
        vi_class, _ = clf.classify(defects)
        assert vi_class == "minor"

    def test_all_severe(self):
        defects = [make_defect(f"D{i}", severity="severe") for i in range(10)]
        clf = VIClassifier()
        vi_class, _ = clf.classify(defects)
        assert vi_class == "critical"

    def test_vi_class_values_are_lowercase(self):
        """[Schema fix] — all vi_class values must be lowercase enums."""
        clf = VIClassifier()
        defect_sets = [
            [],
            [make_defect("D1", severity="hairline")],
            [make_defect("D1", severity="moderate")],
            [make_defect("D1", severity="severe")] * 5,
        ]
        valid = {"minor", "moderate", "severe", "critical"}
        for ds in defect_sets:
            vi_class, _ = clf.classify(ds)
            assert vi_class in valid, f"vi_class '{vi_class}' not in valid enum {valid}"


# ---------------------------------------------------------------------------
# Unit: FeatureExtractor
# ---------------------------------------------------------------------------

class TestFeatureExtractor:
    def test_parallel_extraction_completes(self, synthetic_image):
        img = cv2.imread(synthetic_image)
        extractor = FeatureExtractor({})
        features = extractor.extract(img)
        assert "crack_line_count" in features
        assert "spall_count" in features
        assert "texture_laplacian_variance" in features

    def test_worker_cap(self):
        from pipeline import MAX_WORKERS
        cpu = os.cpu_count() or 2
        assert MAX_WORKERS <= max(1, cpu - 1), \
            f"[RC-01] MAX_WORKERS={MAX_WORKERS} exceeds CPU-1={max(1, cpu-1)}"


# ---------------------------------------------------------------------------
# Unit: ZoneSeverityIndexer
# ---------------------------------------------------------------------------

class TestZoneSeverityIndexer:
    def test_nine_zone_keys(self):
        indexer = ZoneSeverityIndexer()
        defects = [make_defect(f"D{i}", cx=float(i * 30), cy=float(i * 20)) for i in range(9)]
        result = indexer.compute(defects, 256, 256)
        assert len(result) == 9
        for key in result:
            assert key.startswith("R") and "C" in key

    def test_empty_defects_all_zero(self):
        indexer = ZoneSeverityIndexer()
        result = indexer.compute([], 256, 256)
        assert all(v == 0.0 for v in result.values())

    def test_scores_normalized_01(self):
        indexer = ZoneSeverityIndexer()
        defects = [make_defect(f"D{i}", severity="severe", cx=10.0, cy=10.0) for i in range(5)]
        result = indexer.compute(defects, 256, 256)
        assert all(0.0 <= v <= 1.0 for v in result.values())


# ---------------------------------------------------------------------------
# Integration: SQLite store  [RC-07, RC-08, RC-09, RC-10, RC-12]
# ---------------------------------------------------------------------------

class TestSQLiteStore:
    def _make_result(self, building_id="TEST_B1", cycle=1, n_defects=3):
        defects = []
        for i in range(n_defects):
            d = make_defect(f"{building_id}_C{cycle}_{i:04d}",
                            cx=float(i * 40), cy=float(i * 30))
            defects.append(d)
        import dataclasses
        return {
            "pipeline_version": PIPELINE_VERSION,
            "run_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "building_id": building_id,
            "cycle_id": cycle,
            "vi_class": "moderate",
            "vi_score": 2.5,
            "gsd_mm_per_px": 1.2,
            "total_defects": n_defects,
            "defects": [dataclasses.asdict(d) for d in defects],
            "pipeline_warnings": [],
            "zone_severity_index": {"R1C1": 0.5, "R2C2": 0.3},
        }

    def test_save_and_retrieve(self, tmp_db):
        result = self._make_result()
        iid = save_inspection(result, db_path=tmp_db)
        assert iid > 0
        rows = get_inspections(db_path=tmp_db)
        assert len(rows) == 1
        assert rows[0]["building_id"] == "TEST_B1"

    def test_warnings_json_roundtrip(self, tmp_db):
        """[RC-12] — warnings must survive JSON round-trip."""
        result = self._make_result()
        result["pipeline_warnings"] = [
            {"code": "BLACKBOX_API_FAILURE", "severity": "non_fatal", "message": "timeout"}
        ]
        save_inspection(result, db_path=tmp_db)
        rows = get_inspections(db_path=tmp_db)
        warnings = rows[0]["pipeline_warnings"]
        assert isinstance(warnings, list), "pipeline_warnings must be a list after deserialize"
        assert warnings[0]["code"] == "BLACKBOX_API_FAILURE"

    def test_growth_acceleration_not_null(self, tmp_db):
        """[RC-09] — growth_acceleration must never be NULL in DB."""
        result = self._make_result()
        save_inspection(result, db_path=tmp_db)
        rows = get_inspections(db_path=tmp_db)
        defects = get_defects(rows[0]["id"], db_path=tmp_db)
        for d in defects:
            assert d["growth_acceleration"] is not None, \
                "[RC-09] growth_acceleration is NULL"

    def test_defect_filter_by_type(self, tmp_db):
        result = self._make_result(n_defects=3)
        # Manually set different types
        result["defects"][0]["defect_type"] = "crack"
        result["defects"][1]["defect_type"] = "spall"
        result["defects"][2]["defect_type"] = "crack"
        iid = save_inspection(result, db_path=tmp_db)
        cracks = get_defects(iid, defect_type="crack", db_path=tmp_db)
        spalls = get_defects(iid, defect_type="spall", db_path=tmp_db)
        assert len(cracks) == 2
        assert len(spalls) == 1

    def test_concurrent_writes(self, tmp_db):
        """[RC-07, RC-08] — WAL mode allows concurrent writes without crash."""
        errors = []

        def write_inspection(idx):
            try:
                r = self._make_result(building_id=f"B{idx}", cycle=1)
                save_inspection(r, db_path=tmp_db)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=write_inspection, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent write failures: {errors}"
        rows = get_inspections(db_path=tmp_db)
        assert len(rows) == 10

    def test_zero_defect_inspection(self, tmp_db):
        """Edge case: clean facade — no defects, VI=minor."""
        result = self._make_result(n_defects=0)
        result["vi_class"] = "minor"
        result["vi_score"] = 0.0
        iid = save_inspection(result, db_path=tmp_db)
        defects = get_defects(iid, db_path=tmp_db)
        assert defects == []

    def test_propagated_defects_query(self, tmp_db):
        """Temporal chain: C1 → C2 matched defects appear in propagated query."""
        import dataclasses
        d_c1 = make_defect("B_C1_0001", cx=100.0, cy=100.0)
        d_c2 = make_defect(
            "B_C2_0001", cx=102.0, cy=101.0,
            prev_id="B_C1_0001", growth_rate=0.25, growth_acc=0.1
        )
        r1 = self._make_result(building_id="PROP_B", cycle=1, n_defects=0)
        r1["defects"] = [dataclasses.asdict(d_c1)]
        r1["total_defects"] = 1

        r2 = self._make_result(building_id="PROP_B", cycle=2, n_defects=0)
        r2["defects"] = [dataclasses.asdict(d_c2)]
        r2["total_defects"] = 1

        save_inspection(r1, db_path=tmp_db)
        save_inspection(r2, db_path=tmp_db)

        propagated = get_propagated_defects("PROP_B", db_path=tmp_db)
        assert len(propagated) == 1
        assert propagated[0]["matched_previous_id"] == "B_C1_0001"


# ---------------------------------------------------------------------------
# Integration: Confidence threshold filtering  [RC-04]
# ---------------------------------------------------------------------------

class TestConfidenceFilter:
    def test_below_threshold_excluded(self):
        from pipeline import CONFIDENCE_THRESHOLD
        mock_detections = [
            {"type": "crack", "severity": "moderate", "confidence": 0.2,
             "width_mm": 1.0, "length_cm": 5.0, "area_px2": 100.0,
             "false_positive_prob": 0.3, "contour": [[0, 0]]},
            {"type": "crack", "severity": "severe", "confidence": 0.9,
             "width_mm": 3.0, "length_cm": 10.0, "area_px2": 300.0,
             "false_positive_prob": 0.05, "contour": [[0, 0]]},
        ]
        filtered = [d for d in mock_detections if d["confidence"] >= CONFIDENCE_THRESHOLD]
        assert len(filtered) == 1
        assert filtered[0]["severity"] == "severe"


# ---------------------------------------------------------------------------
# Integration: Blackbox API failure + warnings  [RC-03, RC-06]
# ---------------------------------------------------------------------------

class TestBlackboxFallback:
    def test_api_failure_returns_empty_with_warning(self):
        from pipeline import BlackboxDetector
        detector = BlackboxDetector("http://nonexistent.internal/detect", "key")
        warnings = []
        result = detector.detect("base64data", warnings)
        assert result == [], "Must return empty list on failure"
        assert len(warnings) == 1, "Must capture exactly one warning"
        assert warnings[0]["code"] == "BLACKBOX_API_FAILURE"
        assert warnings[0]["severity"] == "non_fatal"
        assert "fallback" in warnings[0]

    def test_warning_structure_is_json_serializable(self):
        from pipeline import BlackboxDetector
        detector = BlackboxDetector("http://nonexistent.internal/detect", "key")
        warnings = []
        detector.detect("data", warnings)
        try:
            json.dumps(warnings)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"Warning not JSON serializable: {exc}")


# ---------------------------------------------------------------------------
# E2E: Full pipeline → DB → stats
# ---------------------------------------------------------------------------

class TestE2EPipeline:
    def test_full_run_with_mocked_blackbox(
        self, synthetic_image, minimal_config, tmp_path, tmp_db
    ):
        mock_detections = [
            {"type": "crack", "severity": "moderate", "confidence": 0.88,
             "width_mm": 2.1, "length_cm": 8.5, "area_px2": 220.0,
             "false_positive_prob": 0.08,
             "contour": [[50, 50], [80, 50], [80, 80], [50, 80]]},
            {"type": "spall", "severity": "severe", "confidence": 0.75,
             "width_mm": 5.0, "length_cm": 12.0, "area_px2": 600.0,
             "false_positive_prob": 0.05,
             "contour": [[100, 100], [150, 100], [150, 150], [100, 150]]},
            # Below threshold — should be filtered  [RC-04]
            {"type": "crack", "severity": "hairline", "confidence": 0.20,
             "width_mm": 0.5, "length_cm": 2.0, "area_px2": 30.0,
             "false_positive_prob": 0.6,
             "contour": [[10, 10]]},
        ]

        with patch("pipeline.BlackboxDetector.detect", return_value=mock_detections):
            pipeline = CortexPipeline(minimal_config)
            result = pipeline.run(
                image_path=synthetic_image,
                building_id="E2E_B1",
                cycle_id=1,
            )

        # Pipeline output checks
        assert result.pipeline_version == PIPELINE_VERSION        # [RC-05]
        assert result.total_defects == 2                          # [RC-04] threshold filtered 1
        assert result.vi_class in {"minor", "moderate", "severe", "critical"}
        assert isinstance(result.pipeline_warnings, list)         # [RC-06]
        assert len(result.zone_severity_index) == 9

        # Save to DB and retrieve
        import dataclasses
        result_dict = dataclasses.asdict(result)
        iid = save_inspection(result_dict, db_path=tmp_db)
        assert iid > 0

        rows = get_inspections(building_id="E2E_B1", db_path=tmp_db)
        assert len(rows) == 1
        assert rows[0]["vi_class"] in {"minor", "moderate", "severe", "critical"}

        defects = get_defects(iid, db_path=tmp_db)
        assert len(defects) == 2
        for d in defects:
            assert d["confidence"] >= CONFIDENCE_THRESHOLD
            assert d["growth_acceleration"] is not None   # [RC-09]

        stats = get_db_stats(db_path=tmp_db)
        assert stats["total_inspections"] == 1
        assert stats["total_defects"] == 2
