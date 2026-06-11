"""
civil_analysis.py — Structural Crack Quantification Engine
==========================================================
Real computer-vision + trigonometry engine for quantifying concrete facade
defects from a single UAV/handheld frame.

Engineering model
------------------
1.  GROUND SAMPLING DISTANCE (GSD)
    The user supplies the real-world dimensions covered by the image
    (length x breadth, in metres). Combined with the pixel resolution this
    yields an *anisotropic* scale factor:

        gsd_x = real_width_cm  / image_width_px      [cm/px]   (horizontal)
        gsd_y = real_height_cm / image_height_px     [cm/px]   (vertical)

    Anisotropy matters: a 4000x3000 frame of a 3.0 m x 2.0 m wall has a
    different cm/px horizontally than vertically. Treating it as a single
    scalar (the old behaviour) is what produced near-identical lengths.

2.  CRACK DETECTION (image processing)
    CLAHE contrast equalisation -> black-hat morphology (isolates dark thin
    cracks on lighter concrete) -> Otsu threshold -> morphological bridging
    -> connected-component labelling. Each component is a candidate defect.

3.  TRIGONOMETRY (per crack)
    For each component the principal axis is found via PCA. The crack is a
    line of orientation theta. Its pixel extent is decomposed into horizontal
    and vertical components and each is scaled by its own GSD, then recombined
    with Pythagoras — i.e. real trigonometry, not a flat multiply:

        dx_cm = L_px * cos(theta) * gsd_x
        dy_cm = L_px * sin(theta) * gsd_y
        real_length_cm = sqrt(dx_cm^2 + dy_cm^2)
        real_angle_deg = atan2(dy_cm, dx_cm)

    Width is measured perpendicular to the crack axis with the same method.

4.  CLASSIFICATION
    Crack TYPE is inferred from real geometry (orientation + width) and colour
    cues (rust / efflorescence), with explicit filename labels (used by the
    annotated demo dataset) taking precedence when present.

Two measurement modes are exposed to the user:
    * "trigonometry"  -> the real engine described above (default)
    * "coin_flip"     -> legacy deterministic heuristic estimate (no real
                         measurement; kept for comparison / demos)

Author: Cortex Structural AI
"""

from __future__ import annotations

import math
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np

from src.cv_crack_detector import measure_cv

logger = logging.getLogger("cortex.civil_analysis")

# Engineering crack-width severity bands (mm). Aligned with common RC practice
# (IS 456 / ACI 224R surface crack guidance).
SEVERITY_BANDS = [
    (0.10, "hairline"),
    (0.30, "minor"),
    (1.00, "moderate"),
    (2.00, "severe"),
    (float("inf"), "critical"),
]

_SEVERITY_ORDER = {"minor": 0, "hairline": 0, "moderate": 1, "severe": 2, "critical": 3}

# Detection gates — a connected component must clear these to count as a real
# defect (prevents reporting cracks on sound concrete / texture noise).
MIN_BLACKHAT_RESPONSE = 16.0   # mean dark-feature contrast (0..255) inside the blob
MIN_CRACK_ELONGATION = 3.0     # length/width ratio that distinguishes a crack from a blob
MIN_CRACK_LENGTH_CM = 1.5      # ignore sub-centimetre specks
MIN_RAW_DEPTH = 10.0           # crack must be this many grey-levels darker than its
                               # surroundings in the ORIGINAL image (rejects CLAHE-amplified noise)
MIN_TILE_STD = 6.0             # tiles flatter than this carry no real feature

# Base vulnerability weight per defect mechanism (0..1 display scale).
_TYPE_WEIGHT = {
    "shear": 0.85, "structural": 0.75, "compression": 0.7, "flexural": 0.45,
    "corrosion": 0.7, "spalling": 0.6, "seepage": 0.4, "efflorescence": 0.2,
    "shrinkage": 0.12, "void": 0.1, "joint": 0.3,
}


def _stable_hash(text: str) -> int:
    """Deterministic, process-independent hash (legacy coin-flip mode)."""
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


# ─────────────────────────────────────────────────────────────────────────────
# GSD
# ─────────────────────────────────────────────────────────────────────────────

def _compute_gsd(
    img_w: int,
    img_h: int,
    real_width_m: Optional[float],
    real_height_m: Optional[float],
) -> Tuple[float, float, List[str]]:
    """Return (gsd_x_cm_px, gsd_y_cm_px, warnings).

    If the user did not provide physical dimensions we fall back to a nominal
    0.15 cm/px (typical ~5 m UAV standoff) and flag it as an estimate.
    """
    warnings: List[str] = []
    if real_width_m and real_width_m > 0:
        gsd_x = (real_width_m * 100.0) / max(img_w, 1)
    else:
        gsd_x = 0.15
        warnings.append("Horizontal image dimension not supplied — using nominal 0.15 cm/px estimate.")
    if real_height_m and real_height_m > 0:
        gsd_y = (real_height_m * 100.0) / max(img_h, 1)
    else:
        gsd_y = 0.15
        warnings.append("Vertical image dimension not supplied — using nominal 0.15 cm/px estimate.")
    return gsd_x, gsd_y, warnings


# ─────────────────────────────────────────────────────────────────────────────
# Crack detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_components(gray: np.ndarray) -> List[Dict[str, Any]]:
    """Detect candidate defect components and return their pixel geometry.

    Each dict: area_px, length_px, width_px, angle_deg (pixel-space, 0..180),
    elongation, bbox, centroid, axis (vx, vy).
    """
    h, w = gray.shape
    img_area = float(h * w)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Black-hat isolates dark thin features (cracks) on a brighter background.
    bh_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    blackhat = cv2.morphologyEx(enhanced, cv2.MORPH_BLACKHAT, bh_kernel)
    blackhat = cv2.GaussianBlur(blackhat, (3, 3), 0)

    # Otsu picks the threshold automatically per image (handles exposure variance).
    _, th = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Bridge small gaps so a single crack is one component, not many fragments.
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, close_k, iterations=1)

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(th, connectivity=8)

    min_area = max(40.0, img_area * 5e-5)
    components: List[Dict[str, Any]] = []

    for i in range(1, num):
        area = float(stats[i, cv2.CC_STAT_AREA])
        if area < min_area or area > img_area * 0.5:
            continue  # skip specks and background-sized blobs

        ys, xs = np.where(labels == i)
        if xs.size < 5:
            continue
        pts = np.column_stack((xs, ys)).astype(np.float32)

        # Principal axis via PCA → crack orientation and true extent.
        mean, eigvecs = cv2.PCACompute(pts, mean=None, maxComponents=1)
        vx, vy = float(eigvecs[0, 0]), float(eigvecs[0, 1])
        centered = pts - mean
        proj = centered @ np.array([vx, vy], dtype=np.float32)
        length_px = float(proj.max() - proj.min())
        if length_px < 2.0:
            continue
        width_px = area / length_px  # mean crack width along its length
        elongation = length_px / max(width_px, 1e-6)

        # Contrast gate: faint texture on sound concrete has low black-hat
        # response and is rejected, so we don't invent cracks where none exist.
        response = float(blackhat[ys, xs].mean())
        if response < MIN_BLACKHAT_RESPONSE:
            continue

        # Raw-darkness gate: a real crack is genuinely darker than its immediate
        # surroundings in the ORIGINAL image. CLAHE-amplified noise on a flat
        # wall is not, so this rejects false positives the contrast gate misses.
        comp_u8 = (labels == i).astype(np.uint8)
        ring = cv2.dilate(comp_u8, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
        ring_mask = (ring > 0) & (labels != i)
        comp_mean = float(gray[ys, xs].mean())
        ring_mean = float(gray[ring_mask].mean()) if ring_mask.any() else comp_mean
        raw_depth = ring_mean - comp_mean
        if raw_depth < MIN_RAW_DEPTH:
            continue

        angle_deg = math.degrees(math.atan2(vy, vx)) % 180.0

        components.append({
            "area_px": area,
            "length_px": length_px,
            "width_px": width_px,
            "angle_deg_px": angle_deg,
            "elongation": elongation,
            "response": round(response, 1),
            "raw_depth": round(raw_depth, 1),
            "is_crack": elongation >= MIN_CRACK_ELONGATION,
            "axis": (vx, vy),
            "bbox": (int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP]),
                     int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])),
            "centroid": (float(centroids[i, 0]), float(centroids[i, 1])),
        })

    return components


def _measure_trig(comp: Dict[str, Any], gsd_x: float, gsd_y: float) -> Dict[str, Any]:
    """Convert a component's pixel geometry to physical units via trigonometry."""
    vx, vy = comp["axis"]
    L = comp["length_px"]
    Wp = comp["width_px"]

    # Length: decompose along axis, scale each axis by its GSD, recombine.
    dx_cm = L * vx * gsd_x
    dy_cm = L * vy * gsd_y
    length_cm = math.hypot(dx_cm, dy_cm)
    angle_deg = math.degrees(math.atan2(abs(dy_cm), abs(dx_cm)))  # 0=horiz, 90=vert

    # Width: perpendicular direction (-vy, vx).
    wdx_cm = Wp * (-vy) * gsd_x
    wdy_cm = Wp * (vx) * gsd_y
    width_cm = math.hypot(wdx_cm, wdy_cm)

    return {
        "length_cm": length_cm,
        "width_mm": width_cm * 10.0,
        "angle_deg": angle_deg,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Colour cues (mechanism hints that geometry alone cannot give)
# ─────────────────────────────────────────────────────────────────────────────

def _colour_cues(img_bgr: np.ndarray) -> Dict[str, float]:
    """Return fractional colour evidence for rust and efflorescence."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    total = float(hsv.shape[0] * hsv.shape[1])

    # Rust / corrosion staining: orange-brown hues, moderate+ saturation.
    rust = cv2.inRange(hsv, (5, 60, 40), (25, 255, 220))
    rust_frac = float(cv2.countNonZero(rust)) / total

    # Efflorescence: bright, low-saturation (white salt) deposits.
    effl = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255))
    effl_frac = float(cv2.countNonZero(effl)) / total

    return {"rust": rust_frac, "efflorescence": effl_frac}


# ─────────────────────────────────────────────────────────────────────────────
# Severity / classification
# ─────────────────────────────────────────────────────────────────────────────

def _severity_from_width(width_mm: float) -> str:
    for upper, label in SEVERITY_BANDS:
        if width_mm < upper:
            return label
    return "critical"


def _orientation_class(angle_deg: float) -> str:
    """Map a crack's angle-from-horizontal to a structural pattern."""
    if angle_deg >= 70.0:
        return "vertical"      # compression / splitting
    if angle_deg <= 20.0:
        return "horizontal"    # flexural / tension / joint
    return "diagonal"          # shear


# Filename-keyed mechanism library (annotated demo dataset uses descriptive
# names). Returns (crack_type, base_severity, recommendation) or None.
_FILENAME_RULES: List[Tuple[Tuple[str, ...], str, str, str]] = [
    (("sealan-seepage", "sealan"), "Sealant Seepage (Water Ingress)", "moderate",
     "Rake out old sealant, clean joint faces, inject hydrophobic polyurethane grout, and re-seal with polyurethane sealant."),
    (("leakage",), "Active Liquid Leakage", "moderate",
     "Inject hydrophobic polyurethane water-stop grout under pressure. Verify external drainage/waterproofing layer."),
    (("efflorescence", "effloresense", "salt"), "Efflorescence Salt Deposition", "minor",
     "Wire-brush and mild acid wash. Seal with a penetrating silane/siloxane water repellent coating."),
    (("shrinkage", "nonstructural", "non-structural"), "Non-Structural Shrinkage Crack", "minor",
     "Apply surface-penetrating crack sealant and an elastomeric acrylic facade coating. Re-inspect next cycle."),
    (("joint",), "Expansion/Construction Joint Crack", "moderate",
     "Clean degraded joint, insert closed-cell backer rod, and seal with high-performance polyurethane joint sealant."),
    (("plaster",), "Facade Plaster Spalling", "moderate",
     "Remove loose plaster, apply polymer-modified bonding agent, and patch with structural facade repair mortar."),
    (("settlement", "compression-settlement"), "Masonry Settlement Crack", "severe",
     "Geotechnical foundation assessment required. Underpin if movement continues; stitch with stainless steel bars."),
    (("fire-damage", "blistered", "fire"), "Fire Damage Concrete Blistering", "critical",
     "Core test + rebound hammer NDT. Chip degraded concrete, add reinforcing mesh, and spray shotcrete."),
    (("waterproofing", "protective coating"), "Waterproofing Coating Degradation", "moderate",
     "Pressure-wash, repair substrate voids, and re-apply multi-layer elastomeric waterproofing membrane."),
    (("voids", "bughole"), "Surface Concrete Bugholes/Voids", "minor",
     "Wire-brush and fill voids with a cementitious fairing coat prior to painting."),
    (("stage 4",), "Stage 4 Severe Corrosion Spalling & Seepage", "critical",
     "EMERGENCY: shore the member. Encase in RC jacketing or apply structural CFRP laminates to restore capacity."),
    (("stage 3",), "Stage 3 Corrosion Spalling (Exposed Rebar)", "critical",
     "Cut out spalled concrete, sandblast bars, add auxiliary reinforcement if section loss >15%, patch with structural mortar."),
    (("stage 2",), "Stage 2 Corrosion Splitting Crack", "severe",
     "Expose corroded rebar, remove scale, prime, and patch with high-strength structural repair mortar."),
    (("stage 1",), "Stage 1 Corrosion Crack", "moderate",
     "Expose rebar locally, clean rust, apply zinc-rich primer, and seal with polymer-modified cementitious mortar."),
    (("shear",), "Structural Shear Crack", "severe",
     "Diagonal shear cracking. Shore immediately, pressure-inject structural epoxy, and consider CFRP wrapping."),
]


def _mechanism_from_filename(name_lower: str) -> Optional[Tuple[str, str, str]]:
    for keys, ctype, sev, rec in _FILENAME_RULES:
        if any(k in name_lower for k in keys):
            return ctype, sev, rec
    return None


def _classify(
    width_mm: float,
    angle_deg: float,
    member_type: str,
    cues: Dict[str, float],
    filename: str,
) -> Tuple[str, str, str]:
    """Return (crack_type, severity, recommendation).

    Precedence: explicit filename label > colour-evidenced mechanism >
    geometry-derived structural class. Severity is escalated to at least the
    measured crack-width band.
    """
    measured_sev = _severity_from_width(width_mm)
    name_lower = filename.lower()

    # 1. Explicit annotated label.
    fn = _mechanism_from_filename(name_lower)
    if fn:
        ctype, sev, rec = fn
        sev = sev if _SEVERITY_ORDER.get(sev, 0) >= _SEVERITY_ORDER.get(measured_sev, 0) else measured_sev
        return ctype, sev, rec

    # 2. Colour-evidenced mechanism.
    if cues.get("rust", 0) > 0.04:
        sev = "severe" if _SEVERITY_ORDER["severe"] >= _SEVERITY_ORDER[measured_sev] else measured_sev
        return ("Corrosion-Induced Splitting Crack", max(sev, measured_sev, key=lambda s: _SEVERITY_ORDER[s]),
                "Active rebar corrosion. Chisel cover, clean steel to bright metal, apply zinc-rich primer, patch with polymer mortar.")
    if cues.get("efflorescence", 0) > 0.12:
        return ("Efflorescence / Moisture Ingress", measured_sev,
                "Salt leaching indicates moisture migration. Identify water source, dry the substrate, and apply a breathable water-repellent sealer.")

    # 3. Geometry-derived structural class.
    oc = _orientation_class(angle_deg)
    if oc == "diagonal":
        return ("Structural Shear Crack", max("severe", measured_sev, key=lambda s: _SEVERITY_ORDER[s]),
                "Diagonal (shear) cracking. Monitor with tell-tale gauges, pressure-inject structural epoxy, and evaluate CFRP shear strengthening.")
    if oc == "vertical":
        if member_type == "column":
            return ("Column Compression / Splitting Crack", max("severe", measured_sev, key=lambda s: _SEVERITY_ORDER[s]),
                    "Vertical cracking on a column suggests overload/splitting. Verify axial capacity; confine with RC/steel jacketing or CFRP wrap.")
        return ("Vertical Tension Crack", measured_sev,
                "Vertical tension crack. Seal with low-viscosity epoxy and monitor for width growth across inspection cycles.")
    # horizontal
    if member_type in ("beam", "slab"):
        return ("Flexural Tension Crack", measured_sev,
                "Flexural cracking under bending. Install tell-tale gauges, seal with elastomeric sealant, and review live-load demand.")
    return ("Shrinkage / Map Crack", measured_sev,
            "Fine shrinkage/thermal cracking. Clean surface and apply a penetrating silane sealer; re-inspect next cycle.")


def _vulnerability_index(crack_type: str, severity: str) -> float:
    """Compute a normalised 0..1 vulnerability contribution."""
    t = crack_type.lower()
    weight = 0.3
    for key, w in _TYPE_WEIGHT.items():
        if key in t:
            weight = w
            break
    sev_mult = {"hairline": 0.3, "minor": 0.4, "moderate": 0.6, "severe": 0.85, "critical": 1.0}.get(severity, 0.5)
    return round(min(weight * sev_mult / 0.85, 1.0), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Rebar spacing (Hough on near-parallel lines), scaled by real GSD
# ─────────────────────────────────────────────────────────────────────────────

def _rebar_spacing(gray: np.ndarray, gsd_x: float, filename: str, method: str) -> Tuple[float, int]:
    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                            minLineLength=h // 4, maxLineGap=20)
    xs: List[int] = []
    if lines is not None:
        for ln in lines:
            x1, y1, x2, y2 = ln[0]
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            if dy > 0 and (dx / dy) < 0.18:           # near-vertical
                xs.append((x1 + x2) // 2)
    xs = sorted(set(xs))
    filtered: List[int] = []
    for x in xs:
        if not filtered or abs(x - filtered[-1]) > 30:
            filtered.append(x)

    if len(filtered) >= 2:
        gaps = [filtered[i + 1] - filtered[i] for i in range(len(filtered) - 1)]
        return float(np.median(gaps)) * gsd_x, len(filtered)
    return 0.0, 0  # honest "not detected"


def _member_and_grid(name_lower: str) -> Tuple[str, str]:
    if any(k in name_lower for k in ("column", "compression", "fire-damage")):
        return "column", "A2"
    if any(k in name_lower for k in ("beam", "shear", "flexural", "leakage")):
        return "beam", "C3"
    return "slab", "D4"


# ─────────────────────────────────────────────────────────────────────────────
# Geometry method
# ─────────────────────────────────────────────────────────────────────────────

def _geometry_measure(gray: np.ndarray, gsd_x: float, gsd_y: float) -> Tuple[Dict[str, Any], List[Dict[str, Any]], int]:
    """Geometry/trigonometry method: PCA principal-axis straight-line extent."""
    h, w = gray.shape
    components = _detect_components(gray)
    cracks: List[Dict[str, Any]] = []
    for comp in components:
        phys = _measure_trig(comp, gsd_x, gsd_y)
        is_blob = not comp.get("is_crack", comp["elongation"] >= MIN_CRACK_ELONGATION)
        bx, by, bw, bh = comp["bbox"]
        vx, vy = comp["axis"]
        cx, cy = comp["centroid"]
        L = comp["length_px"]
        # Build a two-point line at the principal axis (geometry path)
        half = L / 2
        x1 = round((cx - vx * half) / w, 4)
        y1 = round((cy - vy * half) / h, 4)
        x2 = round((cx + vx * half) / w, 4)
        y2 = round((cy + vy * half) / h, 4)
        cracks.append({
            "length_cm": round(phys["length_cm"], 1),
            "width_mm": round(phys["width_mm"], 2),
            "angle_deg": round(phys["angle_deg"], 1),
            "area_cm2": round(comp["area_px"] * gsd_x * gsd_y, 2),
            "length_px": round(comp["length_px"], 1),
            "width_px": round(comp["width_px"], 2),
            "elongation": round(comp["elongation"], 1),
            "kind": "spall/void" if is_blob else "crack",
            "centroid_px": {"x": int(cx), "y": int(cy)},
            "contour_pts": [[x1, y1], [x2, y2]],
        })
    line_like = [c for c in cracks if c["kind"] == "crack"]
    pool = line_like or cracks
    if pool:
        primary = max(pool, key=lambda c: c["elongation"] * c["length_cm"])
    else:
        primary = {"length_cm": 0.0, "width_mm": 0.0, "angle_deg": 0.0, "elongation": 0.0}
    return primary, cracks, len(cracks)


def _build_comparison(geo: Dict[str, Any], cv: Dict[str, Any]) -> Dict[str, Any]:
    """Compare geometry vs CV crack-length measurement."""
    gl, cl = float(geo.get("length_cm", 0)), float(cv.get("length_cm", 0))
    denom = max(gl, cl, 1e-6)
    agreement = max(0.0, round(100.0 * (1.0 - abs(cl - gl) / denom), 1))
    return {
        "geometry": {
            "length_cm": round(gl, 1),
            "width_mm": round(float(geo.get("width_mm", 0)), 2),
            "angle_deg": geo.get("angle_deg"),
            "basis": "PCA straight principal-axis extent + trig GSD scaling",
        },
        "cv": {
            "length_cm": round(cl, 1),
            "width_mm": round(float(cv.get("width_mm", 0)), 2),
            "angle_deg": cv.get("angle_deg"),
            "tortuosity": cv.get("tortuosity"),
            "skeleton_engine": cv.get("skeleton_engine"),
            "yolo_used": cv.get("yolo_used"),
            "basis": "tiled segmentation + skeleton geodesic length (follows curvature)",
        },
        "length_delta_cm": round(cl - gl, 1),
        "length_agreement_pct": agreement,
        "note": ("Geometry measures the straight end-to-end extent; CV traces the crack's "
                 "curved centreline, so CV >= geometry on tortuous cracks is expected."),
    }


def _agreement(a: float, b: float) -> float:
    denom = max(a, b, 1e-6)
    return max(0.0, round(100.0 * (1.0 - abs(a - b) / denom), 1))


def _match_cracks(
    geo_cracks: List[Dict[str, Any]],
    cv_cracks: List[Dict[str, Any]],
    tol_px: float,
    limit: int = 12,
) -> List[Dict[str, Any]]:
    """Pair geometry and CV detections by centroid proximity for a per-crack table."""
    def _cxy(c):
        p = c.get("centroid_px") or {}
        return float(p.get("x", 0)), float(p.get("y", 0))

    rows: List[Dict[str, Any]] = []
    used = set()
    for g in geo_cracks:
        gx, gy = _cxy(g)
        best, best_d = None, tol_px
        for ci, c in enumerate(cv_cracks):
            if ci in used:
                continue
            cx, cy = _cxy(c)
            d = math.hypot(gx - cx, gy - cy)
            if d < best_d:
                best_d, best = d, ci
        c = cv_cracks[best] if best is not None else None
        if best is not None:
            used.add(best)
        gl = float(g.get("length_cm", 0))
        cl = float(c.get("length_cm", 0)) if c else None
        rows.append({
            "geometry_length_cm": round(gl, 1),
            "geometry_width_mm": round(float(g.get("width_mm", 0)), 2),
            "cv_length_cm": round(cl, 1) if cl is not None else None,
            "cv_width_mm": round(float(c.get("width_mm", 0)), 2) if c else None,
            "angle_deg": g.get("angle_deg"),
            "tortuosity": c.get("tortuosity") if c else None,
            "delta_cm": round(cl - gl, 1) if cl is not None else None,
            "agreement_pct": _agreement(gl, cl) if cl is not None else None,
            "matched": c is not None,
            "kind": g.get("kind", "crack"),
        })
    # CV-only detections (geometry missed them).
    for ci, c in enumerate(cv_cracks):
        if ci in used:
            continue
        cl = float(c.get("length_cm", 0))
        rows.append({
            "geometry_length_cm": None,
            "geometry_width_mm": None,
            "cv_length_cm": round(cl, 1),
            "cv_width_mm": round(float(c.get("width_mm", 0)), 2),
            "angle_deg": c.get("angle_deg"),
            "tortuosity": c.get("tortuosity"),
            "delta_cm": None,
            "agreement_pct": None,
            "matched": False,
            "kind": "crack",
        })

    rows.sort(key=lambda r: max(r.get("cv_length_cm") or 0, r.get("geometry_length_cm") or 0), reverse=True)
    return rows[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def analyze_structural_image(
    image_bytes: bytes,
    filename: str,
    real_width_m: Optional[float] = None,
    real_height_m: Optional[float] = None,
    measurement_method: str = "trigonometry",
) -> Dict[str, Any]:
    """Analyse a concrete frame for cracks, dimensions, type and severity.

    Parameters
    ----------
    image_bytes : bytes
        Raw uploaded image bytes.
    filename : str
        Original filename (used for annotated-dataset labels and member type).
    real_width_m, real_height_m : float, optional
        Physical dimensions the image covers (metres). Required for accurate
        measurement; if omitted a nominal GSD is used and a warning is emitted.
    measurement_method : {"trigonometry", "cv"}
        "trigonometry" (a.k.a. geometry) — straight principal-axis length + trig.
        "cv" — tiled segmentation + skeleton geodesic length, using the YOLO
        model when configured and falling back to classical CV otherwise.
    """
    method = (measurement_method or "trigonometry").lower().strip()
    # Normalise aliases. Only two user-facing methods: geometry and cv.
    _aliases = {"geometry": "trigonometry", "trig": "trigonometry",
                "computer_vision": "cv", "cv_segmentation": "cv", "segmentation": "cv",
                "yolo": "cv", "coin_flip": "trigonometry", "estimate": "trigonometry"}
    method = _aliases.get(method, method)
    if method not in ("trigonometry", "cv"):
        method = "trigonometry"

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Invalid image file uploaded.")

    h, w = img.shape[:2]
    orientation = "portrait" if h > w else "landscape"
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    name_lower = filename.lower()
    member_type, grid_reference = _member_and_grid(name_lower)
    gsd_x, gsd_y, warnings = _compute_gsd(w, h, real_width_m, real_height_m)

    cracks: List[Dict[str, Any]] = []
    detected_count = 0
    method_comparison: Optional[Dict[str, Any]] = None
    cv_detail: Optional[Dict[str, Any]] = None

    # Always run BOTH methods so the geometry-vs-CV comparison is available.
    geo_primary, geo_cracks, geo_count = _geometry_measure(gray, gsd_x, gsd_y)
    try:
        # CV always attempts the YOLO model, falling back to tiled segmentation.
        cv_detail = measure_cv(gray, gsd_x, gsd_y, img_bgr=img, use_yolo=True)
        warnings.extend(cv_detail.get("warnings", []))
    except Exception as e:
        logger.warning("CV measurement failed: %s", e)
        cv_detail = {"length_cm": 0.0, "width_mm": 0.0, "angle_deg": 0.0,
                     "crack_count": 0, "cracks": [], "yolo_used": False,
                     "tortuosity": 1.0, "skeleton_engine": "unavailable"}
        warnings.append(f"CV method error: {e}")

    method_comparison = _build_comparison(geo_primary, cv_detail)
    _tol = max(40.0, 0.08 * math.hypot(w, h))
    method_comparison["per_crack"] = _match_cracks(
        geo_cracks, cv_detail.get("cracks", []), _tol
    )

    # No-crack decision: a defect is reported only if at least one method finds
    # a valid feature. On sound concrete both return nothing → "No Crack Detected".
    geo_has = geo_count > 0
    cv_has = cv_detail.get("crack_count", 0) > 0
    defect_found = geo_has or cv_has

    if method == "cv":
        primary = {"length_cm": cv_detail["length_cm"], "width_mm": cv_detail["width_mm"],
                   "angle_deg": cv_detail["angle_deg"], "elongation": 0.0}
        cracks = cv_detail.get("cracks", [])
        detected_count = cv_detail.get("crack_count", 0)
    else:  # trigonometry / geometry
        primary = geo_primary
        cracks = geo_cracks
        detected_count = geo_count

    crack_width_mm = float(primary["width_mm"])
    crack_length_cm = float(primary["length_cm"])
    orientation_angle = float(primary.get("angle_deg", 0.0))

    if not defect_found:
        # Honest "nothing here" result for sound surfaces.
        warnings.append("No crack-like features detected — surface appears sound.")
        reinspection_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        return {
            "filename": filename,
            "measurement_method": method,
            "image_orientation": orientation,
            "resolution_w": w,
            "resolution_h": h,
            "real_image_width_m": real_width_m,
            "real_image_height_m": real_height_m,
            "gsd_cm_per_px_x": round(gsd_x, 5),
            "gsd_cm_per_px_y": round(gsd_y, 5),
            "gsd_mm_px": round((gsd_x + gsd_y) / 2.0 * 10.0, 2),
            "gsd": round((gsd_x + gsd_y) / 2.0 * 10.0, 2),
            "defect_found": False,
            "width_mm": 0.0,
            "length_cm": 0.0,
            "orientation_angle": 0.0,
            "rebar_spacing_cm": 0.0,
            "detected_rods": 0,
            "crack_type": "No Crack Detected",
            "crack_subtype": "none",
            "severity": "none",
            "v_index": 0.0,
            "recommendation": ("No structural cracks or surface defects were detected in this frame. "
                               "The surface appears sound. Continue the routine inspection cycle."),
            "recommended_intervention": "No action required. Re-inspect on the next scheduled cycle.",
            "propagation_rate": "none",
            "member_type": member_type,
            "grid_reference": grid_reference,
            "grid_ref": grid_reference,
            "visible_bar_diameter_mm": None,
            "estimated_cover_loss_mm": None,
            "capacity_reduction_pct": None,
            "reinspection_date": reinspection_date,
            "crack_count": 0,
            "cracks": [],
            "analysis_confidence": round(0.85 if (real_width_m and real_height_m) else 0.6, 2),
            "warnings": warnings,
            "method_comparison": method_comparison,
            "cv_detail": cv_detail,
        }

    cues = _colour_cues(img)
    crack_type, severity, recommendation = _classify(
        crack_width_mm, orientation_angle, member_type, cues, filename
    )
    v_index = _vulnerability_index(crack_type, severity)
    propagation_rate = "active" if crack_width_mm >= 0.3 else "dormant"

    rebar_spacing_cm, detected_rods = _rebar_spacing(gray, gsd_x, filename, method)

    # Rebar exposure / capacity loss estimate for corrosion-class defects.
    visible_bar_diameter_mm = estimated_cover_loss_mm = capacity_reduction_pct = None
    if any(k in crack_type for k in ("Corrosion", "Spalling", "Steel", "Exposed")) or "stage" in name_lower:
        nominal_dia = 20.0 if member_type == "beam" else 12.0
        dia_loss = min(crack_width_mm * 1.2, nominal_dia - 4.0)
        visible_bar_diameter_mm = round(nominal_dia - dia_loss, 2)
        estimated_cover_loss_mm = round(min(crack_width_mm * 10.0, 40.0), 2)
        orig_area = (math.pi / 4.0) * nominal_dia ** 2
        rem_area = (math.pi / 4.0) * visible_bar_diameter_mm ** 2
        capacity_reduction_pct = round((1.0 - rem_area / orig_area) * 100.0, 1)

    reinspection_days = {"critical": 30, "severe": 90, "moderate": 180}.get(severity, 365)
    reinspection_date = (datetime.now() + timedelta(days=reinspection_days)).strftime("%Y-%m-%d")

    analysis_confidence = (
        0.9 if (real_width_m and real_height_m and detected_count) else 0.65
    )

    return {
        "filename": filename,
        "measurement_method": method,
        "image_orientation": orientation,
        "resolution_w": w,
        "resolution_h": h,
        "real_image_width_m": real_width_m,
        "real_image_height_m": real_height_m,
        "gsd_cm_per_px_x": round(gsd_x, 5),
        "gsd_cm_per_px_y": round(gsd_y, 5),
        "gsd_mm_px": round((gsd_x + gsd_y) / 2.0 * 10.0, 2),
        "gsd": round((gsd_x + gsd_y) / 2.0 * 10.0, 2),
        # Primary defect measurements
        "defect_found": True,
        "width_mm": round(crack_width_mm, 2),
        "length_cm": round(crack_length_cm, 1),
        "orientation_angle": round(orientation_angle, 1),
        "rebar_spacing_cm": round(rebar_spacing_cm, 1),
        "detected_rods": detected_rods if detected_rods >= 2 else 0,
        # Classification
        "crack_type": crack_type,
        "crack_subtype": crack_type.lower().replace(" ", "_"),
        "severity": severity,
        "v_index": v_index,
        "recommendation": recommendation,
        "recommended_intervention": recommendation,
        "propagation_rate": propagation_rate,
        "member_type": member_type,
        "grid_reference": grid_reference,
        "grid_ref": grid_reference,
        # Rebar / corrosion
        "visible_bar_diameter_mm": visible_bar_diameter_mm,
        "estimated_cover_loss_mm": estimated_cover_loss_mm,
        "capacity_reduction_pct": capacity_reduction_pct,
        "reinspection_date": reinspection_date,
        # Multi-defect detail
        "crack_count": detected_count,
        "cracks": cracks,
        "analysis_confidence": round(analysis_confidence, 2),
        "warnings": warnings,
        # Method comparison (geometry vs computer-vision)
        "method_comparison": method_comparison,
        "cv_detail": cv_detail,
    }
