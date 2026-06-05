"""
Phase 1 — Pre-processing
=========================

Drone image pre-processing pipeline responsible for:
    - **Quality Gate**: Rejects blurry (Laplacian variance) and
      over-/under-exposed frames before they enter the pipeline.
    - **Image Enhancement**: Applies CLAHE (Contrast Limited Adaptive Histogram
      Equalisation) and optional unsharp-mask sharpening.
    - **Mosaic Stitching**: Aligns and stitches overlapping drone frames into
      geo-referenced panoramic mosaics using ORB/SIFT feature matching.
    - **GSD Calibration**: Computes Ground Sampling Distance from EXIF metadata
      (focal length, sensor width, flight altitude) so that downstream pixel
      measurements map to real-world metric units.

Typical usage::

    from src.phase1_preprocessing import PreprocessingPipeline
    pipeline = PreprocessingPipeline(config)
    pipeline.run(input_dir="data/raw/", output_dir="data/enhanced/")
"""

# Public API (uncomment as classes are implemented)
# from .quality_gate import QualityGate
# from .enhancement import ImageEnhancer
# from .stitching import MosaicStitcher
# from .gsd_calibration import GSDCalibrator
# from .preprocessing_pipeline import PreprocessingPipeline

__all__ = [
    # "QualityGate",
    # "ImageEnhancer",
    # "MosaicStitcher",
    # "GSDCalibrator",
    # "PreprocessingPipeline",
]
