"""
Visualisation Utilities
=======================

Matplotlib / Seaborn helper functions for creating defect overlays,
severity histograms, heat-maps, and annotated comparison figures used
by the reporting phase and interactive notebooks.

Usage::

    from src.utils.viz_utils import overlay_mask, plot_severity_histogram

    overlay = overlay_mask(image, mask, alpha=0.4)
    plot_severity_histogram(severity_scores, save_path="fig.png")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend for server / CI
    import matplotlib.pyplot as plt
except ImportError:
    plt = None  # type: ignore[assignment]

try:
    import seaborn as sns
except ImportError:
    sns = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Colour palette
# ------------------------------------------------------------------

# Severity levels → BGR colours (for OpenCV overlays)
SEVERITY_COLOURS_BGR: Dict[str, Tuple[int, int, int]] = {
    "low":      (0, 200, 0),       # green
    "medium":   (0, 180, 255),     # orange
    "high":     (0, 0, 255),       # red
    "critical": (0, 0, 180),       # dark red
}

# Same palette as RGB hex for Matplotlib
SEVERITY_COLOURS_HEX: Dict[str, str] = {
    "low":      "#00C800",
    "medium":   "#FFB400",
    "high":     "#FF0000",
    "critical": "#B40000",
}


# ------------------------------------------------------------------
# Overlay helpers
# ------------------------------------------------------------------

def overlay_mask(
    image: np.ndarray,
    mask: np.ndarray,
    *,
    colour: Tuple[int, int, int] = (0, 0, 255),
    alpha: float = 0.4,
) -> np.ndarray:
    """Overlay a binary mask on an image with transparency.

    Parameters
    ----------
    image : np.ndarray
        BGR image (H × W × 3).
    mask : np.ndarray
        Binary mask (H × W), non-zero pixels are overlaid.
    colour : tuple[int, int, int]
        BGR colour for the overlay.
    alpha : float
        Transparency of the overlay (0 = invisible, 1 = opaque).

    Returns
    -------
    np.ndarray
        Annotated BGR image (copy).
    """
    out = image.copy()
    overlay = out.copy()
    overlay[mask > 0] = colour
    cv2.addWeighted(overlay, alpha, out, 1 - alpha, 0, out)
    return out


def draw_contours(
    image: np.ndarray,
    mask: np.ndarray,
    *,
    colour: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """Draw contours from a binary mask onto an image.

    Parameters
    ----------
    image : np.ndarray
        BGR image (H × W × 3).
    mask : np.ndarray
        Binary mask (H × W).
    colour : tuple
        BGR colour.
    thickness : int
        Line thickness.

    Returns
    -------
    np.ndarray
        Annotated image (copy).
    """
    out = image.copy()
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
    )
    cv2.drawContours(out, contours, -1, colour, thickness)
    return out


def annotate_defects(
    image: np.ndarray,
    detections: List[Dict],
    *,
    font_scale: float = 0.5,
    thickness: int = 1,
) -> np.ndarray:
    """Draw bounding boxes and labels for detected defects.

    Parameters
    ----------
    image : np.ndarray
        BGR image.
    detections : list[dict]
        Each dict must have ``"bbox"`` (x, y, w, h) and ``"label"`` keys.
        Optional: ``"severity"`` for colour coding.

    Returns
    -------
    np.ndarray
        Annotated image (copy).
    """
    out = image.copy()
    for det in detections:
        x, y, w, h = det["bbox"]
        severity = det.get("severity", "medium")
        colour = SEVERITY_COLOURS_BGR.get(severity, (255, 255, 255))
        cv2.rectangle(out, (x, y), (x + w, y + h), colour, 2)
        label = det.get("label", "defect")
        cv2.putText(
            out, label, (x, y - 5),
            cv2.FONT_HERSHEY_SIMPLEX, font_scale, colour, thickness,
        )
    return out


# ------------------------------------------------------------------
# Matplotlib / Seaborn plots
# ------------------------------------------------------------------

def plot_severity_histogram(
    scores: Sequence[float],
    *,
    bins: int = 30,
    title: str = "Severity Score Distribution",
    save_path: Optional[str | Path] = None,
    figsize: Tuple[float, float] = (8, 5),
) -> None:
    """Plot a histogram of severity / V-Index scores.

    Parameters
    ----------
    scores : array-like
        Numeric severity scores.
    bins : int
        Number of histogram bins.
    title : str
        Figure title.
    save_path : str | Path | None
        If provided, save the figure to this path.
    figsize : tuple
        Figure size in inches.
    """
    if plt is None:
        logger.warning("matplotlib not installed; skipping histogram plot.")
        return

    fig, ax = plt.subplots(figsize=figsize)
    if sns is not None:
        sns.histplot(scores, bins=bins, kde=True, ax=ax, color="#4a90d9")
    else:
        ax.hist(scores, bins=bins, color="#4a90d9", edgecolor="white")

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("Severity Score")
    ax.set_ylabel("Count")
    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")
        logger.info("Saved histogram to %s", save_path)
    plt.close(fig)


def plot_defect_pie(
    counts: Dict[str, int],
    *,
    title: str = "Defect Type Distribution",
    save_path: Optional[str | Path] = None,
    figsize: Tuple[float, float] = (7, 7),
) -> None:
    """Create a pie chart of defect type distribution.

    Parameters
    ----------
    counts : dict[str, int]
        Mapping of defect type → count.
    title : str
        Figure title.
    save_path : str | Path | None
        Optional save path.
    figsize : tuple
        Figure size.
    """
    if plt is None:
        logger.warning("matplotlib not installed; skipping pie chart.")
        return

    labels = list(counts.keys())
    values = list(counts.values())
    colours = list(SEVERITY_COLOURS_HEX.values())[:len(labels)]

    fig, ax = plt.subplots(figsize=figsize)
    ax.pie(
        values, labels=labels, colors=colours,
        autopct="%1.1f%%", startangle=140,
        textprops={"fontsize": 11},
    )
    ax.set_title(title, fontsize=14, fontweight="bold")
    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")
        logger.info("Saved pie chart to %s", save_path)
    plt.close(fig)


def plot_side_by_side(
    img_left: np.ndarray,
    img_right: np.ndarray,
    *,
    titles: Tuple[str, str] = ("Original", "Processed"),
    save_path: Optional[str | Path] = None,
    figsize: Tuple[float, float] = (14, 6),
) -> None:
    """Show two images side-by-side (e.g. before / after enhancement).

    Parameters
    ----------
    img_left : np.ndarray
        Left image (BGR or grayscale).
    img_right : np.ndarray
        Right image.
    titles : tuple[str, str]
        Subplot titles.
    save_path : str | Path | None
        Optional save path.
    figsize : tuple
        Figure size.
    """
    if plt is None:
        logger.warning("matplotlib not installed; skipping side-by-side plot.")
        return

    def _prepare(img: np.ndarray) -> np.ndarray:
        if img.ndim == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    fig, axes = plt.subplots(1, 2, figsize=figsize)
    for ax, img, t in zip(axes, [img_left, img_right], titles):
        cmap = "gray" if img.ndim == 2 else None
        ax.imshow(_prepare(img), cmap=cmap)
        ax.set_title(t, fontsize=13, fontweight="bold")
        ax.axis("off")
    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")
        logger.info("Saved comparison figure to %s", save_path)
    plt.close(fig)
