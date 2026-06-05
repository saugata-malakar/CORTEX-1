import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional

IS_1786_STANDARD_DIAMETERS_MM = [8, 10, 12, 16, 20, 25, 32]
MIN_COVER_BY_EXPOSURE = {
    "mild":       20,
    "moderate":   30,
    "severe":     45,
    "very_severe": 50,
    "extreme":    75,
}

@dataclass
class RebarResult:
    grid_ref: str
    estimated_diameter_mm: float
    assumed_standard_diameter_mm: int
    measured_spacing_mm: float
    required_cover_mm: int
    measured_cover_mm: float
    cover_status: str          # "Adequate" or "Deficient"
    bar_count_visible: int
    confidence: float


def detect_rebars(
    mosaic_region: np.ndarray,
    gsd_mm_per_px: float,
    exposure_class: str = "moderate",
    grid_ref: str = "UNKNOWN"
) -> Optional[RebarResult]:
    """
    Detects rebar from an exposed spall or corrosion region.
    mosaic_region: cropped numpy array of the exposed area (BGR)
    gsd_mm_per_px: ground sampling distance from pipeline calibration
    """
    gray = cv2.cvtColor(mosaic_region, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150, apertureSize=3)

    # Hough line detection — finds parallel bar lines
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=40,
        minLineLength=30,
        maxLineGap=10
    )

    if lines is None or len(lines) < 2:
        return None

    # Filter to near-parallel lines (same dominant angle)
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180
        angles.append(angle)

    median_angle = np.median(angles)
    parallel_lines = [
        l for l, a in zip(lines, angles)
        if abs(a - median_angle) < 15
    ]

    if len(parallel_lines) < 2:
        return None

    # Compute perpendicular distances between parallel lines
    def line_midpoint(l):
        x1, y1, x2, y2 = l[0]
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    midpoints = sorted(
        [line_midpoint(l) for l in parallel_lines],
        key=lambda p: p[0] if median_angle > 45 else p[1]
    )

    spacings_px = []
    for i in range(len(midpoints) - 1):
        dx = midpoints[i+1][0] - midpoints[i][0]
        dy = midpoints[i+1][1] - midpoints[i][1]
        spacings_px.append(np.sqrt(dx**2 + dy**2))

    avg_spacing_px = float(np.mean(spacings_px)) if spacings_px else 0.0
    spacing_mm = avg_spacing_px * gsd_mm_per_px

    # Estimate bar diameter from line thickness
    line_widths_px = []
    for line in parallel_lines:
        x1, y1, x2, y2 = line[0]
        mask = np.zeros_like(gray)
        cv2.line(mask, (x1, y1), (x2, y2), 255, 1)
        profile = gray[mask > 0]
        if len(profile) > 0:
            width_estimate = np.sum(profile > 128) * gsd_mm_per_px
            line_widths_px.append(width_estimate)

    raw_diameter_mm = float(np.median(line_widths_px)) if line_widths_px else 12.0
    standard_dia = min(
        IS_1786_STANDARD_DIAMETERS_MM,
        key=lambda d: abs(d - raw_diameter_mm)
    )

    # Cover depth from edge of region to first bar midpoint
    region_height_px = mosaic_region.shape[0]
    first_bar_y = min(midpoints, key=lambda p: p[1])[1]
    cover_px = first_bar_y
    cover_mm = cover_px * gsd_mm_per_px

    required_cover = MIN_COVER_BY_EXPOSURE.get(exposure_class, 30)
    cover_status = "Adequate" if cover_mm >= required_cover else "Deficient"

    confidence = min(1.0, len(parallel_lines) / 10.0)

    return RebarResult(
        grid_ref=grid_ref,
        estimated_diameter_mm=round(raw_diameter_mm, 1),
        assumed_standard_diameter_mm=standard_dia,
        measured_spacing_mm=round(spacing_mm, 1),
        required_cover_mm=required_cover,
        measured_cover_mm=round(cover_mm, 1),
        cover_status=cover_status,
        bar_count_visible=len(parallel_lines),
        confidence=round(confidence, 2)
    )


def should_trigger_rebar_analysis(defect: dict) -> bool:
    """
    Returns True if rebar analysis should run for this defect.
    Triggered by corrosion cracks or large spalling areas.
    """
    subtype = defect.get("crack_subtype", "")
    spall_area = defect.get("area_cm2", 0)
    return subtype == "corrosion_induced" or spall_area >= 50.0
