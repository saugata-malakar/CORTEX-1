"""
Cortex Structural Defect Pipeline
==================================

AI-Based Drone Image Processing & Structural Defect Quantification Pipeline.

This package orchestrates a four-phase pipeline:
    1. Phase 1 — Pre-processing (quality gate, enhancement, stitching, GSD)
    2. Phase 2 — Quantification (crack metrics, spalling area, V-Index)
    3. Phase 3 — Filtering (XGBoost false-positive reduction, SHAP)
    4. Phase 4 — Reporting (PDF generation, dashboards)

Author : Saugata Malakar, IIT Kharagpur
License: Confidential — Cortex Construction Solutions Pvt. Ltd.
"""

__version__ = "0.1.0"
__author__ = "Saugata Malakar"

# Phase-level imports (uncomment as modules are implemented)
# from .phase1_preprocessing import PreprocessingPipeline
# from .phase2_quantification import QuantificationEngine
# from .phase3_filtering import FalsePositiveFilter
# from .phase4_reporting import ReportGenerator
