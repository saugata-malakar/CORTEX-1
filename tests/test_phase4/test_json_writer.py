"""
test_json_writer.py — Unit Tests for Hierarchical JSON Writer
============================================================

Verifies:
  - 4-level building metadata assembly.
  - Integration of defect and zone details.
  - JSON schema draft-07 contract validation (config/json_output_schema.json).
  - JSON serialization and file writing.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.phase4_reporting.json_writer import JSONWriter, create_defect_instance, create_zone, create_facade


def test_json_assembly_and_writing(tmp_path: Path) -> None:
    """Verify building object assembly, schema validation, and disk serialization."""
    # Find schema
    schema_path = Path(__file__).parents[2] / "config" / "json_output_schema.json"
    writer = JSONWriter(str(schema_path))
    
    # 1. Defect instance
    d = create_defect_instance(
        defect_id="DEFECT-001",
        defect_type="crack",
        length_cm=15.2,
        width_mm=1.2,
        area_cm2=18.4,
        centroid_px={"x": 120, "y": 240},
        centroid_gps={"latitude": 22.314, "longitude": 87.311},
        bbox_px={"x": 100, "y": 200, "width": 40, "height": 80},
        severity_class="medium",
        vi_contribution=4.5,
        confidence_score=0.92,
        is_false_positive=False,
        temporal_status="propagated",
        parent_defect_id="PARENT-001",
        delta_length_cm=2.1,
        delta_width_mm=0.2,
        delta_area_cm2=1.5,
        growth_rate_mm_per_month=0.2
    )
    
    # 2. Zone
    z = create_zone(
        grid_id="A1",
        zone_area_cm2=10000.0,
        zone_vi=4.5,
        defects=[d]
    )
    
    # 3. Facade
    f = create_facade(
        facade_id="FACADE-N",
        orientation="N",
        area_m2=150.0,
        vi_score=15.4,
        vi_class="minor",
        mosaic_path="data/mosaics/facade_n.png",
        zones=[z]
    )
    
    # 4. Building
    building_info = {
        "id": "BLDG-009",
        "name": "IIT KGP Civil Block",
        "address": "Campus Road, IIT Kharagpur",
        "gps_centroid": {"latitude": 22.314, "longitude": 87.311},
        "inspection_date": "2026-06-02",
        "cycle_number": 2,
        "module_version": "1.0.0",
        "temporal_comparison": {
            "comparison_cycle": 1,
            "delta_vi": 1.2,
            "new_defects_count": 3,
            "propagated_defects_count": 5
        }
    }
    
    building = writer.assemble_building(building_info, [f])
    wrapped = writer.wrap_with_metadata(building)
    
    # Check hierarchy
    assert wrapped["buildings"][0]["id"] == "BLDG-009"
    assert wrapped["buildings"][0]["facades"][0]["orientation"] == "N"
    assert wrapped["buildings"][0]["facades"][0]["zones"][0]["grid_id"] == "A1"
    assert wrapped["buildings"][0]["facades"][0]["zones"][0]["defects"][0]["defect_id"] == "DEFECT-001"
    
    # Validate against schema
    is_valid, errors = writer.validate(wrapped)
    assert is_valid, f"JSON validation failed: {errors}"
    
    # Write to file
    out_file = tmp_path / "output.json"
    writer.write(wrapped, str(out_file), validate_schema=True)
    assert out_file.exists()
    
    # Load and verify size
    with open(out_file, "r") as fh:
        loaded = json.load(fh)
    assert loaded["buildings"][0]["name"] == "IIT KGP Civil Block"
