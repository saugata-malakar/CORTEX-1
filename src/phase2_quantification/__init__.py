"""
Phase 2 — Defect Quantification Engine
=====================================

Provides core modules for physical measurement, black-box API wrapping, IS 13311-aligned health
scoring, and multitemporal change detection.

Exposes:
  - ``CortexAdapter``: Standard wrapper for black-box detection API with mock capability.
  - ``DefectQuantifier``: Computes length, width, and area of defects.
  - ``VulnerabilityIndexEngine``: Aligns physical defect metrics with building condition scores.
  - ``TemporalTracker``: Compares multi-cycle drone facade surveys.
"""

from __future__ import annotations

from .cortex_adapter import CortexAdapter, MockCortexDetector
from .quantifier import DefectQuantifier
from .vi_engine import VulnerabilityIndexEngine
from .temporal_tracker import TemporalTracker

__all__ = [
    "CortexAdapter",
    "MockCortexDetector",
    "DefectQuantifier",
    "VulnerabilityIndexEngine",
    "TemporalTracker",
]
