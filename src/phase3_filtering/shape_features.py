"""
shape_features.py — Geometric Shape Feature Extraction Module
=============================================================

Extracts 7 classical shape descriptors from defect contours:
  1. Elongation ratio: Major axis length / minor axis length from minAreaRect.
  2. Solidity: Ratio of contour area to its convex hull area.
  3. Circularity: Ratio of contour area to its perimeter squared (normalized).
  4. Hu moments (1-4): Standard translation, scale, and rotation invariant moments
     (log-transformed to stabilize scales).

Total dimensionality: 7 dimensions.

References:
  - Hu (1962) Visual Pattern Recognition by Moment Invariants.
"""

from __future__ import annotations

import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def extract_shape_features(contour: np.ndarray | None) -> np.ndarray:
    """Extract a 7-dimensional geometric shape feature vector from a contour.

    Handles empty/degenerate contours gracefully by returning safe defaults.

    Parameters
    ----------
    contour : np.ndarray, optional
        OpenCV contour array of shape (N, 1, 2) or None.

    Returns
    -------
    np.ndarray
        1D float32 array of shape (7,). Contains:
        [elongation, solidity, circularity, hu1, hu2, hu3, hu4]
    """
    # Safe defaults
    elongation = 1.0
    solidity = 1.0
    circularity = 1.0
    hu_moments = np.zeros(4, dtype=np.float32)
    
    if contour is not None and len(contour) >= 3:
        try:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, closed=True)
            
            # 1. Elongation
            rect = cv2.minAreaRect(contour)
            (cx, cy), (w, h), angle = rect
            major = max(w, h)
            minor = min(w, h)
            elongation = float(major / minor) if minor > 0 else 1.0
            
            # 2. Solidity
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = float(area / hull_area) if hull_area > 0 else 1.0
            
            # 3. Circularity
            if perimeter > 0:
                circularity = float((4.0 * np.pi * area) / (perimeter ** 2))
                # Clip to [0, 1] as mathematical maximum is 1.0 (circle)
                circularity = min(1.0, max(0.0, circularity))
            else:
                circularity = 0.0
                
            # 4. Hu Moments
            moments = cv2.moments(contour)
            raw_hu = cv2.HuMoments(moments).flatten()
            
            # Log transform the first 4 moments to avoid extreme scales
            # Formula: sign(hu) * log10(abs(hu))
            for idx in range(4):
                val = raw_hu[idx]
                if abs(val) > 0:
                    hu_moments[idx] = float(-np.sign(val) * np.log10(abs(val)))
                else:
                    hu_moments[idx] = 0.0
                    
        except Exception as exc:
            logger.debug("Failed shape extraction from contour: %s. Using defaults.", str(exc))
            
    features = np.array([
        elongation,
        solidity,
        circularity,
        hu_moments[0],
        hu_moments[1],
        hu_moments[2],
        hu_moments[3],
    ], dtype=np.float32)
    
    return features
