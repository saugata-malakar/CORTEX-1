"""
test_e2e.py — End-to-End Integration Verification Test
======================================================
Verifies the unified execution of the Cortex Drone Defect Quantification Pipeline:
  - Phase 1-4 pipeline execution on raw flight frames.
  - JSON datastore generation containing warnings list and pipeline version schema.
  - SQLite persistent database storage insertion validation in defects.db.
  - PDF manual compilation output verification.
"""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path

from src.pipeline import CortexPipeline

def test_pipeline_e2e_integration(tmp_path: Path) -> None:
    """Run E2E pipeline and verify SQLite records, JSON schema, warnings, and PDF generation."""
    workspace = Path(__file__).parents[1].resolve()
    
    # Paths setup
    config_path = workspace / "config" / "pipeline_config.yaml"
    input_dir = workspace / "data" / "raw"
    output_dir = tmp_path / "reports"
    
    assert config_path.exists(), f"Configuration not found: {config_path}"
    assert input_dir.exists(), f"Raw test images folder not found: {input_dir}"
    
    # 1. Execute Pipeline E2E
    pipeline = CortexPipeline(str(config_path))
    pdf_report_path = pipeline.run(str(input_dir), str(output_dir))
    
    # 2. Check output files existence
    assert Path(pdf_report_path).exists()
    
    json_path = output_dir / "inspection_results.json"
    assert json_path.exists()
    
    facade_image = output_dir / "stitched_facade.png"
    assert facade_image.exists()
    
    # 3. Validate JSON data store structure
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert "schema_version" in data
    assert "pipeline_version" in data
    assert "pipeline_warnings" in data
    assert isinstance(data["pipeline_warnings"], list)
    
    building = data["buildings"][0]
    assert building["id"] == "BLDG-KHG-09"
    assert len(building["facades"]) > 0
    
    # 4. Validate SQLite Persistence writes
    db_path = workspace / "data" / "reports" / "defects.db"
    assert db_path.exists(), "SQLite database defects.db was not created."
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Query inspection record
    inspection_id = f"{building['id']}_{building['inspection_date']}_C{building['cycle_number']}"
    cursor = conn.execute("SELECT * FROM inspections WHERE id = ?", (inspection_id,))
    inspection_row = cursor.fetchone()
    assert inspection_row is not None
    assert abs(inspection_row["vi_score"] - building["facades"][0]["vi_score"]) < 0.05
    
    # Decode warnings from db row
    db_warnings = json.loads(inspection_row["warnings"])
    assert isinstance(db_warnings, list)
    
    # Query defects list
    cursor = conn.execute("SELECT * FROM defects WHERE inspection_id = ?", (inspection_row["id"],))
    defect_rows = cursor.fetchall()
    
    # Number of defects in SQLite must equal defects in JSON
    json_defect_count = sum(len(z["defects"]) for z in building["facades"][0]["zones"])
    assert len(defect_rows) == json_defect_count
    
    if len(defect_rows) > 0:
        d = defect_rows[0]
        assert "growth_acceleration" in d.keys()
        
    conn.close()
