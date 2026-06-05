"""
quantifier.py — Defect Geometry Quantification Module
=====================================================

Performs precise metric measurements on binary defect masks:
  - Skeletonization-based crack length estimation with diagonal step weighting.
  - Perpendicular crack width profiling via Euclidean Distance Transform.
  - Defect area computation with contour vs. pixel-sum cross-validation.
  - Morphological gap closing and defect fragment linking.
  - Defect classification based on elongation ratio, solidity, and size.

References:
  - [R7] Yang et al. (2018) Automated Crack Measurement on Concrete Mosaics.
  - [R9] Liu et al. (2019) Deep Learning-Based Bridge Crack Detection and Quantification.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    from skimage.morphology import skeletonize
except ImportError:
    # Fallback to OpenCV thin if scikit-image is not installed
    def skeletonize(image: np.ndarray) -> np.ndarray:  # type: ignore[misc]
        """Simple morphological thinning fallback if skimage is unavailable."""
        size = np.size(image)
        skel = np.zeros(image.shape, np.uint8)
        ret, img = cv2.threshold((image * 255).astype(np.uint8), 127, 255, 0)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        done = False
        while not done:
            eroded = cv2.erode(img, element)
            temp = cv2.dilate(eroded, element)
            temp = cv2.subtract(img, temp)
            skel = cv2.bitwise_or(skel, temp)
            img = eroded.copy()
            zeros = size - cv2.countNonZero(img)
            if zeros == size:
                done = True
        return skel > 0

logger = logging.getLogger(__name__)


class DefectQuantifier:
    """Measures physical dimensions of detected structural defects using GSD.

    Parameters
    ----------
    config : dict
        Pipeline configuration dict (uses 'quantification' parameters).
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        
        # Load parameters with safe defaults
        quant_cfg = config.get("quantification", {})
        self.skeleton_min_length_px = quant_cfg.get("skeleton_min_length_px", 5)
        self.width_sample_points = quant_cfg.get("width_sample_points", 10)
        self.area_cv_tolerance = quant_cfg.get("area_cross_validation_tolerance", 0.02)
        self.elongation_crack_threshold = quant_cfg.get("elongation_crack_threshold", 5.0)
        self.elongation_joint_range = quant_cfg.get("elongation_joint_range", [2.0, 4.0])
        self.morph_dilation_kernel = quant_cfg.get("morph_dilation_kernel", 3)
        self.morph_dilation_iterations = quant_cfg.get("morph_dilation_iterations", 2)
        
        from src.rebar_detector import RebarDetector
        self.rebar_detector = RebarDetector(config)
        
        logger.info("DefectQuantifier initialized.")

    def link_fragments(self, mask: np.ndarray) -> np.ndarray:
        """Apply morphological dilation to close small gaps in defect masks.

        Parameters
        ----------
        mask : np.ndarray
            Binary mask (0 or 255).

        Returns
        -------
        np.ndarray
            Connected/linked binary mask.
        """
        if self.morph_dilation_iterations == 0:
            return mask
            
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, 
            (self.morph_dilation_kernel, self.morph_dilation_kernel)
        )
        linked = cv2.dilate(mask, kernel, iterations=self.morph_dilation_iterations)
        return linked

    def extract_contours(self, mask: np.ndarray) -> List[np.ndarray]:
        """Find individual connected defect components and extract their contours.

        Parameters
        ----------
        mask : np.ndarray
            Binary mask (0 or 255).

        Returns
        -------
        list of np.ndarray
            Contours found in the mask.
        """
        # Ensure image is uint8 single-channel
        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8)
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        return list(contours)

    def classify_shape(self, contour: np.ndarray) -> Tuple[str, float, float]:
        """Classify defect shape using aspect ratios, elongation, and solidity.

        Parameters
        ----------
        contour : np.ndarray
            Contour points.

        Returns
        -------
        defect_type : str
            Classified type: 'crack', 'joint_match', or 'spalling/stain'.
        elongation : float
            Major axis length / minor axis length.
        solidity : float
            Contour area / convex hull area.
        """
        area = cv2.contourArea(contour)
        if area <= 0:
            return "stain", 1.0, 0.0
            
        # Get minimum area bounding rectangle
        rect = cv2.minAreaRect(contour)
        (cx, cy), (w, h), angle = rect
        
        # Elongation = long side / short side
        major = max(w, h)
        minor = min(w, h)
        elongation = major / minor if minor > 0 else 1.0
        
        # Solidity = area / hull_area
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0.0
        
        # Classification logic
        if elongation >= self.elongation_crack_threshold:
            defect_type = "crack"
        elif self.elongation_joint_range[0] <= elongation <= self.elongation_joint_range[1] and solidity > 0.8:
            defect_type = "construction_joint"
        else:
            defect_type = "spalling"
            
        return defect_type, elongation, solidity

    def measure_crack_length(self, mask: np.ndarray, gsd_cm_per_px: float) -> float:
        """Compute the length of a crack centerline via skeletonization.

        Parameters
        ----------
        mask : np.ndarray
            Binary mask (0 or 255).
        gsd_cm_per_px : float
            Ground Sampling Distance.

        Returns
        -------
        float
            Centerline length in centimeters.
        """
        # Ensure mask is boolean for skimage skeletonize
        binary = mask > 0
        if not np.any(binary):
            return 0.0
            
        skel = skeletonize(binary)
        
        # Count connections to weight diagonal steps properly
        y, x = np.where(skel)
        coords = list(zip(x, y))
        coord_set = set(coords)
        
        length_px = 0.0
        for px, py in coords:
            # Orthogonal steps
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                if (px + dx, py + dy) in coord_set:
                    length_px += 0.5  # divided by 2 because each edge is visited twice
            # Diagonal steps
            for dx, dy in [(-1, -1), (1, 1), (-1, 1), (1, -1)]:
                if (px + dx, py + dy) in coord_set:
                    length_px += 0.5 * 1.4142  # sqrt(2) / 2
                    
        return length_px * gsd_cm_per_px

    def measure_crack_width(
        self,
        mask: np.ndarray,
        gsd_cm_per_px: float,
        n_points: int = 10,
    ) -> Tuple[float, float, List[float]]:
        """Compute width profile of a crack using Distance Transform on the skeleton.

        Parameters
        ----------
        mask : np.ndarray
            Binary mask (0 or 255).
        gsd_cm_per_px : float
            Ground Sampling Distance (cm/px).
        n_points : int
            Number of points along the skeleton to sample widths.

        Returns
        -------
        median_width_mm : float
            Median width in millimeters.
        max_width_mm : float
            Maximum width in millimeters.
        width_profile_mm : list of float
            Full sampled width profile in millimeters.
        """
        binary = mask > 0
        if not np.any(binary):
            return 0.0, 0.0, []
            
        skel = skeletonize(binary)
        
        # Distance transform yields shortest distance to background (in pixels)
        # We use L2 Euclidean distance with a 5x5 mask for higher accuracy
        dt = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
        
        # Width at any skeleton point is 2 * distance_transform value
        widths_px = 2.0 * dt[skel]
        
        if len(widths_px) == 0:
            return 0.0, 0.0, []
            
        # Sample N evenly-spaced points along the skeleton to form a profile
        indices = np.linspace(0, len(widths_px) - 1, min(n_points, len(widths_px)), dtype=int)
        sampled_widths_px = widths_px[indices]
        
        # Convert GSD from cm/px to mm/px by multiplying by 10.0
        gsd_mm_per_px = gsd_cm_per_px * 10.0
        
        widths_mm = [float(w * gsd_mm_per_px) for w in sampled_widths_px]
        median_width_mm = float(np.median(widths_px) * gsd_mm_per_px)
        max_width_mm = float(np.max(widths_px) * gsd_mm_per_px)
        
        return median_width_mm, max_width_mm, widths_mm

    def measure_area(
        self,
        mask: np.ndarray,
        gsd_cm_per_px: float,
        contour: Optional[np.ndarray] = None,
    ) -> float:
        """Measure defect area and cross-validate with pixel count area.

        Parameters
        ----------
        mask : np.ndarray
            Binary mask (0 or 255).
        gsd_cm_per_px : float
            Ground Sampling Distance (cm/px).
        contour : np.ndarray, optional
            Optional pre-extracted contour to speed up calculation.

        Returns
        -------
        area_cm2 : float
            Validated area in square centimeters.
        """
        # Area from pixel count
        pixel_count = np.sum(mask > 0)
        pixel_area = pixel_count * (gsd_cm_per_px ** 2)
        
        # Area from contour green theorem
        if contour is None:
            contours = self.extract_contours(mask)
            contour_area = sum(cv2.contourArea(c) for c in contours) if contours else 0.0
        else:
            contour_area = cv2.contourArea(contour)
            
        contour_area_metric = contour_area * (gsd_cm_per_px ** 2)
        
        if contour_area_metric == 0:
            return float(pixel_area)
            
        # Cross-validation: check if they agree within tolerance
        diff = abs(pixel_area - contour_area_metric) / max(pixel_area, 1e-6)
        if diff > self.area_cv_tolerance:
            logger.debug(
                "Area cross-validation warning: pixel area (%.2f cm2) and contour area (%.2f cm2) "
                "differ by %.1f%% (> %.1f%%). Defaulting to pixel count.",
                pixel_area, contour_area_metric, diff * 100, self.area_cv_tolerance * 100
            )
            return float(pixel_area)
            
        # Return average of the two if they agree
        return float((pixel_area + contour_area_metric) / 2.0)

    def classify_crack_type(
        self,
        contour: np.ndarray,
        width_mm: float,
        length_cm: float,
        bbox_px: List[int],
        image_shape: Tuple[int, int],
        confidence: float
    ) -> str:
        """Classify a generic crack into one of the 7 senior civil engineering classes."""
        h, w = image_shape[:2]
        bx, by, bw, bh = bbox_px
        
        # Get rotated bounding box angle
        rect = cv2.minAreaRect(contour)
        angle = abs(rect[2])
        if angle > 45:
            angle = 90 - angle # normalize to [0, 45] range relative to axis
            
        # 1. Shrinkage Crack
        # Very fine, random pattern (high number of contour vertices or branching)
        if width_mm < 0.25:
            return "shrinkage_crack"
            
        # 2. Shear Crack
        # Diagonal roughly 45 degrees, near supports (left or right 25% of image width)
        is_near_support = (bx < w * 0.25) or (bx + bw > w * 0.75)
        is_diagonal = (30 <= angle <= 60)
        if is_diagonal and is_near_support and width_mm > 0.5:
            return "shear_crack"
            
        # 3. Corrosion-induced Crack
        # Longitudinal crack parallel to reinforcement (vertical or horizontal, often near edges or along rebars)
        is_longitudinal = (angle < 15 or angle > 75)
        if is_longitudinal and (width_mm > 1.0 or confidence > 0.85):
            return "corrosion_crack"
            
        # 4. Flexural Crack
        # Vertical, appear at the bottom of beams and slabs
        is_bottom = (by + bh > h * 0.65)
        is_vertical = (angle > 70)
        if is_vertical and is_bottom:
            return "flexural_crack"
            
        # 5. Settlement Crack
        # Diagonal starting from corners of openings
        if 20 <= angle <= 70 and (by < h * 0.4):
            return "settlement_crack"
            
        # 6. Compression Crack
        # Vertical splitting cracks in columns (vertical and narrow)
        is_vertical_split = (angle > 80) and (bh / max(bw, 1e-6) > 4.0)
        if is_vertical_split:
            return "compression_crack"
            
        # 7. Fatigue Crack
        # Star-shaped or branching pattern (high convex hull defect count)
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        area = cv2.contourArea(contour)
        solidity = area / hull_area if hull_area > 0 else 1.0
        if solidity < 0.4:
            return "fatigue_crack"
            
        # Default fallback
        return "flexural_crack" if width_mm > 0.5 else "shrinkage_crack"

    def classify_crack_subtype(
        self,
        contour: np.ndarray,
        mask: np.ndarray,
        gsd_mm_per_px: float
    ) -> dict:
        """
        Returns crack_subtype, orientation_angle_deg, and risk_multiplier.
        Called only when defect type is already classified as 'crack'.
        """
        rect = cv2.minAreaRect(contour)
        angle = rect[2]  # degrees from horizontal

        # Normalise angle to 0-180
        if angle < 0:
            angle += 180

        # Classify by orientation
        if angle < 15 or angle > 165:
            subtype = "flexural"
            risk_multiplier = 1.0
        elif 30 <= angle <= 60 or 120 <= angle <= 150:
            subtype = "shear"
            risk_multiplier = 2.5   # most dangerous — brittle failure
        elif 15 < angle < 30 or 150 < angle < 165:
            subtype = "settlement"
            risk_multiplier = 1.8
        else:
            subtype = "unknown"
            risk_multiplier = 1.0

        # Check for map cracking pattern (shrinkage)
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        if perimeter > 0:
            compactness = (4 * np.pi * area) / (perimeter ** 2)
            if compactness < 0.1 and area < 500:  # px² threshold
                subtype = "shrinkage_crazing"
                risk_multiplier = 0.8

        # Check for corrosion — elongated crack parallel to surface edge
        bounding_rect = cv2.boundingRect(contour)
        aspect_ratio = bounding_rect[2] / max(bounding_rect[3], 1)
        if aspect_ratio > 8 and (angle < 10 or angle > 170):
            subtype = "corrosion_induced"
            risk_multiplier = 2.0

        return {
            "crack_subtype": subtype,
            "orientation_angle_deg": round(float(angle), 1),
            "risk_multiplier": risk_multiplier
        }

    def quantify_defect(
        self,
        mask: np.ndarray,
        gsd_cm_per_px: float,
        defect_type: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """Quantify a single defect instance and return its physical measurements.

        Parameters
        ----------
        mask : np.ndarray
            Binary mask (0 or 255) for this single defect instance.
        gsd_cm_per_px : float
            Ground Sampling Distance (cm/px).
        defect_type : str
            API-reported defect type (e.g. 'crack', 'spalling').
        confidence : float
            API-reported confidence score.

        Returns
        -------
        dict
            Defect instance measurements matching the output schema.
        """
        linked = self.link_fragments(mask)
        contours = self.extract_contours(linked)
        
        if not contours:
            return {
                "defect_id": "unknown",
                "type": defect_type,
                "length_cm": 0.0,
                "width_mm": 0.0,
                "area_cm2": 0.0,
                "bbox_px": [0, 0, 0, 0],
                "centroid_px": [0, 0],
                "confidence_score": float(confidence),
                "severity_class": "hairline",
                "elongation_ratio": 1.0,
                "solidity": 0.0,
            }
            
        # Quantify based on the largest contour if multiple were returned by link_fragments
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Aspect metrics
        shape_type, elongation, solidity = self.classify_shape(largest_contour)
        
        # Bounding box
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Centroid
        moments = cv2.moments(largest_contour)
        if moments["m00"] > 0:
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])
        else:
            cx = x + w // 2
            cy = y + h // 2
            
        # Physical Measurements
        area_cm2 = self.measure_area(linked, gsd_cm_per_px, largest_contour)
        
        # Bounding box angle & orientation
        rect = cv2.minAreaRect(largest_contour)
        angle = abs(rect[2])
        if angle > 45:
            angle = 90 - angle
        orientation_angle = round(float(angle), 1)

        # Infer Member Type and Location Grid Reference System
        h_img = mask.shape[0]
        w_img = mask.shape[1]
        if cy > h_img * 0.65:
            member_type = "beam"
        elif cx < w_img * 0.25 or cx > w_img * 0.75:
            member_type = "column"
        else:
            member_type = "slab"

        # Elevation Grid Reference (A-F, 1-8)
        row_idx = int((h_img - cy) / (h_img / 6.0))
        row_idx = max(0, min(5, row_idx))
        row_letter = ["A", "B", "C", "D", "E", "F"][row_idx]
        col_idx = int(cx / (w_img / 8.0))
        col_idx = max(0, min(7, col_idx))
        grid_reference = f"{row_letter}{col_idx + 1}"

        # Length & width analysis
        if defect_type == "crack" or shape_type == "crack":
            length_cm = self.measure_crack_length(linked, gsd_cm_per_px)
            median_w_mm, max_w_mm, profile = self.measure_crack_width(linked, gsd_cm_per_px, self.width_sample_points)
            width_mm = median_w_mm
            
            # Classification into 7 detailed civil crack subtypes
            defect_type = self.classify_crack_type(largest_contour, width_mm, length_cm, [x, y, w, h], mask.shape, confidence)
        else:
            # For spalls, length is approximated by bounding box diagonal, width by short side
            length_cm = float(np.sqrt(w**2 + h**2) * gsd_cm_per_px)
            width_mm = float(min(w, h) * gsd_cm_per_px * 10.0)
            max_w_mm = width_mm

        # Rebar Exposure Sub-routine (runs on corrosion cracks)
        visible_bar_diameter_mm = None
        estimated_cover_loss_mm = None
        capacity_reduction_pct = None
        
        if defect_type in ["corrosion_crack", "corrosion"]:
            rebar_res = self.rebar_detector.analyze_exposed_rebar(
                linked, gsd_cm_per_px, defect_type, width_mm, area_cm2, member_type
            )
            visible_bar_diameter_mm = rebar_res["visible_bar_diameter_mm"]
            estimated_cover_loss_mm = rebar_res["estimated_cover_loss_mm"]
            capacity_reduction_pct = rebar_res["capacity_reduction_pct"]

        # Delamination Area (m2) for spalls
        delamination_area_m2 = round(area_cm2 / 10000.0, 5) if defect_type == "spalling" else None

        # Propagation Rate / Activity Status (active vs dormant)
        propagation_rate = "active" if width_mm >= 0.3 else "dormant"

        # Auto-populate Intervention Recommendation and Re-inspection Date
        if "shear" in defect_type:
            recommended_intervention = "Structural CFRP wrapping and high-pressure epoxy resin injection"
            reinspection_days = 30
        elif "corrosion" in defect_type:
            recommended_intervention = "Expose bar, mechanical rust removal, zinc-rich coating, polymer-modified repair mortar"
            reinspection_days = 90
        elif "compression" in defect_type:
            recommended_intervention = "Emergency temporary support props and concrete column steel plate jacketing"
            reinspection_days = 30
        elif width_mm < 0.2:
            recommended_intervention = "Surface treatment with silane-siloxane penetrating hydrophobic sealer"
            reinspection_days = 365
        elif width_mm < 1.0:
            recommended_intervention = "V-groove routing and sealing with elastomeric polyurethane compound"
            reinspection_days = 180
        else:
            recommended_intervention = "Stitching using helical stainless steel bars embedded in non-shrink grout"
            reinspection_days = 90

        from datetime import datetime, timedelta
        reinspection_date = (datetime.now() + timedelta(days=reinspection_days)).strftime("%Y-%m-%d")

        # Determine Severity Class based on width
        # Hairline: <0.2mm, Fine: 0.2-1mm, Medium: 1-5mm, Wide: >5mm
        if width_mm < 0.2:
            severity = "hairline"
        elif width_mm < 1.0:
            severity = "fine"
        elif width_mm < 5.0:
            severity = "medium"
        else:
            severity = "wide"
            
        # Crack subtype analysis
        if defect_type in ["crack", "shear_crack", "flexural_crack", "corrosion_crack", "settlement_crack", "compression_crack", "fatigue_crack", "shrinkage_crack"]:
            subtype_info = self.classify_crack_subtype(largest_contour, linked, gsd_cm_per_px * 10.0)
            crack_subtype = subtype_info["crack_subtype"]
            orientation_angle_deg = subtype_info["orientation_angle_deg"]
            risk_multiplier = subtype_info["risk_multiplier"]
        else:
            crack_subtype = None
            orientation_angle_deg = None
            risk_multiplier = 1.0

        from src.grid_utils import assign_grid_ref
        grid_ref_new = assign_grid_ref(
            centroid_x=cx,
            centroid_y=cy,
            mosaic_width=mask.shape[1],
            mosaic_height=mask.shape[0]
        )

        return {
            "type": defect_type,
            "length_cm": round(length_cm, 3),
            "width_mm": round(width_mm, 3),
            "max_width_mm": round(max_w_mm, 3),
            "area_cm2": round(area_cm2, 3),
            "bbox_px": [int(x), int(y), int(w), int(h)],
            "centroid_px": [int(cx), int(cy)],
            "confidence_score": float(confidence),
            "severity_class": severity,
            "elongation_ratio": round(float(elongation), 2),
            "solidity": round(float(solidity), 3),
            "visible_bar_diameter_mm": visible_bar_diameter_mm,
            "estimated_cover_loss_mm": estimated_cover_loss_mm,
            "capacity_reduction_pct": capacity_reduction_pct,
            "orientation_angle": orientation_angle,
            "propagation_rate": propagation_rate,
            "delamination_area_m2": delamination_area_m2,
            "grid_reference": grid_reference, # Legacy grid reference
            "grid_ref": grid_ref_new,         # New accurate grid reference
            "member_type": member_type,
            "crack_subtype": crack_subtype,
            "orientation_angle_deg": orientation_angle_deg,
            "risk_multiplier": risk_multiplier,
            "member_type": member_type,
            "recommended_intervention": recommended_intervention,
            "reinspection_date": reinspection_date
        }

    def quantify_all(
        self,
        extracted_defects: List[Tuple[np.ndarray, str, float]],
        gsd_cm_per_px: float,
    ) -> List[Dict[str, Any]]:
        """Batch-process and quantify a list of extracted defect masks.

        Parameters
        ----------
        extracted_defects : list of tuple
            List of tuples from CortexAdapter.extract_masks(): (mask, type, confidence).
        gsd_cm_per_px : float
            Ground Sampling Distance (cm/px).

        Returns
        -------
        list of dict
            List of quantified defect dicts.
        """
        results: List[Dict[str, Any]] = []
        for idx, (mask, dtype, conf) in enumerate(extracted_defects):
            try:
                defect_json = self.quantify_defect(mask, gsd_cm_per_px, dtype, conf)
                defect_json["defect_id"] = f"DEFECT-{idx+1:03d}"
                results.append(defect_json)
            except Exception as exc:
                logger.error("Failed to quantify defect index %d: %s", idx, str(exc), exc_info=True)
                
        logger.info("Batch quantified %d defect instances.", len(results))
        return results
