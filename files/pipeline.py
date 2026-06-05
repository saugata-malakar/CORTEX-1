"""
Cortex Structural Intelligence Defect Pipeline
pipeline.py — Production-hardened core pipeline

ROOT CAUSES FIXED:
  [RC-01] ThreadPoolExecutor unbounded → CPU thrash on 4-core machines
  [RC-02] SIFT cache keyed on filename → cross-cycle collisions
  [RC-03] API fallback silently drops data → invisible data loss
  [RC-04] No confidence threshold → noise floods GeoJSON output
  [RC-05] No pipeline_version in output → audit trail broken
  [RC-06] No pipeline_warnings[] → frontend has no signal on partial failures
"""

import os
import json
import hashlib
import logging
import traceback
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Logging — structured JSON to stdout for Grafana Loki ingestion
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}'
)
log = logging.getLogger("cortex.pipeline")

PIPELINE_VERSION = "1.4.0"
MAX_WORKERS = max(1, (os.cpu_count() or 2) - 1)   # [RC-01] cap at CPU-1
CONFIDENCE_THRESHOLD = 0.45                          # [RC-04] filter noise


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class Defect:
    defect_id: str
    defect_type: str          # crack | spall | delamination | efflorescence
    severity: str             # hairline | moderate | severe
    width_mm: float
    length_cm: float
    area_px2: float
    centroid_x: float
    centroid_y: float
    confidence: float
    false_positive_prob: float
    contour_geojson: dict
    # Temporal fields (populated by TemporalTracker)
    matched_previous_id: Optional[str] = None
    delta_width_mm: float = 0.0
    growth_rate_mm_per_month: float = 0.0
    growth_acceleration: float = 0.0


@dataclass
class InspectionResult:
    pipeline_version: str
    run_timestamp: str
    building_id: str
    cycle_id: int
    vi_class: str             # minor | moderate | severe | critical
    vi_score: float
    gsd_mm_per_px: float
    total_defects: int
    defects: list[Defect] = field(default_factory=list)
    pipeline_warnings: list[dict] = field(default_factory=list)   # [RC-06]
    zone_severity_index: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# SIFT Descriptor Cache  [RC-02 fixed — keyed on SHA-256, not filename]
# ---------------------------------------------------------------------------

class SIFTCache:
    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._sift = cv2.SIFT_create()

    @staticmethod
    def _hash(image_path: str) -> str:
        h = hashlib.sha256()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def get_descriptors(self, image_path: str):
        key = self._hash(image_path)
        if key not in self._cache:
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise ValueError(f"Cannot read image: {image_path}")
            kp, des = self._sift.detectAndCompute(img, None)
            self._cache[key] = (kp, des)
            log.info(f"SIFT cached: {Path(image_path).name} → {key[:12]}...")
        return self._cache[key]

    def invalidate(self, image_path: str):
        key = self._hash(image_path)
        self._cache.pop(key, None)


_sift_cache = SIFTCache()


# ---------------------------------------------------------------------------
# Feature Extractor — parallel submodules  [RC-01 fixed — bounded pool]
# ---------------------------------------------------------------------------

class FeatureExtractor:
    """
    Runs crack_features, spall_features, texture_features concurrently.
    MAX_WORKERS is CPU-bound — prevents thread thrash.
    """

    def __init__(self, config: dict):
        self.config = config

    def _extract_crack_features(self, image: np.ndarray) -> dict:
        # Canny + HoughLinesP for crack geometry
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                 minLineLength=30, maxLineGap=10)
        count = 0 if lines is None else len(lines)
        return {"crack_line_count": count, "edge_density": float(np.sum(edges) / edges.size)}

    def _extract_spall_features(self, image: np.ndarray) -> dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        areas = [cv2.contourArea(c) for c in contours if cv2.contourArea(c) > 200]
        return {
            "spall_count": len(areas),
            "mean_spall_area_px2": float(np.mean(areas)) if areas else 0.0,
            "max_spall_area_px2": float(max(areas)) if areas else 0.0,
        }

    def _extract_texture_features(self, image: np.ndarray) -> dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return {"texture_laplacian_variance": laplacian_var}

    def extract(self, image: np.ndarray) -> dict:
        submodules = [
            self._extract_crack_features,
            self._extract_spall_features,
            self._extract_texture_features,
        ]
        results = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:   # [RC-01]
            futures = {pool.submit(fn, image): fn.__name__ for fn in submodules}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results.update(future.result())
                except Exception as exc:
                    log.error(f"Feature submodule {name} failed: {exc}")
                    results[f"{name}_error"] = str(exc)
        return results


# ---------------------------------------------------------------------------
# Blackbox Detector — graceful fallback with WARNING capture  [RC-03 fixed]
# ---------------------------------------------------------------------------

class BlackboxDetector:
    """
    Wraps external API calls.
    On failure: returns empty list AND appends structured warning to caller.
    Previously: silently returned empty set with no signal to frontend.
    """

    def __init__(self, api_endpoint: str, api_key: str):
        self.endpoint = api_endpoint
        self.api_key = api_key

    def detect(self, image_b64: str, warnings: list) -> list[dict]:
        try:
            import requests
            resp = requests.post(
                self.endpoint,
                json={"image": image_b64},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("detections", [])

        except Exception as exc:
            tb = traceback.format_exc()
            log.warning(f"[RC-03] Blackbox API failed: {exc}")
            # [RC-06] structured warning — surfaced in frontend banner
            warnings.append({
                "code": "BLACKBOX_API_FAILURE",
                "severity": "non_fatal",
                "message": f"Blackbox detection unavailable: {str(exc)}",
                "fallback": "empty_detections",
                "traceback_snippet": tb.splitlines()[-3:],
            })
            return []


# ---------------------------------------------------------------------------
# Temporal Tracker
# ---------------------------------------------------------------------------

class TemporalTracker:
    """
    Matches current-cycle defects to previous-cycle defects.
    Calculates delta_width_mm, growth_rate_mm_per_month, growth_acceleration.

    EDGE CASES HANDLED:
      - Division by zero when elapsed_months == 0
      - growth_acceleration when previous rate is None (first match)
      - Centroid distance matching with configurable tolerance
    """

    def __init__(self, tolerance_px: float = 25.0, elapsed_months: float = 6.0):
        self.tolerance = tolerance_px
        self.elapsed_months = max(elapsed_months, 0.001)   # guard div/zero

    def match(self, current: list[Defect], previous: list[Defect]) -> list[Defect]:
        prev_map = {d.defect_id: d for d in previous}

        for defect in current:
            best_match = None
            best_dist = float("inf")

            for prev_defect in previous:
                if prev_defect.defect_type != defect.defect_type:
                    continue
                dist = np.sqrt(
                    (defect.centroid_x - prev_defect.centroid_x) ** 2 +
                    (defect.centroid_y - prev_defect.centroid_y) ** 2
                )
                if dist < best_dist:
                    best_dist = dist
                    best_match = prev_defect

            if best_match and best_dist <= self.tolerance:
                defect.matched_previous_id = best_match.defect_id
                defect.delta_width_mm = defect.width_mm - best_match.width_mm
                defect.growth_rate_mm_per_month = (
                    defect.delta_width_mm / self.elapsed_months
                )
                # growth_acceleration: rate change vs previous rate
                if best_match.growth_rate_mm_per_month != 0.0:
                    defect.growth_acceleration = (
                        defect.growth_rate_mm_per_month
                        - best_match.growth_rate_mm_per_month
                    )
                else:
                    defect.growth_acceleration = defect.growth_rate_mm_per_month

        return current


# ---------------------------------------------------------------------------
# Zone Severity Indexer (IS 13311 — 3×3 facade grid)
# ---------------------------------------------------------------------------

class ZoneSeverityIndexer:
    SEVERITY_WEIGHT = {"hairline": 1, "moderate": 3, "severe": 7}

    def compute(self, defects: list[Defect], image_w: int, image_h: int) -> dict:
        grid = {f"R{r}C{c}": 0.0 for r in range(1, 4) for c in range(1, 4)}
        zone_counts = {k: 0 for k in grid}

        cell_w = image_w / 3
        cell_h = image_h / 3

        for d in defects:
            col = min(int(d.centroid_x / cell_w) + 1, 3)
            row = min(int(d.centroid_y / cell_h) + 1, 3)
            key = f"R{row}C{col}"
            grid[key] += self.SEVERITY_WEIGHT.get(d.severity, 1)
            zone_counts[key] += 1

        # Normalize to 0–1
        max_score = max(grid.values()) if max(grid.values()) > 0 else 1
        return {k: round(v / max_score, 4) for k, v in grid.items()}


# ---------------------------------------------------------------------------
# Vulnerability Index Classifier
# ---------------------------------------------------------------------------

class VIClassifier:
    def classify(self, defects: list[Defect]) -> tuple[str, float]:
        if not defects:
            return "minor", 0.0

        score = sum(
            {"hairline": 1, "moderate": 3, "severe": 7}.get(d.severity, 1)
            for d in defects
        ) / len(defects)

        if score < 1.5:
            return "minor", round(score, 3)
        elif score < 3.0:
            return "moderate", round(score, 3)
        elif score < 5.5:
            return "severe", round(score, 3)
        else:
            return "critical", round(score, 3)


# ---------------------------------------------------------------------------
# CortexPipeline — Orchestrator
# ---------------------------------------------------------------------------

class CortexPipeline:
    def __init__(self, config_path: str = "configs/config.json"):
        with open(config_path) as f:
            self.config = json.load(f)

        self.feature_extractor = FeatureExtractor(self.config)
        self.temporal_tracker = TemporalTracker(
            tolerance_px=self.config.get("temporal_tolerance_px", 25.0),
            elapsed_months=self.config.get("elapsed_months", 6.0),
        )
        self.zone_indexer = ZoneSeverityIndexer()
        self.vi_classifier = VIClassifier()
        self.blackbox = BlackboxDetector(
            api_endpoint=self.config.get("blackbox_api_endpoint", ""),
            api_key=self.config.get("blackbox_api_key", ""),
        )

    def run(
        self,
        image_path: str,
        building_id: str,
        cycle_id: int,
        previous_defects: Optional[list[Defect]] = None,
    ) -> InspectionResult:
        start = time.time()
        warnings: list[dict] = []   # [RC-06] collects all non-fatal issues

        log.info(f"Pipeline start: building={building_id} cycle={cycle_id}")

        # 1. Load image
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"Cannot load image: {image_path}")
        h, w = image.shape[:2]

        # 2. SIFT features (cached by SHA-256)  [RC-02]
        try:
            kp, descriptors = _sift_cache.get_descriptors(image_path)
        except Exception as exc:
            warnings.append({
                "code": "SIFT_CACHE_MISS",
                "severity": "non_fatal",
                "message": str(exc),
            })
            kp, descriptors = [], None

        # 3. Parallel feature extraction  [RC-01]
        features = self.feature_extractor.extract(image)

        # 4. Blackbox API detection  [RC-03]
        import base64
        _, img_encoded = cv2.imencode(".jpg", image)
        img_b64 = base64.b64encode(img_encoded).decode()
        raw_detections = self.blackbox.detect(img_b64, warnings)

        # 5. Build defect objects + confidence filter  [RC-04]
        defects: list[Defect] = []
        for i, det in enumerate(raw_detections):
            conf = float(det.get("confidence", 0.0))
            if conf < CONFIDENCE_THRESHOLD:   # [RC-04] filter noise
                continue
            contour = det.get("contour", [[0, 0]])
            cx = float(np.mean([p[0] for p in contour]))
            cy = float(np.mean([p[1] for p in contour]))
            defects.append(Defect(
                defect_id=f"{building_id}_C{cycle_id}_{i:04d}",
                defect_type=det.get("type", "crack"),
                severity=det.get("severity", "hairline"),
                width_mm=float(det.get("width_mm", 0.0)),
                length_cm=float(det.get("length_cm", 0.0)),
                area_px2=float(det.get("area_px2", 0.0)),
                centroid_x=cx,
                centroid_y=cy,
                confidence=conf,
                false_positive_prob=float(det.get("false_positive_prob", 0.0)),
                contour_geojson={
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [contour],
                    },
                    "properties": {
                        "defect_id": f"{building_id}_C{cycle_id}_{i:04d}",
                        "type": det.get("type", "crack"),
                        "severity": det.get("severity", "hairline"),
                        "width_mm": det.get("width_mm", 0.0),
                        "length_cm": det.get("length_cm", 0.0),
                        "false_positive_prob": det.get("false_positive_prob", 0.0),
                    },
                },
            ))

        # 6. Temporal matching
        if previous_defects:
            defects = self.temporal_tracker.match(defects, previous_defects)

        # 7. VI classification
        vi_class, vi_score = self.vi_classifier.classify(defects)

        # 8. Zone severity index
        zone_map = self.zone_indexer.compute(defects, w, h)

        elapsed = round(time.time() - start, 3)
        log.info(f"Pipeline complete: {len(defects)} defects | VI={vi_class} | {elapsed}s")

        return InspectionResult(
            pipeline_version=PIPELINE_VERSION,      # [RC-05]
            run_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            building_id=building_id,
            cycle_id=cycle_id,
            vi_class=vi_class,
            vi_score=vi_score,
            gsd_mm_per_px=float(self.config.get("gsd_mm_per_px", 1.0)),
            total_defects=len(defects),
            defects=defects,
            pipeline_warnings=warnings,             # [RC-06]
            zone_severity_index=zone_map,
        )

    def to_json(self, result: InspectionResult) -> dict:
        d = asdict(result)
        return d
