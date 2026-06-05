"""
I/O Helper Utilities
====================

Convenience functions for image loading / saving, directory scaffolding,
and format conversion used across all pipeline phases.

Usage::

    from src.utils.io_helpers import load_image, save_image, ensure_dir

    img = load_image("data/raw/frame_001.jpg")
    ensure_dir("data/enhanced/")
    save_image(img, "data/enhanced/frame_001_clahe.png")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Supported image extensions (lowercase)
_IMAGE_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp",
}


# ------------------------------------------------------------------
# Directory utilities
# ------------------------------------------------------------------

def ensure_dir(path: str | Path) -> Path:
    """Create a directory (and parents) if it does not exist.

    Parameters
    ----------
    path : str | Path
        Directory path to create.

    Returns
    -------
    Path
        Resolved ``Path`` object.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


# ------------------------------------------------------------------
# Image loading
# ------------------------------------------------------------------

def load_image(
    path: str | Path,
    *,
    color: bool = True,
    as_float: bool = False,
) -> np.ndarray:
    """Load an image from disk using OpenCV.

    Parameters
    ----------
    path : str | Path
        File path to the image.
    color : bool
        If ``True`` (default), load as BGR; otherwise grayscale.
    as_float : bool
        If ``True``, convert to ``float32`` in [0, 1].

    Returns
    -------
    np.ndarray
        Loaded image array.

    Raises
    ------
    FileNotFoundError
        If the image file does not exist.
    ValueError
        If the image could not be decoded.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")

    flag = cv2.IMREAD_COLOR if color else cv2.IMREAD_GRAYSCALE
    img = cv2.imread(str(p), flag)

    if img is None:
        raise ValueError(f"Failed to decode image: {p}")

    if as_float:
        img = img.astype(np.float32) / 255.0

    logger.debug("Loaded image %s  shape=%s  dtype=%s", p.name, img.shape, img.dtype)
    return img


def load_image_pil(
    path: str | Path,
    *,
    mode: str = "RGB",
) -> Image.Image:
    """Load an image as a Pillow ``Image`` object.

    Parameters
    ----------
    path : str | Path
        File path to the image.
    mode : str
        Target colour mode (e.g. ``"RGB"``, ``"L"``).

    Returns
    -------
    PIL.Image.Image
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")
    img = Image.open(p).convert(mode)
    logger.debug("Loaded PIL image %s  mode=%s  size=%s", p.name, img.mode, img.size)
    return img


# ------------------------------------------------------------------
# Image saving
# ------------------------------------------------------------------

def save_image(
    image: np.ndarray,
    path: str | Path,
    *,
    create_parents: bool = True,
    quality: int = 95,
) -> Path:
    """Save an image to disk using OpenCV.

    Parameters
    ----------
    image : np.ndarray
        Image array (BGR or grayscale).
    path : str | Path
        Destination file path.
    create_parents : bool
        Automatically create parent directories.
    quality : int
        JPEG quality (1–100). Ignored for lossless formats.

    Returns
    -------
    Path
        Resolved output path.
    """
    p = Path(path)
    if create_parents:
        p.parent.mkdir(parents=True, exist_ok=True)

    params: list = []
    ext = p.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    elif ext == ".png":
        params = [cv2.IMWRITE_PNG_COMPRESSION, 3]

    success = cv2.imwrite(str(p), image, params)
    if not success:
        raise IOError(f"Failed to save image: {p}")

    logger.debug("Saved image %s  shape=%s", p.name, image.shape)
    return p.resolve()


# ------------------------------------------------------------------
# Batch / directory listing
# ------------------------------------------------------------------

def list_images(
    directory: str | Path,
    *,
    extensions: Optional[Sequence[str]] = None,
    recursive: bool = False,
) -> List[Path]:
    """Return sorted list of image file paths in a directory.

    Parameters
    ----------
    directory : str | Path
        Root directory to scan.
    extensions : Sequence[str] | None
        Allowed extensions (default: common image formats).
    recursive : bool
        Walk subdirectories recursively.

    Returns
    -------
    list[Path]
        Sorted list of image paths.
    """
    exts = set(extensions) if extensions else _IMAGE_EXTENSIONS
    d = Path(directory)
    if not d.is_dir():
        raise NotADirectoryError(f"Not a directory: {d}")

    pattern = "**/*" if recursive else "*"
    files = sorted(
        p for p in d.glob(pattern)
        if p.is_file() and p.suffix.lower() in exts
    )
    logger.info("Found %d images in %s", len(files), d)
    return files


# ------------------------------------------------------------------
# Format conversion helpers
# ------------------------------------------------------------------

def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    """Convert BGR (OpenCV) array to RGB."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(image: np.ndarray) -> np.ndarray:
    """Convert RGB array to BGR (OpenCV)."""
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a BGR image to single-channel grayscale."""
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def resize_image(
    image: np.ndarray,
    target_size: Tuple[int, int],
    *,
    interpolation: int = cv2.INTER_LINEAR,
) -> np.ndarray:
    """Resize an image to ``(width, height)``.

    Parameters
    ----------
    image : np.ndarray
        Source image.
    target_size : tuple[int, int]
        ``(width, height)`` of the output.
    interpolation : int
        OpenCV interpolation flag.

    Returns
    -------
    np.ndarray
        Resized image.
    """
    return cv2.resize(image, target_size, interpolation=interpolation)
