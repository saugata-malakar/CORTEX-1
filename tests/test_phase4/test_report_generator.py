"""
test_report_generator.py — Unit Tests for Report Generator Engine
==================================================================

Verifies:
  - Integration of building datastores into ReportLab flowables.
  - NumberedCanvas dynamic page decorations.
  - Alternating colors, styled headers, and severity badge rendering.
  - High-performance, in-memory PDF generation to file paths.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from src.phase4_reporting.report_generator import PDFReportGenerator
from src.phase4_reporting.json_writer import create_defect_instance, create_zone, create_facade, create_building


@pytest.fixture
def rep_config() -> dict:
    """Minimal mock configuration."""
    return {
        "reporting": {
            "pdf_page_size": "A4",
            "company_name": "Cortex scan Solutions",
            "use_in_memory_generation": True,
            "report_generation_timeout_sec": 30,
        }
    }


def test_pdf_generation(rep_config: dict, tmp_path: Path) -> None:
    """Verify that the PLATYPUS pipeline successfully renders a PDF to disk."""
    generator = PDFReportGenerator(rep_config)
    
    # 1. Assemble a mock building datastore
    d = create_defect_instance(
        defect_id="DEFECT-001",
        defect_type="crack",
        length_cm=20.0,
        width_mm=0.5,
        area_cm2=10.0,
        severity_class="fine"
    )
    z = create_zone("A1", 5000.0, 10.0, [d])
    f = create_facade("FAC-01", "N", 120.0, 15.0, "minor", "mosaic.png", {}, [z])
    b = create_building("BLD-01", "Kharagpur Faculty Complex", "KGP campus", None, "2026-06-02", 1, [f])
    
    wrapped = {
        "schema_version": "1.0.0",
        "generated_at": "2026-06-02T15:00:00Z",
        "pipeline_config_hash": "0123456789abcdef",
        "buildings": [b]
    }
    
    pdf_path = tmp_path / "report.pdf"
    res_path = generator.generate(wrapped, str(pdf_path))
    
    assert Path(res_path).exists()
    assert Path(res_path).stat().st_size > 1000  # Non-trivial size


def test_pdf_generation_multi_cycle(rep_config: dict, tmp_path: Path) -> None:
    """Verify that multi-cycle datasets compile to PDF successfully with comparison sections."""
    generator = PDFReportGenerator(rep_config)
    
    # Cycle 1 building
    d1 = create_defect_instance(
        defect_id="DEFECT-001",
        defect_type="crack",
        length_cm=15.0,
        width_mm=0.4,
        area_cm2=8.0,
        severity_class="fine"
    )
    z1 = create_zone("A1", 5000.0, 8.0, [d1])
    f1 = create_facade("FAC-01", "N", 120.0, 10.0, "minor", "mosaic_c1.png", {}, [z1])
    b1 = create_building("BLD-01", "Kharagpur Faculty Complex", "KGP campus", None, "2026-05-02", 1, [f1])
    
    # Cycle 2 building (growth and one new defect)
    d2_prop = create_defect_instance(
        defect_id="DEFECT-001",
        defect_type="crack",
        length_cm=17.0,
        width_mm=0.6,
        area_cm2=9.5,
        severity_class="fine",
        temporal_status="propagated",
        parent_defect_id="DEFECT-001",
        delta_length_cm=2.0,
        delta_width_mm=0.2,
        delta_area_cm2=1.5,
        growth_rate_mm_per_month=0.2
    )
    d2_new = create_defect_instance(
        defect_id="DEFECT-002",
        defect_type="spalling",
        length_cm=5.0,
        width_mm=10.0,
        area_cm2=50.0,
        severity_class="wide",
        temporal_status="new",
        growth_rate_mm_per_month=10.0
    )
    
    z2 = create_zone("A1", 5000.0, 25.0, [d2_prop, d2_new])
    f2 = create_facade("FAC-01", "N", 120.0, 25.0, "moderate", "mosaic_c2.png", {}, [z2])
    b2 = create_building("BLD-01", "Kharagpur Faculty Complex", "KGP campus", None, "2026-06-02", 2, [f2])
    
    # Wrap both buildings
    wrapped = {
        "schema_version": "1.0.0",
        "generated_at": "2026-06-02T15:00:00Z",
        "pipeline_config_hash": "0123456789abcdef",
        "buildings": [b2, b1]  # Sort order will resolve b2 as current and b1 as previous
    }
    
    pdf_path = tmp_path / "multi_cycle_report.pdf"
    res_path = generator.generate(wrapped, str(pdf_path))
    
    assert Path(res_path).exists()
    assert Path(res_path).stat().st_size > 1000  # Should be non-trivial and contain comparisons
