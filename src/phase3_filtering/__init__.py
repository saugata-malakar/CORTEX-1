"""
Phase 3 — Feature Extraction & False-Positive Filtering
======================================================

Provides multi-modal feature engineering (edge, texture, deep ResNet-50, and contour shape descriptors)
and an XGBoost classification layer to filter out facade false positives with a precision-first target.

Exposes:
  - ``PatchExtractor``: Handles border-aware square image crops with zero padding.
  - ``FeatureExtractor``: Orchestrates and scales unified 180-dim feature vectors.
  - ``PatchAugmenter``: Applies image-level data augmentations (flips, rotations, noise).
  - ``FalsePositiveFilter``: Machine learning model (XGBoost / RandomForest) classifier.
"""

from __future__ import annotations

from .patch_extractor import PatchExtractor
from .feature_extractor import FeatureExtractor
from .augment_patches import PatchAugmenter
from .feature_filter import FalsePositiveFilter

__all__ = [
    "PatchExtractor",
    "FeatureExtractor",
    "PatchAugmenter",
    "FalsePositiveFilter",
]
