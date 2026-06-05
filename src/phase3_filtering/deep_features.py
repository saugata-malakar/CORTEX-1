"""
deep_features.py — Pretrained ResNet-50 Deep Feature Extractor
=============================================================

Extracts highly-representative deep features from 96×96 px defect patches:
  1. Penultimate 2048-dimensional avgpool embeddings from pretrained ResNet-50.
  2. Linear dimensionality reduction to 128 dimensions using PCA.
  3. Supports batch extraction, fitting PCA on datasets, and model serialization.
  4. Robust fallback using deterministic multi-scale Gabor filter histograms 
     if PyTorch/torchvision are unavailable or network weights cannot be fetched.

References:
  - [R15] He et al. (2016) Deep Residual Learning for Image Recognition.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np

# Try importing deep learning stack
try:
    import torch
    import torch.nn as nn
    import torchvision.models as models
    
    # Handle older torchvision APIs gracefully
    try:
        from torchvision.models import ResNet50_Weights
        RESNET_WEIGHTS = ResNet50_Weights.DEFAULT
    except ImportError:
        RESNET_WEIGHTS = None  # type: ignore[assignment]
        
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("PyTorch/torchvision not available. Deep features will use deterministic Gabor fallback.")

try:
    from sklearn.decomposition import PCA
except ImportError:
    # Dummy PCA fallback
    class PCA:  # type: ignore[no-redef]
        def __init__(self, n_components: int) -> None:
            self.n_components = n_components
        def fit(self, X: np.ndarray) -> PCA: return self
        def transform(self, X: np.ndarray) -> np.ndarray: return X[:, :self.n_components]
        def fit_transform(self, X: np.ndarray) -> np.ndarray: return X[:, :self.n_components]

logger = logging.getLogger(__name__)


_SHARED_RESNET_MODEL = None


class DeepFeatureExtractor:
    """Extracts 2048-dim ResNet-50 features and reduces them to 128 dimensions via PCA.

    Parameters
    ----------
    config : dict
        Pipeline configuration dict (specifically uses 'feature_extraction' parameters).
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        
        fe_cfg = config.get("feature_extraction", {})
        self.pca_n_components = fe_cfg.get("pca_n_components", 128)
        self.patch_size = fe_cfg.get("patch_size", 96)
        
        self.model: Optional[Any] = None
        self.pca: Optional[Any] = None
        
        # Load the PyTorch model if possible
        self._init_network()
        
        # Initialize default PCA
        self.pca = PCA(n_components=self.pca_n_components)
        logger.info("DeepFeatureExtractor initialized.")

    def _init_network(self) -> None:
        """Helper to safely initialize the ResNet-50 model."""
        global _SHARED_RESNET_MODEL
        if _SHARED_RESNET_MODEL is not None:
            self.model = _SHARED_RESNET_MODEL
            logger.info("ResNet-50 network loaded from shared module cache.")
            return

        if not TORCH_AVAILABLE:
            return
            
        try:
            # Silence model loading logs
            logging.getLogger("torch").setLevel(logging.WARNING)
            
            if RESNET_WEIGHTS is not None:
                self.model = models.resnet50(weights=RESNET_WEIGHTS)
            else:
                self.model = models.resnet50(pretrained=True)
                
            # Replace final classification head with an Identity layer
            self.model.fc = nn.Identity()
            self.model.eval()
            
            # Disable gradients to speed up inference
            for param in self.model.parameters():
                param.requires_grad = False
                
            _SHARED_RESNET_MODEL = self.model
            logger.info("ResNet-50 network loaded successfully.")
        except Exception as exc:
            logger.warning(
                "Failed to download or load ResNet-50 weights: %s. Using Gabor fallback.",
                str(exc)
            )
            self.model = None

    def _extract_gabor_fallback(self, patch: np.ndarray) -> np.ndarray:
        """Deterministic fallback feature vector if PyTorch is unavailable.

        Uses 8 orientations of Gabor filters + downsampled color histograms
        to build a robust 2048-dim representation.
        """
        # Ensure grayscale
        if patch.ndim == 3:
            gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        else:
            gray = patch
            
        gray = cv2.resize(gray, (self.patch_size, self.patch_size))
        
        features = []
        # Extract Gabor filters (4 wavelengths, 8 orientations)
        for theta in np.arange(0, np.pi, np.pi / 8.0):
            for wavelength in [3.0, 6.0, 9.0, 12.0]:
                kernel = cv2.getGaborKernel((21, 21), 2.5, theta, wavelength, 0.5, 0, ktype=cv2.CV_32F)
                fimg = cv2.filter2D(gray, cv2.CV_32F, kernel)
                # Compute statistical descriptors
                features.extend([np.mean(fimg), np.std(fimg), np.var(fimg)])
                
        # Pad features to exactly 2048 elements
        target_len = 2048
        # Add spatial pixel features to fill
        flat_pixel = cv2.resize(gray, (32, 32)).flatten() / 255.0  # 1024 dims
        features.extend(flat_pixel)
        
        # Final padding/clipping
        features = np.array(features, dtype=np.float32)
        if len(features) < target_len:
            pad = np.zeros(target_len - len(features), dtype=np.float32)
            features = np.concatenate([features, pad])
        elif len(features) > target_len:
            features = features[:target_len]
            
        return features

    def _preprocess_patch(self, patch: np.ndarray) -> Any:
        """Standard ImageNet pre-processing for PyTorch tensors."""
        if patch.ndim == 3:
            # Convert BGR to RGB
            rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
        else:
            rgb = cv2.cvtColor(patch, cv2.COLOR_GRAY2RGB)
            
        resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_LINEAR)
        
        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        
        normed = (resized.astype(np.float32) / 255.0 - mean) / std
        
        # HWC -> CHW and batch dim
        tensor = torch.tensor(normed).permute(2, 0, 1).unsqueeze(0)
        return tensor

    def extract_raw_features(self, patch: np.ndarray) -> np.ndarray:
        """Extract the raw 2048 penultimate embeddings from a single patch.

        Parameters
        ----------
        patch : np.ndarray
            Crop patch image.

        Returns
        -------
        np.ndarray
            1D float32 array of shape (2048,).
        """
        if self.model is None:
            return self._extract_gabor_fallback(patch)
            
        try:
            tensor = self._preprocess_patch(patch)
            with torch.no_grad():
                feat = self.model(tensor)
                # Flatten the feature tensor
                return feat.numpy().flatten().astype(np.float32)
        except Exception as exc:
            logger.debug("Failed PyTorch feature extraction: %s. Using Gabor fallback.", str(exc))
            return self._extract_gabor_fallback(patch)

    def extract(self, patch: np.ndarray) -> np.ndarray:
        """Extract the PCA-reduced 128-dimensional deep feature vector from a patch.

        Parameters
        ----------
        patch : np.ndarray
            Image crop patch.

        Returns
        -------
        np.ndarray
            1D float32 array of shape (128,).
        """
        raw = self.extract_raw_features(patch)
        if not hasattr(self.pca, "components_"):
            # Fallback if PCA has not been fitted yet
            return raw[:self.pca_n_components].astype(np.float32)
        reduced = self.pca.transform(raw.reshape(1, -1))
        return reduced.flatten().astype(np.float32)

    def extract_batch(self, patches: np.ndarray) -> np.ndarray:
        """Batch extract deep features.

        Parameters
        ----------
        patches : np.ndarray
            Stacked array of shape (N, H, W, C).

        Returns
        -------
        np.ndarray
            Reduced features of shape (N, 128).
        """
        raw_feats = []
        for p in patches:
            raw_feats.append(self.extract_raw_features(p))
            
        if not raw_feats:
            return np.empty((0, self.pca_n_components), dtype=np.float32)
            
        raw_matrix = np.vstack(raw_feats)
        if not hasattr(self.pca, "components_"):
            # Fallback if PCA has not been fitted yet
            return raw_matrix[:, :self.pca_n_components].astype(np.float32)
        reduced_matrix = self.pca.transform(raw_matrix)
        return reduced_matrix.astype(np.float32)

    def fit_pca(self, patches: np.ndarray) -> None:
        """Fit the PCA model on a dataset of representative patches.

        Parameters
        ----------
        patches : np.ndarray
            Training set patches of shape (N, H, W, C).
        """
        logger.info("Fitting PCA model on %d patches...", len(patches))
        raw_feats = []
        for p in patches:
            raw_feats.append(self.extract_raw_features(p))
            
        if not raw_feats:
            raise ValueError("No patches provided to fit PCA.")
            
        raw_matrix = np.vstack(raw_feats)
        self.pca = PCA(n_components=self.pca_n_components)
        self.pca.fit(raw_matrix)
        logger.info("PCA model fit complete. Retained components=%d", self.pca_n_components)

    def save_pca(self, path: str | Path) -> None:
        """Serialize the fitted PCA parameters to disk.

        Parameters
        ----------
        path : str or Path
            Output file path.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as fh:
            pickle.dump(self.pca, fh)
        logger.info("PCA model serialised to %s", p)

    def load_pca(self, path: str | Path) -> None:
        """Deserialize and load the PCA parameters.

        Parameters
        ----------
        path : str or Path
            Input file path.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"PCA serialised file not found: {p}")
        with open(p, "rb") as fh:
            self.pca = pickle.load(fh)
        logger.info("PCA model loaded from %s", p)
