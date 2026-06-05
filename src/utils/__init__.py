"""
Utilities
=========

Shared helper modules used across all pipeline phases:
    - **config_loader**: YAML-based configuration loading and validation.
    - **io_helpers**: Image I/O, directory scaffolding, format conversion.
    - **geo_utils**: GPS coordinate parsing, CRS transforms (pyproj).
    - **viz_utils**: Matplotlib/Seaborn plotting helpers for overlays,
      heatmaps, and annotated defect visualisations.
"""

# Public API (uncomment as modules are implemented)
# from .config_loader import PipelineConfig
# from .io_helpers import load_image, save_image, ensure_dir
# from .geo_utils import exif_gps_to_decimal, transform_crs
# from .viz_utils import overlay_mask, plot_severity_histogram

__all__ = [
    # "PipelineConfig",
    # "load_image",
    # "save_image",
    # "ensure_dir",
    # "exif_gps_to_decimal",
    # "transform_crs",
    # "overlay_mask",
    # "plot_severity_histogram",
]
