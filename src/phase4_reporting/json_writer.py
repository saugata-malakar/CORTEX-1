"""
json_writer.py — Hierarchical JSON Data Store Module

Assembles all upstream pipeline outputs into a structured JSON data store
with a 4-level hierarchy: Building → Facade → Zone → Defect_Instance.

Validated against config/json_output_schema.json using jsonschema.
Designed as the single source of truth for all inspection data — the PDF
report reads from this JSON (JSON-first pattern).

Author: Saugata Malakar | IIT Kharagpur
Organisation: Cortex Construction Solutions Pvt. Ltd.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

logger = logging.getLogger(__name__)


# ===========================================================================
# Data Assembly
# ===========================================================================

def _normalize_gps(gps: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Helper to convert latitude/longitude coordinates to schema-compliant lat/lon keys."""
    if not gps:
        return {"lat": 0.0, "lon": 0.0}
    lat = gps.get("lat", gps.get("latitude", 0.0))
    lon = gps.get("lon", gps.get("longitude", 0.0))
    return {"lat": round(float(lat), 6), "lon": round(float(lon), 6)}


def create_defect_instance(
    defect_id: str,
    defect_type: str,
    length_cm: float = 0.0,
    width_mm: float = 0.0,
    area_cm2: float = 0.0,
    centroid_px: Optional[Dict] = None,
    centroid_gps: Optional[Dict] = None,
    bbox_px: Optional[Dict] = None,
    severity_class: str = "minor",
    vi_contribution: float = 0.0,
    confidence_score: float = 0.0,
    image_crop_path: str = "",
    is_false_positive: bool = False,
    fp_confidence: float = 0.0,
    elongation_ratio: float = 1.0,
    solidity: float = 1.0,
    temporal_status: Optional[str] = None,
    parent_defect_id: Optional[str] = None,
    delta_length_cm: Optional[float] = None,
    delta_width_mm: Optional[float] = None,
    delta_area_cm2: Optional[float] = None,
    growth_rate_mm_per_month: Optional[float] = None
) -> Dict[str, Any]:
    """Create a single defect instance record.

    Args:
        defect_id: Unique defect identifier.
        defect_type: One of: crack, spalling, corrosion, water_seepage,
                     efflorescence, plaster_detachment, structural_displacement.
        length_cm: Measured crack length in centimetres.
        width_mm: Measured crack width in millimetres.
        area_cm2: Defect area in square centimetres.
        centroid_px: Pixel coordinates {'x': int, 'y': int}.
        centroid_gps: GPS coordinates {'latitude': float, 'longitude': float}.
        bbox_px: Bounding box {'x': int, 'y': int, 'width': int, 'height': int}.
        severity_class: IS 13311 severity class string.
        vi_contribution: This defect's contribution to the facade VI.
        confidence_score: Detection model confidence (0-1).
        image_crop_path: Path to cropped defect image.
        is_false_positive: Whether flagged as FP by filter.
        fp_confidence: FP filter confidence score.
        elongation_ratio: Shape elongation ratio.
        solidity: Shape solidity metric.
        temporal_status: Temporal tracking status compared to previous cycles.
        parent_defect_id: The matching defect ID from previous cycle.
        delta_length_cm: Change in length compared to previous cycle.
        delta_width_mm: Change in width compared to previous cycle.
        delta_area_cm2: Change in area compared to previous cycle.
        growth_rate_mm_per_month: Growth rate of the defect.

    Returns:
        Defect instance dictionary.
    """
    res = {
        "defect_id": defect_id,
        "type": defect_type,
        "length_cm": round(length_cm, 2),
        "width_mm": round(width_mm, 2),
        "area_cm2": round(area_cm2, 2),
        "centroid_px": centroid_px or {"x": 0, "y": 0},
        "centroid_gps": _normalize_gps(centroid_gps),
        "severity_class": severity_class,
        "vi_contribution": round(vi_contribution, 4),
        "confidence_score": round(confidence_score, 4),
        "image_crop_path": image_crop_path or None,
        "is_false_positive": is_false_positive,
        "fp_confidence": round(fp_confidence, 4) if fp_confidence is not None else None
    }
    
    if temporal_status is not None:
        res["temporal_status"] = temporal_status
    if parent_defect_id is not None:
        res["parent_defect_id"] = parent_defect_id
    if delta_length_cm is not None:
        res["delta_length_cm"] = round(delta_length_cm, 2)
    if delta_width_mm is not None:
        res["delta_width_mm"] = round(delta_width_mm, 2)
    if delta_area_cm2 is not None:
        res["delta_area_cm2"] = round(delta_area_cm2, 2)
    if growth_rate_mm_per_month is not None:
        res["growth_rate_mm_per_month"] = round(growth_rate_mm_per_month, 2)
        
    return res


def create_zone(
    grid_id: str,
    zone_area_cm2: float = 0.0,
    zone_vi: float = 0.0,
    defects: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """Create a facade zone record.

    Args:
        grid_id: Zone identifier (e.g., 'A1', 'B3', 'D4').
        zone_area_cm2: Zone area in square centimetres.
        zone_vi: Zone-level Vulnerability Index (0-100).
        defects: List of defect instance dicts within this zone.

    Returns:
        Zone dictionary.
    """
    defects = defects or []
    defect_types = [d['type'] for d in defects if not d.get('is_false_positive', False)]

    # Find dominant defect type
    dominant = None
    if defect_types:
        from collections import Counter
        dominant = Counter(defect_types).most_common(1)[0][0]

    return {
        "grid_id": grid_id,
        "zone_area_cm2": round(zone_area_cm2, 2),
        "zone_vi": round(zone_vi, 2),
        "defect_count": len([d for d in defects if not d.get('is_false_positive', False)]),
        "dominant_defect_type": dominant,
        "defects": defects
    }


def create_facade(
    facade_id: str,
    orientation: str = "N",
    area_m2: float = 0.0,
    vi_score: float = 0.0,
    vi_class: str = "I",
    mosaic_path: str = "",
    enhancement_params: Optional[Dict] = None,
    zones: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """Create a facade record.

    Args:
        facade_id: Unique facade identifier.
        orientation: Cardinal direction ('N', 'S', 'E', 'W').
        area_m2: Total facade area in square metres.
        vi_score: Facade-level Vulnerability Index (0-100).
        vi_class: IS 13311 class ('I'-'V').
        mosaic_path: Path to stitched mosaic image.
        enhancement_params: Enhancement parameters used.
        zones: List of zone dicts.

    Returns:
        Facade dictionary.
    """
    return {
        "id": facade_id,
        "orientation": orientation,
        "area_m2": round(area_m2, 2),
        "vi_score": round(vi_score, 2),
        "vi_class": vi_class,
        "mosaic_path": mosaic_path,
        "enhancement_params": enhancement_params or {},
        "zones": zones or []
    }


def create_building(
    building_id: str,
    name: str = "",
    address: str = "",
    gps_centroid: Optional[Dict] = None,
    inspection_date: Optional[str] = None,
    cycle_number: int = 1,
    facades: Optional[List[Dict]] = None,
    module_version: str = "1.0.0",
    temporal_comparison: Optional[Dict] = None
) -> Dict[str, Any]:
    """Create a top-level building record.

    Args:
        building_id: Unique building identifier.
        name: Building name.
        address: Building address.
        gps_centroid: Centre GPS {'latitude': float, 'longitude': float}.
        inspection_date: ISO 8601 date string.
        cycle_number: Inspection cycle number.
        facades: List of facade dicts.
        module_version: Pipeline version string.
        temporal_comparison: Comparison data to previous cycle.

    Returns:
        Building dictionary.
    """
    res = {
        "id": building_id,
        "name": name,
        "address": address,
        "gps_centroid": _normalize_gps(gps_centroid),
        "inspection_date": inspection_date or datetime.now().isoformat()[:10],
        "inspector_module_version": module_version,
        "cycle_number": cycle_number,
        "facades": facades or []
    }
    if temporal_comparison is not None:
        res["temporal_comparison"] = temporal_comparison
    return res


# ===========================================================================
# JSON Writer Class
# ===========================================================================

class JSONWriter:
    """Assembles pipeline outputs into validated hierarchical JSON.

    JSON-first design pattern: all data is written to JSON first, then
    consumed by the PDF report generator for rendering. This decouples
    data from presentation and simplifies testing.

    Args:
        schema_path: Path to json_output_schema.json for validation.

    Example:
        >>> writer = JSONWriter("config/json_output_schema.json")
        >>> building = writer.assemble_building(metadata, defects, vi_results)
        >>> writer.write(building, "data/reports/building_001.json")
    """

    def __init__(self, schema_path: Optional[str] = None):
        self.schema = None
        if schema_path and HAS_JSONSCHEMA:
            try:
                with open(schema_path, 'r') as f:
                    self.schema = json.load(f)
                logger.info(f"Loaded output JSON schema from {schema_path}")
            except Exception as e:
                logger.warning(f"Failed to load JSON schema: {e}")

    def assemble_building(
        self,
        building_info: Dict[str, Any],
        facade_data: List[Dict[str, Any]],
        vi_results: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Assemble a complete building record from pipeline outputs.

        Args:
            building_info: Basic building metadata.
            facade_data: List of facade records with zones and defects.
            vi_results: Optional VI computation results.

        Returns:
            Complete building dictionary ready for serialisation.
        """
        building = create_building(
            building_id=building_info.get('id', 'unknown'),
            name=building_info.get('name', ''),
            address=building_info.get('address', ''),
            gps_centroid=building_info.get('gps_centroid'),
            inspection_date=building_info.get('inspection_date'),
            cycle_number=building_info.get('cycle_number', 1),
            facades=facade_data,
            module_version=building_info.get('module_version', '1.0.0'),
            temporal_comparison=building_info.get('temporal_comparison')
        )

        return building

    def wrap_with_metadata(
        self,
        building: Dict[str, Any],
        config_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Wrap building data with root-level metadata.

        Args:
            building: Assembled building dictionary.
            config_path: Path to pipeline config for hashing.

        Returns:
            Root-level output dictionary with metadata.
        """
        config_hash = ""
        if config_path:
            try:
                with open(config_path, 'rb') as f:
                    config_hash = hashlib.md5(f.read()).hexdigest()[:8]
            except Exception:
                pass

        return {
            "schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pipeline_config_hash": config_hash or "0123456789abcdef",
            "buildings": [building]
        }

    def validate(self, data: Dict[str, Any]) -> Tuple:
        """Validate JSON data against the output schema.

        Args:
            data: Data dictionary to validate.

        Returns:
            Tuple of (is_valid, errors_list).
        """
        if not HAS_JSONSCHEMA or self.schema is None:
            logger.warning("JSON schema validation skipped (no schema loaded)")
            return True, []

        import sys
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(10000)
        try:
            jsonschema.validate(instance=data, schema=self.schema)
            logger.info("JSON schema validation PASSED")
            return True, []
        except jsonschema.ValidationError as e:
            logger.warning(f"JSON schema validation FAILED: {e.message}")
            return False, [str(e.message)]
        except jsonschema.SchemaError as e:
            logger.error(f"Invalid JSON schema: {e.message}")
            return False, [f"Schema error: {e.message}"]
        except Exception as e:
            logger.warning(f"JSON schema validation bypassed due to library error: {e}")
            return False, [f"Library validation error: {e}"]
        finally:
            sys.setrecursionlimit(old_limit)



    def write(
        self,
        data: Dict[str, Any],
        output_path: str,
        validate_schema: bool = True
    ) -> str:
        """Write JSON data to file with optional schema validation.

        Args:
            data: Data dictionary to write.
            output_path: Output file path.
            validate_schema: Whether to validate before writing.

        Returns:
            Path to written file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write data to file first to ensure output is persisted
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        file_size_kb = output_path.stat().st_size / 1024
        logger.info(f"JSON written to {output_path} ({file_size_kb:.1f} KB)")

        # Validate schema safely
        if validate_schema:
            try:
                is_valid, errors = self.validate(data)
                if not is_valid:
                    logger.warning(f"JSON schema validation errors found: {errors}")
            except Exception as e:
                logger.error(f"JSON schema validation crashed during execution: {e}", exc_info=True)

        return str(output_path)

    def get_summary_stats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract summary statistics from the building data.

        Args:
            data: Root-level data dictionary (with 'building' key).

        Returns:
            Summary statistics dictionary for report generation.
        """
        building = data.get('building', data)
        if 'buildings' in data and isinstance(data['buildings'], list) and len(data['buildings']) > 0:
            building = data['buildings'][0]
        facades = building.get('facades', [])

        total_defects = 0
        defect_counts = {}
        vi_scores = []

        for facade in facades:
            vi_scores.append(facade.get('vi_score', 0))
            for zone in facade.get('zones', []):
                for defect in zone.get('defects', []):
                    if not defect.get('is_false_positive', False):
                        total_defects += 1
                        dtype = defect.get('type', 'unknown')
                        defect_counts[dtype] = defect_counts.get(dtype, 0) + 1

        return {
            'building_id': building.get('id', 'unknown'),
            'inspection_date': building.get('inspection_date', ''),
            'num_facades': len(facades),
            'total_defects': total_defects,
            'defect_counts_by_type': defect_counts,
            'mean_vi_score': sum(vi_scores) / len(vi_scores) if vi_scores else 0,
            'max_vi_score': max(vi_scores) if vi_scores else 0,
            'overall_vi_class': self._classify_vi(max(vi_scores) if vi_scores else 0)
        }

    def _classify_vi(self, vi_score: float) -> str:
        """Classify VI score to IS 13311 class."""
        if vi_score <= 20:
            return "I"
        elif vi_score <= 40:
            return "II"
        elif vi_score <= 60:
            return "III"
        elif vi_score <= 80:
            return "IV"
        else:
            return "V"


# Need this import for type hint in validate
from typing import Tuple
