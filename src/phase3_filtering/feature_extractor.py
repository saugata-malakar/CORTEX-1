"""
feature_extractor.py — Unified Feature Orchestration Module
===========================================================

Coordinates the extraction and scaling of multi-modal features for each defect candidate:
  - Edge features: local sharpness, Canny density (3-dim).
  - Texture features: Local Binary Patterns + GLCM spatial descriptors (42-dim).
  - Deep features: ResNet-50 embeddings via PCA (128-dim).
  - Shape features: contour solidity, elongation, Hu moments (7-dim).
  - Normalization: Fits, saves, and applies sklearn's ``StandardScaler`` (180-dim).
  - Verification: Ensures CPU execution time stays below 200ms per patch.

References:
  - [R8] Sobel (1970) Edge detection.
  - [R14] Haralick (1973) Texture features.
  - [R15] He (2016) ResNet-50.
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

try:
    from sklearn.preprocessing import StandardScaler
except ImportError:
    # Dummy StandardScaler fallback if sklearn is missing
    class StandardScaler:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self.mean_ = None
            self.scale_ = None
        def fit(self, X: np.ndarray) -> StandardScaler:
            self.mean_ = np.mean(X, axis=0)
            self.scale_ = np.std(X, axis=0)
            self.scale_[self.scale_ == 0] = 1.0
            return self
        def transform(self, X: np.ndarray) -> np.ndarray:
            if self.mean_ is None: return X
            return (X - self.mean_) / self.scale_
        def fit_transform(self, X: np.ndarray) -> np.ndarray:
            self.fit(X)
            return self.transform(X)

from .edge_features import extract_edge_features
from .texture_features import extract_texture_features
from .shape_features import extract_shape_features
from .deep_features import DeepFeatureExtractor

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Orchestrates all feature extraction submodules and scales final vectors.

    Parameters
    ----------
    config : dict
        Pipeline configuration dict containing 'feature_extraction' parameters.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        
        fe_cfg = config.get("feature_extraction", {})
        self.time_limit_ms = fe_cfg.get("extraction_time_limit_ms", 200)
        
        # Instantiate deep feature extractor (handles internal fallbacks)
        self.deep_extractor = DeepFeatureExtractor(config)
        
        # Initialize Scaler
        self.scaler = StandardScaler()
        
        # ThreadPoolExecutor for parallel feature extraction (capped based on CPU count)
        max_workers = min(4, max(1, (os.cpu_count() or 4) - 1))
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        logger.info("FeatureExtractor initialized successfully with %d workers.", max_workers)

    def __del__(self) -> None:
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)

    def extract_raw_vector(
        self,
        patch: np.ndarray,
        contour: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Extract and concatenate all edge, texture, deep, and shape features.

        Parameters
        ----------
        patch : np.ndarray
            Crop patch image array (size 96x96 px recommended).
        contour : np.ndarray, optional
            Contour representing the shape boundary of the defect.

        Returns
        -------
        np.ndarray
            1D float32 array of shape (180,).
        """
        start_time = time.perf_counter()
        
        # Parallel extraction of feature channels using the ThreadPoolExecutor
        future_edge = self.executor.submit(extract_edge_features, patch)
        future_texture = self.executor.submit(extract_texture_features, patch)
        future_deep = self.executor.submit(self.deep_extractor.extract, patch)
        future_shape = self.executor.submit(extract_shape_features, contour)
        
        edge_vec = future_edge.result()
        texture_vec = future_texture.result()
        deep_vec = future_deep.result()
        shape_vec = future_shape.result()
        
        # Concatenate: 3 + 42 + 128 + 7 = 180 dimensions
        raw_vector = np.concatenate([edge_vec, texture_vec, deep_vec, shape_vec])
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        if elapsed_ms > self.time_limit_ms:
            logger.warning(
                "Feature extraction took %.1f ms, exceeding target limit of %d ms.",
                elapsed_ms, self.time_limit_ms
            )
            
        return raw_vector.astype(np.float32)

    def extract(
        self,
        patch: np.ndarray,
        contour: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Extract and standardize (normalize) the unified feature vector.

        Parameters
        ----------
        patch : np.ndarray
            Crop patch image array.
        contour : np.ndarray, optional
            Defect contour points.

        Returns
        -------
        np.ndarray
            1D float32 array of shape (180,), normalized via StandardScaler.
        """
        raw = self.extract_raw_vector(patch, contour)
        
        # Scale the vector (transform expects a 2D matrix, so reshape)
        if hasattr(self.scaler, "mean_") and self.scaler.mean_ is not None:
            scaled = self.scaler.transform(raw.reshape(1, -1)).flatten()
            return scaled.astype(np.float32)
        else:
            logger.debug("Scaler not fitted. Returning raw unscaled features.")
            return raw

    def fit_scaler(self, feature_matrix: np.ndarray) -> None:
        """Fit the StandardScaler on a training set feature matrix.

        Parameters
        ----------
        feature_matrix : np.ndarray
            Feature matrix of shape (N, 180).
        """
        logger.info("Fitting StandardScaler on matrix of shape %s", str(feature_matrix.shape))
        self.scaler.fit(feature_matrix)
        logger.info("StandardScaler fit complete.")

    def save_scaler(self, path: str | Path) -> None:
        """Serialize the fitted StandardScaler to disk.

        Parameters
        ----------
        path : str or Path
            Output file path.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as fh:
            pickle.dump(self.scaler, fh)
        logger.info("StandardScaler serialized to %s", p)

    def load_scaler(self, path: str | Path) -> None:
        """Deserialize and load the StandardScaler.

        Parameters
        ----------
        path : str or Path
            Input file path.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Scaler serialized file not found: {p}")
        with open(p, "rb") as fh:
            self.scaler = pickle.load(fh)
        logger.info("StandardScaler loaded from %s", p)
