"""
Phase 4 — Analytical Output & Reporting Module
=============================================

Exposes:
  - ``JSONWriter``: Compiles pipeline metrics into a schema-validated hierarchical JSON data store.
  - ``PDFReportGenerator``: Generates client-ready inspection manual from the JSON data store.
  - ``classify_vi_score``: Aligns vulnerability scores with IS 13311 building safety condition bands.
"""

from __future__ import annotations

from .json_writer import JSONWriter
from .report_generator import PDFReportGenerator
from .severity_classifier import classify_vi_score

__all__ = [
    "JSONWriter",
    "PDFReportGenerator",
    "classify_vi_score",
]
