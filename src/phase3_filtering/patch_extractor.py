"""
patch_extractor.py — Multiscale Patch Extraction Module
======================================================

Crops localized image patches (default 96×96 px) around defect centroids.
Implements robust zero-padding for defects located near or on image borders.
Supports batch patch extraction for high-throughput processing.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class PatchExtractor:
    """Extracts localized image patches around coordinates with automatic padding.

    Parameters
    ----------
    config : dict
        Pipeline configuration dict (specifically uses 'feature_extraction' parameters).
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        fe_cfg = config.get("feature_extraction", {})
        self.patch_size = fe_cfg.get("patch_size", 96)
        logger.info("PatchExtractor initialized with patch_size=%d", self.patch_size)

    def extract_patch(
        self,
        image: np.ndarray,
        centroid: Tuple[int, int],
        size: int | None = None,
    ) -> np.ndarray:
        """Crop a square patch of size *size* around a centroid with zero-padding.

        Parameters
        ----------
        image : np.ndarray
            Source image array (BGR or grayscale).
        centroid : tuple of int
            Centroid coordinates as (x, y).
        size : int, optional
            Size of the square patch. Defaults to config 'patch_size' (96).

        Returns
        -------
        np.ndarray
            Square patch of shape (size, size, C) or (size, size).
        """
        if size is None:
            size = self.patch_size
            
        cx, cy = int(centroid[0]), int(centroid[1])
        half = size // 2
        
        # Calculate boundaries relative to source image
        x1 = cx - half
        y1 = cy - half
        x2 = x1 + size
        y2 = y1 + size
        
        h, w = image.shape[:2]
        
        # Allocate output patch
        if image.ndim == 3:
            patch = np.zeros((size, size, image.shape[2]), dtype=image.dtype)
        else:
            patch = np.zeros((size, size), dtype=image.dtype)
            
        # Target coordinate bounds (inside the new patch)
        px1 = max(0, -x1)
        py1 = max(0, -y1)
        px2 = size - max(0, x2 - w)
        py2 = size - max(0, y2 - h)
        
        # Source coordinate bounds (inside the source image)
        ix1 = max(0, x1)
        iy1 = max(0, y1)
        ix2 = min(w, x2)
        iy2 = min(h, y2)
        
        # Perform crop and copy into padded canvas
        if (iy2 > iy1) and (ix2 > ix1):
            patch[py1:py2, px1:px2] = image[iy1:iy2, ix1:ix2]
            
        return patch

    def extract_patches_batch(
        self,
        image: np.ndarray,
        centroids: List[Tuple[int, int]],
        size: int | None = None,
    ) -> np.ndarray:
        """Batch extract patches for a list of centroids.

        Parameters
        ----------
        image : np.ndarray
            Source image.
        centroids : list of tuple
            List of (x, y) centroids.
        size : int, optional
            Output square patch dimension.

        Returns
        -------
        np.ndarray
            Stacked numpy array of shape (N, size, size, C) or (N, size, size).
        """
        if size is None:
            size = self.patch_size
            
        patches = []
        for c in centroids:
            p = self.extract_patch(image, c, size)
            patches.append(p)
            
        if not patches:
            # Return empty array with correct shape
            c_dim = image.shape[2] if image.ndim == 3 else 1
            shape = (0, size, size, c_dim) if image.ndim == 3 else (0, size, size)
            return np.empty(shape, dtype=image.dtype)
            
        return np.stack(patches, axis=0)
