"""
edge_features.py — Edge and Gradient Feature Extraction Module
==============================================================

Extracts classical edge-related feature vectors from image patches:
  1. Canny edge density: Fraction of edge pixels in the region.
  2. Laplacian variance: Indicator of local sharpness / texture variance.
  3. Sobel gradient magnitude mean: Average sharpness of local structures.

Total dimensionality: 3 dimensions.

References:
  - [R8] Sobel (1970) An Isotropic 3x3 Image Gradient Operator.
"""

from __future__ import annotations

import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def extract_edge_features(patch: np.ndarray) -> np.ndarray:
    """Extract a 3-dimensional edge and gradient feature vector from a patch.

    Parameters
    ----------
    patch : np.ndarray
        Image patch (RGB/BGR or grayscale).

    Returns
    -------
    np.ndarray
        A 1D float32 array of shape (3,). Contains:
        [canny_density, laplacian_variance, sobel_gradient_mean]
    """
    # 1. Convert to grayscale if necessary
    if patch.ndim == 3:
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    else:
        gray = patch
        
    h, w = gray.shape[:2]
    total_pixels = max(1.0, float(h * w))
    
    # 2. Canny Edge Density
    # Automatically compute low/high thresholds based on median intensity
    median_val = np.median(gray)
    lower = int(max(0, 0.66 * median_val))
    upper = int(min(255, 1.33 * median_val))
    
    edges = cv2.Canny(gray, lower, upper)
    canny_density = np.sum(edges > 0) / total_pixels
    
    # 3. Laplacian Variance
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    laplacian_variance = np.var(laplacian)
    
    # 4. Sobel Gradient Magnitude Mean
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(sobelx**2 + sobely**2)
    sobel_gradient_mean = np.mean(magnitude)
    
    # Pack features
    features = np.array([
        canny_density,
        laplacian_variance,
        sobel_gradient_mean,
    ], dtype=np.float32)
    
    return features
