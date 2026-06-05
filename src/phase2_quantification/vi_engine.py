"""
vi_engine.py — Vulnerability Index (VI) Computation Module
===========================================================

Implements structural health scoring of building facades:
  - Defect-level VI: wi × si × Ai
  - Facade-level VI: [Σ(wi × si × Ai) / Afacade] × 100
  - Grid-based partitioning (A1–D4) and zone-level aggregation
  - IS 13311 aligned severity mapping & recommended action timeline

References:
  - [R11] Xu et al. (2019) Building Facade Vulnerability Indexing and Risk Assessment.
  - IS 13311 (Part 1 & 2): 1992 Non-destructive testing of concrete — Methods of test.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)

MEMBER_CRITICALITY = {
    "column":          3.0,
    "beam":            2.0,
    "slab":            1.5,
    "wall_structural": 1.2,
    "wall_partition":  0.5,
    "unknown":         1.0,
}

CRACK_SUBTYPE_RISK = {
    "shear":             2.5,
    "corrosion_induced": 2.0,
    "settlement":        1.8,
    "flexural":          1.0,
    "shrinkage_crazing": 0.8,
    None:                1.0,
    "unknown":           1.0,
}

class VulnerabilityIndexEngine:
    """Computes composite health scores for building facades and grid zones.

    Parameters
    ----------
    config : dict
        Pipeline configuration dict (specifically uses 'vulnerability_index' parameter section).
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        
        # Load parameters with safe fallback defaults
        vi_cfg = config.get("vulnerability_index", {})
        
        self.defect_weights = vi_cfg.get("defect_weights", {
            "crack": 1.0,
            "spalling": 0.8,
            "corrosion": 0.6,
            "water_seepage": 0.5,
            "efflorescence": 0.3,
            "plaster_detachment": 0.7,
            "structural_displacement": 1.0,
            "stain": 0.1,
        })
        
        self.severity_multipliers = vi_cfg.get("severity_multipliers", {
            "hairline": 0.3,
            "fine": 0.5,
            "medium": 0.8,
            "wide": 1.0,
        })
        
        self.width_thresholds = vi_cfg.get("width_thresholds_mm", {
            "hairline_max": 0.2,
            "fine_max": 1.0,
            "medium_max": 5.0,
        })
        
        self.class_thresholds = vi_cfg.get("class_thresholds", {
            "minor_max": 20,
            "moderate_max": 40,
            "significant_max": 60,
            "severe_max": 80,
        })
        
        self.facade_grid_str = vi_cfg.get("facade_grid", "4x4")
        
        logger.info("VulnerabilityIndexEngine initialized.")

    def classify_severity(self, width_mm: float) -> str:
        """Classify crack severity based on width boundaries.

        Parameters
        ----------
        width_mm : float
            Crack width in millimeters.

        Returns
        -------
        str
            Severity class ('hairline', 'fine', 'medium', 'wide').
        """
        if width_mm < self.width_thresholds.get("hairline_max", 0.2):
            return "hairline"
        elif width_mm < self.width_thresholds.get("fine_max", 1.0):
            return "fine"
        elif width_mm < self.width_thresholds.get("medium_max", 5.0):
            return "medium"
        else:
            return "wide"

    def compute_defect_vi(self, defect: Dict[str, Any]) -> float:
        """Calculate the individual Vulnerability Index contribution of a single defect.

        Formula:
            VI_defect = wi × si × Ai × crack_type_risk × member_criticality × exposure_multiplier

        Parameters
        ----------
        defect : dict
            Quantified defect dict containing 'type', 'width_mm' (or 'severity_class'),
            'area_cm2', 'member_type', 'crack_type', and 'exposure_condition'.

        Returns
        -------
        float
            Individual defect VI contribution.
        """
        defect_type = defect.get("type", "crack")
        area_cm2 = defect.get("area_cm2", 0.0)
        
        # Get weight (wi)
        wi = self.defect_weights.get(defect_type, 0.5)
        
        # Get severity class and multiplier (si)
        severity_class = defect.get("severity_class")
        if not severity_class:
            width_mm = defect.get("width_mm", 0.0)
            severity_class = self.classify_severity(width_mm)
            
        si = self.severity_multipliers.get(severity_class, 0.5)
        
        # Determine crack type risk
        crack_type_risk = 1.0
        ctype = str(defect.get("crack_type") or defect.get("type") or "").lower()
        if "shear" in ctype:
            crack_type_risk = 2.5
        elif "corrosion" in ctype:
            crack_type_risk = 2.0
        elif "compression" in ctype:
            crack_type_risk = 3.0
            
        # Determine member criticality
        member_type = str(defect.get("member_type") or "slab").lower()
        if "column" in member_type:
            member_mult = 3.0
        elif "beam" in member_type:
            member_mult = 2.0
        elif "slab" in member_type:
            member_mult = 1.0
        elif "wall" in member_type:
            member_mult = 0.5
        else:
            member_mult = 1.0

        # Exposure condition multiplier
        exposure_cond = defect.get("exposure_condition") or self.config.get("vulnerability_index", {}).get("exposure_condition", "normal")
        exposure_mult = 1.0
        if str(exposure_cond).lower() in ("extreme", "coastal", "severe"):
            exposure_mult = 1.5
        
        # Individual VI
        base_vi = wi * si * area_cm2 * crack_type_risk * member_mult * exposure_mult

        member_type = defect.get("member_type", "unknown")
        crack_subtype = defect.get("crack_subtype", None)

        member_weight = MEMBER_CRITICALITY.get(member_type, 1.0)
        subtype_weight = CRACK_SUBTYPE_RISK.get(crack_subtype, 1.0)

        adjusted_vi = base_vi * member_weight * subtype_weight

        return float(adjusted_vi)

    def compute_facade_vi(self, defects: List[Dict[str, Any]], facade_area_cm2: float) -> float:
        """Calculate the composite Vulnerability Index for the entire facade.

        Formula:
            VI_facade = [Σ(wi × si × Ai × crack_type_risk × member_criticality × exposure_multiplier) / Afacade] × 100

        Parameters
        ----------
        defects : list of dict
            List of quantified defect dicts.
        facade_area_cm2 : float
            Total physical area of the facade in square centimeters.

        Returns
        -------
        float
            Facade Vulnerability Index score (0 to 100).
        """
        if facade_area_cm2 <= 0:
            logger.warning("Invalid facade area: %.2f. Defaulting to 0.", facade_area_cm2)
            return 0.0
            
        total_vi_sum = sum(self.compute_defect_vi(d) for d in defects)
        vi_score = (total_vi_sum / facade_area_cm2) * 100.0
        
        # Cap score to 100
        return float(min(vi_score, 100.0))

    def classify_vi(self, vi_score: float) -> str:
        """Map the Vulnerability Index score to an IS 13311 aligned condition class.

        Parameters
        ----------
        vi_score : float
            Vulnerability Index score (0 to 100).

        Returns
        -------
        str
            Condition class (Class I, II, III, IV, or V).
        """
        if vi_score <= self.class_thresholds.get("minor_max", 20):
            return "Class I (Minor)"
        elif vi_score <= self.class_thresholds.get("moderate_max", 40):
            return "Class II (Moderate)"
        elif vi_score <= self.class_thresholds.get("significant_max", 60):
            return "Class III (Significant)"
        elif vi_score <= self.class_thresholds.get("severe_max", 80):
            return "Class IV (Severe)"
        else:
            return "Class V (Critical)"

    def get_recommendations(self, vi_score_or_class: Any) -> Dict[str, str]:
        """Get structural repair recommendations and timeline aligned with IS 13935 / ACI 224R.

        Parameters
        ----------
        vi_score_or_class : Any
            Vulnerability score float or classified condition string.

        Returns
        -------
        dict
            Dict with 'action' and 'timeline' keys.
        """
        import re
        if isinstance(vi_score_or_class, (int, float)):
            score = float(vi_score_or_class)
        else:
            # Try to parse score from string or match class name
            score_match = re.search(r"(\d+\.?\d*)", str(vi_score_or_class))
            if score_match:
                score = float(score_match.group(1))
            else:
                c = str(vi_score_or_class).upper()
                if "CLASS I" in c:
                    score = 15.0
                elif "CLASS II" in c:
                    score = 35.0
                elif "CLASS III" in c:
                    score = 50.0
                elif "CLASS IV" in c:
                    score = 70.0
                else:
                    score = 90.0

        if score < 30.0:
            return {
                "action": "Monitor at next cycle",
                "timeline": "Next cycle",
            }
        elif score < 60.0:
            return {
                "action": "Detailed investigation",
                "timeline": "Within 90 days",
            }
        elif score < 80.0:
            return {
                "action": "Repair and remediation",
                "timeline": "Within 30 days",
            }
        else:
            return {
                "action": "Emergency site visit by structural engineer",
                "timeline": "Within 72 hours",
            }

    def aggregate_zones(
        self,
        mosaic_shape: Tuple[int, int],
        defects: List[Dict[str, Any]],
        facade_area_cm2: float,
    ) -> Dict[str, Dict[str, Any]]:
        """Assign defects to spatial grid cells (e.g. A1–D4) and compute per-zone VI.

        Parameters
        ----------
        mosaic_shape : tuple of int
            (Height, Width) of the stitched facade mosaic in pixels.
        defects : list of dict
            List of quantified defects (each containing 'centroid_px' and physical dimensions).
        facade_area_cm2 : float
            Total physical area of the facade in square centimeters.

        Returns
        -------
        dict
            Dictionary mapping zone IDs (e.g. 'A1') to their statistics:
            { 'zone_vi', 'defect_count', 'dominant_defect_type', 'defects', 'severity_class' }
        """
        h, w = mosaic_shape[:2]
        
        # Parse grid dimensions (e.g. "4x4")
        match = re.match(r"^(\d+)[xX](\d+)$", self.facade_grid_str)
        if match:
            rows = int(match.group(1))
            cols = int(match.group(2))
        else:
            rows, cols = 4, 4  # default to 4x4
            
        # Physical area of a single zone grid cell
        num_cells = rows * cols
        zone_area_cm2 = facade_area_cm2 / num_cells
        
        # Initialize grid map
        zones: Dict[str, Dict[str, Any]] = {}
        for r in range(rows):
            for c in range(cols):
                col_letter = chr(ord("A") + c)
                row_num = str(r + 1)
                zone_id = f"{col_letter}{row_num}"
                zones[zone_id] = {
                    "grid_id": zone_id,
                    "zone_area_cm2": round(zone_area_cm2, 2),
                    "defect_count": 0,
                    "defects": [],
                    "dominant_defect_type": None,
                    "zone_vi": 0.0,
                }
                
        # Assign defects to zones
        for d in defects:
            centroid = d.get("centroid_px", [w // 2, h // 2])
            cx, cy = centroid
            
            # Map pixels to grid cells (with clipping to prevent index overflows)
            col_idx = min(cols - 1, max(0, int(cx / (w / cols))))
            row_idx = min(rows - 1, max(0, int(cy / (h / rows))))
            
            col_letter = chr(ord("A") + col_idx)
            row_num = str(row_idx + 1)
            zone_id = f"{col_letter}{row_num}"
            
            # Compute defect VI contribution and attach it
            vi_contrib = self.compute_defect_vi(d)
            d["vi_contribution"] = round(vi_contrib, 3)
            
            zones[zone_id]["defects"].append(d)
            zones[zone_id]["defect_count"] += 1
            
        # Calculate statistics for each zone
        for zone_id, zone_data in zones.items():
            zone_defects = zone_data["defects"]
            if not zone_defects:
                continue
                
            # Compute zone VI
            vi_score = self.compute_facade_vi(zone_defects, zone_area_cm2)
            zone_data["zone_vi"] = round(vi_score, 3)
            
            # Find dominant defect type
            types = [d.get("type", "crack") for d in zone_defects]
            dominant_type = max(set(types), key=types.count)
            zone_data["dominant_defect_type"] = dominant_type
            
        return zones
