"""
cv_crack_detector.py — Tile-based Computer-Vision Crack Measurement
===================================================================
A segmentation-driven crack measurement path that complements the analytical
"geometry" engine in ``civil_analysis.py``.

Two key ideas the geometry method does not use:

1.  TILING ("divide the image into small pixels")
    Large facade frames are split into overlapping tiles. Per-tile CLAHE +
    black-hat + Otsu thresholding recovers thin cracks that a single global
    threshold loses, and flat tiles are skipped so Otsu cannot hallucinate
    cracks on sound concrete. Tile masks are OR-ed back into a full-resolution
    crack mask.

2.  SKELETON GEODESIC LENGTH
    Each crack's centreline (skeleton) is traced and its length summed
    edge-by-edge with anisotropic GSD — so the measured length follows the
    crack's true curved path instead of a straight principal axis.

An optional YOLOv8-seg model is used when ``ultralytics`` is installed and
``CORTEX_YOLO_WEIGHTS`` points to a crack-trained checkpoint; otherwise the
tiled classical segmentation is used and a warning is recorded. Heavy DL
dependencies are therefore never required to run.
"""

from __future__ import annotations

import os
import math
import logging
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("cortex.cv_crack_detector")

# Detection gates (kept local to avoid a circular import with civil_analysis).
MIN_TILE_STD = 6.0    # tiles flatter than this carry no real feature
MIN_RAW_DEPTH = 10.0  # a crack must be this many grey-levels darker than surroundings

# Optional, accurate skeletonisation. Falls back to a contour-perimeter
# estimate when scikit-image is not installed.
try:
    from skimage.morphology import skeletonize as _sk_skeletonize
    _SKIMAGE_AVAILABLE = True
except Exception:  # pragma: no cover
    _SKIMAGE_AVAILABLE = False

_YOLO_MODEL = None
_YOLO_TRIED = False


# ─────────────────────────────────────────────────────────────────────────────
# Optional YOLO loader
# ─────────────────────────────────────────────────────────────────────────────

def _load_yolo():
    """Lazily load a YOLO segmentation model if configured. Returns model or None."""
    global _YOLO_MODEL, _YOLO_TRIED
    if _YOLO_TRIED:
        return _YOLO_MODEL
    _YOLO_TRIED = True
    weights = os.getenv("CORTEX_YOLO_WEIGHTS")
    if not weights or not os.path.exists(weights):
        logger.info("YOLO weights not configured (CORTEX_YOLO_WEIGHTS unset/missing).")
        return None
    try:
        from ultralytics import YOLO  # type: ignore
        _YOLO_MODEL = YOLO(weights)
        logger.info("Loaded YOLO crack model from %s", weights)
    except Exception as e:  # pragma: no cover
        logger.warning("Could not load YOLO (%s). Falling back to classical CV.", e)
        _YOLO_MODEL = None
    return _YOLO_MODEL


def _yolo_mask(model, img_bgr: np.ndarray) -> Optional[np.ndarray]:
    """Run YOLO-seg and return a binary crack mask at the image resolution."""
    try:
        h, w = img_bgr.shape[:2]
        res = model.predict(img_bgr, verbose=False)
        if not res or res[0].masks is None:
            return None
        data = res[0].masks.data.cpu().numpy()  # (n, mh, mw)
        combined = (data.max(axis=0) > 0.5).astype(np.uint8) * 255
        return cv2.resize(combined, (w, h), interpolation=cv2.INTER_NEAREST)
    except Exception as e:  # pragma: no cover
        logger.warning("YOLO inference failed (%s).", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Tiled classical segmentation
# ─────────────────────────────────────────────────────────────────────────────

def segment_cracks_tiled(
    gray: np.ndarray,
    tile: int = 256,
    overlap: int = 32,
    response_floor: int = 18,
) -> np.ndarray:
    """Return a full-resolution binary crack mask via per-tile segmentation."""
    h, w = gray.shape
    mask = np.zeros((h, w), np.uint8)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    bh_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    step = max(1, tile - overlap)

    for y0 in range(0, h, step):
        for x0 in range(0, w, step):
            y1, x1 = min(y0 + tile, h), min(x0 + tile, w)
            patch = gray[y0:y1, x0:x1]
            if patch.size == 0 or patch.shape[0] < 8 or patch.shape[1] < 8:
                continue
            # Flat tiles carry no real feature — skip before CLAHE so we don't
            # amplify noise into a fake crack.
            if float(patch.std()) < MIN_TILE_STD:
                continue
            enhanced = clahe.apply(patch)
            bh = cv2.morphologyEx(enhanced, cv2.MORPH_BLACKHAT, bh_kernel)
            # Skip flat tiles: no meaningful dark-feature response → no crack.
            if int(bh.max()) < response_floor:
                continue
            _, th = cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            sub = mask[y0:y1, x0:x1]
            mask[y0:y1, x0:x1] = cv2.bitwise_or(sub, th)

    # Remove speckle, then bridge crack gaps.
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    return mask


# ─────────────────────────────────────────────────────────────────────────────
# Skeleton + geodesic length
# ─────────────────────────────────────────────────────────────────────────────

def _skeleton(mask: np.ndarray) -> Optional[np.ndarray]:
    if not _SKIMAGE_AVAILABLE:
        return None
    return (_sk_skeletonize(mask > 0)).astype(np.uint8)


def _skeleton_length(skel: np.ndarray, gsd_x: float, gsd_y: float) -> Tuple[float, float]:
    """Geodesic length of a skeleton. Returns (length_px, length_cm).

    Each adjacency is counted once (forward/down neighbours). Diagonal steps are
    weighted by sqrt(2) in pixels and by the anisotropic diagonal in cm.
    """
    ys, xs = np.where(skel > 0)
    if xs.size == 0:
        return 0.0, 0.0
    pts = set(zip(xs.tolist(), ys.tolist()))
    diag_cm = math.hypot(gsd_x, gsd_y)
    length_px = 0.0
    length_cm = 0.0
    for (x, y) in pts:
        if (x + 1, y) in pts:        # horizontal edge
            length_px += 1.0
            length_cm += gsd_x
        if (x, y + 1) in pts:        # vertical edge
            length_px += 1.0
            length_cm += gsd_y
        if (x + 1, y + 1) in pts:    # diagonal
            length_px += math.sqrt(2)
            length_cm += diag_cm
        if (x - 1, y + 1) in pts:    # anti-diagonal
            length_px += math.sqrt(2)
            length_cm += diag_cm
    return length_px, length_cm


def _contour_length_px(component_mask: np.ndarray) -> float:
    """Fallback length estimate: perimeter/2 of a thin elongated blob."""
    contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return 0.0
    cnt = max(contours, key=cv2.contourArea)
    return cv2.arcLength(cnt, closed=True) / 2.0


# ─────────────────────────────────────────────────────────────────────────────
# Public: measure with the CV method
# ─────────────────────────────────────────────────────────────────────────────

def measure_cv(
    gray: np.ndarray,
    gsd_x: float,
    gsd_y: float,
    img_bgr: Optional[np.ndarray] = None,
    use_yolo: bool = False,
) -> Dict[str, Any]:
    """Detect and measure cracks via segmentation. Returns primary + per-crack data."""
    warnings: List[str] = []
    h, w = gray.shape
    img_area = float(h * w)
    gsd_avg = (gsd_x + gsd_y) / 2.0
    yolo_used = False

    mask = None
    if use_yolo:
        model = _load_yolo()
        if model is not None and img_bgr is not None:
            mask = _yolo_mask(model, img_bgr)
            yolo_used = mask is not None
        if mask is None:
            warnings.append("YOLO unavailable — fell back to tiled CV segmentation.")
    if mask is None:
        mask = segment_cracks_tiled(gray)

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    min_area = max(40.0, img_area * 5e-5)

    cracks: List[Dict[str, Any]] = []
    for i in range(1, num):
        area = float(stats[i, cv2.CC_STAT_AREA])
        if area < min_area or area > img_area * 0.5:
            continue
        comp = (labels == i).astype(np.uint8) * 255

        # Raw-darkness gate: reject blobs that aren't genuinely darker than their
        # surroundings in the original image (CLAHE-amplified noise on flat walls).
        ys_c, xs_c = np.where(labels == i)
        ring = cv2.dilate(comp, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
        ring_mask = (ring > 0) & (labels != i)
        comp_mean = float(gray[ys_c, xs_c].mean())
        ring_mean = float(gray[ring_mask].mean()) if ring_mask.any() else comp_mean
        if (ring_mean - comp_mean) < MIN_RAW_DEPTH:
            continue

        skel = _skeleton(comp)
        if skel is not None:
            length_px, length_cm = _skeleton_length(skel, gsd_x, gsd_y)
        else:
            length_px = _contour_length_px(comp)
            length_cm = length_px * gsd_avg
        if length_px < 2.0:
            continue

        # Width via distance transform (max inscribed radius -> full width).
        edt = cv2.distanceTransform(comp, cv2.DIST_L2, 5)
        ref = skel if skel is not None else comp
        radii = edt[ref > 0]
        mean_width_px = float(2.0 * radii.mean()) if radii.size else area / length_px
        width_mm = mean_width_px * gsd_avg * 10.0

        # Orientation via PCA on component pixels.
        ys, xs = np.where(comp > 0)
        pts = np.column_stack((xs, ys)).astype(np.float32)
        mean, eigvecs = cv2.PCACompute(pts, mean=None, maxComponents=1)
        vx, vy = float(eigvecs[0, 0]), float(eigvecs[0, 1])
        angle_deg = math.degrees(math.atan2(abs(vy), abs(vx)))

        # Curvature/tortuosity: skeleton length vs straight end-to-end distance.
        straight_px = math.hypot(
            (xs.max() - xs.min()), (ys.max() - ys.min())
        )
        tortuosity = length_px / straight_px if straight_px > 1 else 1.0

        # Skeleton or contour polyline — normalized to [0,1] for the frontend.
        # The frontend draws these directly on the canvas, so lines land exactly
        # on the detected crack pixels regardless of display size.
        if skel is not None:
            skel_ys, skel_xs = np.where(skel > 0)
            # Downsample to ≤200 points so the JSON stays small
            pts_arr = np.column_stack((skel_xs, skel_ys))
            if len(pts_arr) > 200:
                idx = np.linspace(0, len(pts_arr) - 1, 200, dtype=int)
                pts_arr = pts_arr[idx]
            # Sort along principal axis so lines connect sequentially
            proj = pts_arr @ np.array([vx, vy])
            pts_arr = pts_arr[np.argsort(proj)]
            contour_pts = [[round(float(px) / w, 4), round(float(py) / h, 4)]
                           for px, py in pts_arr]
        else:
            # Fallback: use the outer contour approximated to ≤60 points
            cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if cnts:
                cnt = max(cnts, key=cv2.contourArea)
                eps = 0.02 * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, eps, False)
                contour_pts = [[round(float(p[0][0]) / w, 4), round(float(p[0][1]) / h, 4)]
                                for p in approx[:60]]
            else:
                contour_pts = []

        cracks.append({
            "length_cm": round(length_cm, 1),
            "width_mm": round(width_mm, 2),
            "angle_deg": round(angle_deg, 1),
            "area_cm2": round(area * gsd_x * gsd_y, 2),
            "length_px": round(length_px, 1),
            "tortuosity": round(tortuosity, 2),
            "centroid_px": {"x": int(centroids[i, 0]), "y": int(centroids[i, 1])},
            "contour_pts": contour_pts,  # normalized [0,1] coords for canvas drawing
        })

    cracks.sort(key=lambda c: c["length_cm"], reverse=True)
    if cracks:
        primary = cracks[0]
    else:
        primary = {"length_cm": 0.0, "width_mm": 0.0, "angle_deg": 0.0, "tortuosity": 1.0}
        warnings.append("CV segmentation found no crack-like features.")

    return {
        "method": "yolo" if yolo_used else "cv",
        "yolo_used": yolo_used,
        "skeleton_engine": "skimage" if _SKIMAGE_AVAILABLE else "contour_perimeter",
        "length_cm": primary["length_cm"],
        "width_mm": primary["width_mm"],
        "angle_deg": primary["angle_deg"],
        "tortuosity": primary.get("tortuosity", 1.0),
        "crack_count": len(cracks),
        "cracks": cracks,
        "warnings": warnings,
    }
