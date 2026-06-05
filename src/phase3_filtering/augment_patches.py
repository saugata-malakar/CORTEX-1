"""
augment_patches.py — Image Patch Augmentation Module
====================================================

Implements a fast, OpenCV-based data augmentation pipeline for training patches:
  - Horizontal and vertical flips.
  - Random affine rotation (±15° with reflection borders).
  - Brightness jittering (±20% scaling).
  - Additive Gaussian noise (σ variable between 5 and 15).
  - Dataset upscaling: Synthesizes patches to achieve a target size (e.g., 600 samples).
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class PatchAugmenter:
    """Applies random OpenCV transformations to augment training datasets.

    Parameters
    ----------
    config : dict
        Pipeline configuration dict containing 'false_positive_filter.augmentation' parameters.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        
        # Load augmentation parameters
        aug_cfg = config.get("false_positive_filter", {}).get("augmentation", {})
        self.flip_h = aug_cfg.get("flip_horizontal", True)
        self.flip_v = aug_cfg.get("flip_vertical", True)
        self.rot_range = aug_cfg.get("rotation_range", 15)
        self.brightness_jitter = aug_cfg.get("brightness_jitter", 0.20)
        self.noise_sigma_range = aug_cfg.get("noise_sigma_range", [5, 15])
        
        logger.info("PatchAugmenter initialized.")

    def flip(self, patch: np.ndarray, flip_code: int) -> np.ndarray:
        """Apply horizontal (1) or vertical (0) flip."""
        return cv2.flip(patch, flip_code)

    def rotate(self, patch: np.ndarray, angle: float) -> np.ndarray:
        """Rotate patch by an angle using reflection boundaries to prevent black borders."""
        h, w = patch.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(patch, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def jitter_brightness(self, patch: np.ndarray, factor: float) -> np.ndarray:
        """Scale pixel intensities to adjust brightness."""
        return np.clip(patch.astype(np.float32) * factor, 0, 255).astype(patch.dtype)

    def add_gaussian_noise(self, patch: np.ndarray, sigma: float) -> np.ndarray:
        """Add Gaussian pixel noise."""
        noise = np.random.normal(0, sigma, patch.shape).astype(np.float32)
        return np.clip(patch.astype(np.float32) + noise, 0, 255).astype(patch.dtype)

    def augment(self, patch: np.ndarray) -> np.ndarray:
        """Apply a random combination of enabled augmentations to a single patch.

        Parameters
        ----------
        patch : np.ndarray
            Input image patch.

        Returns
        -------
        np.ndarray
            Augmented image patch.
        """
        aug = patch.copy()
        
        # 1. Flip
        if self.flip_h and random.random() > 0.5:
            aug = self.flip(aug, 1)
        if self.flip_v and random.random() > 0.5:
            aug = self.flip(aug, 0)
            
        # 2. Rotation
        if self.rot_range > 0 and random.random() > 0.5:
            angle = random.uniform(-self.rot_range, self.rot_range)
            aug = self.rotate(aug, angle)
            
        # 3. Brightness
        if self.brightness_jitter > 0 and random.random() > 0.5:
            factor = random.uniform(1.0 - self.brightness_jitter, 1.0 + self.brightness_jitter)
            aug = self.jitter_brightness(aug, factor)
            
        # 4. Noise
        if self.noise_sigma_range and random.random() > 0.5:
            sigma = random.uniform(self.noise_sigma_range[0], self.noise_sigma_range[1])
            aug = self.add_gaussian_noise(aug, sigma)
            
        return aug

    def augment_dataset(
        self,
        patches: np.ndarray,
        labels: np.ndarray,
        target_size: int = 600,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Upsample and augment a dataset until the *target_size* is reached.

        Guarantees proportional upsampling of both positive and negative classes
        to maintain the original class balance.

        Parameters
        ----------
        patches : np.ndarray
            Original patches, shape (N, H, W, C).
        labels : np.ndarray
            Binary labels, shape (N,).
        target_size : int
            Total target size of the augmented dataset.

        Returns
        -------
        aug_patches : np.ndarray
            Augmented dataset, shape (target_size, H, W, C).
        aug_labels : np.ndarray
            Binary labels for augmented patches, shape (target_size,).
        """
        n_samples = len(patches)
        if n_samples >= target_size or n_samples == 0:
            return patches, labels
            
        logger.info("Augmenting dataset from %d to %d samples...", n_samples, target_size)
        
        aug_patches_list = list(patches)
        aug_labels_list = list(labels)
        
        # Calculate positive/negative counts
        labels_arr = np.array(labels)
        pos_indices = np.where(labels_arr == 1)[0]
        neg_indices = np.where(labels_arr == 0)[0]
        
        if len(pos_indices) == 0 or len(neg_indices) == 0:
            # Single-class dataset, just clone randomly
            while len(aug_patches_list) < target_size:
                idx = random.choice(range(n_samples))
                aug_patches_list.append(self.augment(patches[idx]))
                aug_labels_list.append(labels[idx])
        else:
            # Upsample proportionally to preserve balance
            pos_ratio = len(pos_indices) / n_samples
            target_pos = int(target_size * pos_ratio)
            target_neg = target_size - target_pos
            
            # Augment positive class
            while sum(1 for l in aug_labels_list if l == 1) < target_pos:
                idx = random.choice(pos_indices)
                aug_patches_list.append(self.augment(patches[idx]))
                aug_labels_list.append(1)
                
            # Augment negative class
            while sum(1 for l in aug_labels_list if l == 0) < target_neg:
                idx = random.choice(neg_indices)
                aug_patches_list.append(self.augment(patches[idx]))
                aug_labels_list.append(0)
                
        # Final shuffle
        combined = list(zip(aug_patches_list, aug_labels_list))
        random.shuffle(combined)
        
        shuffled_patches = np.stack([item[0] for item in combined], axis=0)
        shuffled_labels = np.array([item[1] for item in combined], dtype=labels.dtype)
        
        logger.info("Dataset upsampled to %d samples.", len(shuffled_patches))
        return shuffled_patches, shuffled_labels
