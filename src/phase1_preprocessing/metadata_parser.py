"""
metadata_parser.py — EXIF Metadata Extraction & Quality Gate Module

Extracts flight parameters from drone image EXIF data (GPS, altitude,
gimbal pitch, focal length, sensor width, timestamp) and builds a
structured DataFrame. Implements quality gates for blur, underexposure,
altitude anomalies, and temporal gap detection.

References:
    [R3] Agüera-Vega et al. (2017) — GSD calibration accuracy analysis
    [R4] Nex & Remondino (2014) — UAV photogrammetry review

Author: Saugata Malakar | IIT Kharagpur
Organisation: Cortex Construction Solutions Pvt. Ltd.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

import cv2
import numpy as np
import pandas as pd

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ImageMetadata:
    """Structured container for drone image flight parameters."""

    filename: str
    filepath: str

    # GPS
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None        # metres above sea level
    relative_altitude: Optional[float] = None    # metres above takeoff point

    # Gimbal
    gimbal_pitch: Optional[float] = None         # degrees (0 = nadir, 90 = horizon)
    gimbal_yaw: Optional[float] = None           # degrees

    # Camera
    focal_length_mm: Optional[float] = None
    sensor_width_mm: Optional[float] = None
    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None

    # Timing
    timestamp: Optional[str] = None              # ISO 8601

    # Quality metrics
    laplacian_variance: Optional[float] = None
    mean_intensity: Optional[float] = None

    # Flags
    is_blurry: bool = False
    is_underexposed: bool = False
    altitude_anomaly: bool = False
    temporal_gap: bool = False
    quality_passed: bool = True

    # Warnings
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# EXIF Parsing Helpers
# ---------------------------------------------------------------------------

def _dms_to_decimal(dms_tuple: Tuple, ref: str) -> Optional[float]:
    """Convert EXIF DMS (degrees, minutes, seconds) to decimal degrees.

    Args:
        dms_tuple: Tuple of ((deg_num, deg_den), (min_num, min_den), (sec_num, sec_den))
        ref: Reference direction ('N', 'S', 'E', 'W')

    Returns:
        Decimal degree value, negative for S/W.
    """
    try:
        degrees = dms_tuple[0][0] / dms_tuple[0][1]
        minutes = dms_tuple[1][0] / dms_tuple[1][1]
        seconds = dms_tuple[2][0] / dms_tuple[2][1]
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ('S', 'W'):
            decimal = -decimal
        return decimal
    except (TypeError, ZeroDivisionError, IndexError):
        return None


def _rational_to_float(rational: Tuple[int, int]) -> Optional[float]:
    """Convert EXIF rational (numerator, denominator) to float."""
    try:
        if rational[1] == 0:
            return None
        return rational[0] / rational[1]
    except (TypeError, IndexError):
        return None


def _parse_exif_piexif(filepath: str) -> Dict[str, Any]:
    """Parse EXIF data using piexif library.

    Args:
        filepath: Path to image file.

    Returns:
        Dictionary of extracted metadata fields.
    """
    if not HAS_PIEXIF:
        logger.warning("piexif not installed; skipping piexif parsing")
        return {}

    result = {}

    try:
        exif_dict = piexif.load(filepath)
    except Exception as e:
        logger.warning(f"piexif failed to load {filepath}: {e}")
        return {}

    # --- GPS ---
    gps_data = exif_dict.get("GPS", {})

    if piexif.GPSIFD.GPSLatitude in gps_data and piexif.GPSIFD.GPSLatitudeRef in gps_data:
        lat_ref = gps_data[piexif.GPSIFD.GPSLatitudeRef]
        if isinstance(lat_ref, bytes):
            lat_ref = lat_ref.decode('ascii')
        result['gps_latitude'] = _dms_to_decimal(
            gps_data[piexif.GPSIFD.GPSLatitude], lat_ref
        )

    if piexif.GPSIFD.GPSLongitude in gps_data and piexif.GPSIFD.GPSLongitudeRef in gps_data:
        lon_ref = gps_data[piexif.GPSIFD.GPSLongitudeRef]
        if isinstance(lon_ref, bytes):
            lon_ref = lon_ref.decode('ascii')
        result['gps_longitude'] = _dms_to_decimal(
            gps_data[piexif.GPSIFD.GPSLongitude], lon_ref
        )

    if piexif.GPSIFD.GPSAltitude in gps_data:
        result['gps_altitude'] = _rational_to_float(
            gps_data[piexif.GPSIFD.GPSAltitude]
        )

    # --- Camera ---
    exif_section = exif_dict.get("Exif", {})

    if piexif.ExifIFD.FocalLength in exif_section:
        result['focal_length_mm'] = _rational_to_float(
            exif_section[piexif.ExifIFD.FocalLength]
        )

    # --- Image dimensions ---
    ifd0 = exif_dict.get("0th", {})

    if piexif.ImageIFD.ImageWidth in ifd0:
        result['image_width_px'] = ifd0[piexif.ImageIFD.ImageWidth]
    if piexif.ImageIFD.ImageLength in ifd0:
        result['image_height_px'] = ifd0[piexif.ImageIFD.ImageLength]

    # --- Timestamp ---
    if piexif.ExifIFD.DateTimeOriginal in exif_section:
        raw_ts = exif_section[piexif.ExifIFD.DateTimeOriginal]
        if isinstance(raw_ts, bytes):
            raw_ts = raw_ts.decode('ascii')
        result['timestamp'] = raw_ts

    return result


def _parse_exif_exiftool(filepath: str) -> Dict[str, Any]:
    """Parse EXIF data using exiftool subprocess as fallback.

    Extracts DJI-specific XMP fields (RelativeAltitude, GimbalPitchDegree,
    GimbalYawDegree) that piexif cannot access.

    Args:
        filepath: Path to image file.

    Returns:
        Dictionary of extracted metadata fields.
    """
    result = {}

    try:
        cmd = [
            'exiftool', '-json',
            '-GPSLatitude', '-GPSLongitude', '-GPSAltitude',
            '-RelativeAltitude',
            '-GimbalPitchDegree', '-GimbalYawDegree',
            '-FocalLength', '-SensorWidth',
            '-ImageWidth', '-ImageHeight',
            '-DateTimeOriginal',
            '-n',  # numeric output (decimal degrees, not DMS)
            filepath
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if proc.returncode != 0:
            logger.warning(f"exiftool failed on {filepath}: {proc.stderr}")
            return {}

        data = json.loads(proc.stdout)
        if not data:
            return {}
        data = data[0]

    except FileNotFoundError:
        logger.warning("exiftool not found in PATH; skipping exiftool parsing")
        return {}
    except subprocess.TimeoutExpired:
        logger.warning(f"exiftool timed out on {filepath}")
        return {}
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"exiftool output parse error: {e}")
        return {}

    # Map exiftool fields → our schema
    field_map = {
        'GPSLatitude': 'gps_latitude',
        'GPSLongitude': 'gps_longitude',
        'GPSAltitude': 'gps_altitude',
        'RelativeAltitude': 'relative_altitude',
        'GimbalPitchDegree': 'gimbal_pitch',
        'GimbalYawDegree': 'gimbal_yaw',
        'FocalLength': 'focal_length_mm',
        'SensorWidth': 'sensor_width_mm',
        'ImageWidth': 'image_width_px',
        'ImageHeight': 'image_height_px',
        'DateTimeOriginal': 'timestamp',
    }

    for exif_key, our_key in field_map.items():
        if exif_key in data and data[exif_key] is not None:
            val = data[exif_key]
            # Handle string-encoded floats from DJI XMP tags
            if isinstance(val, str):
                try:
                    val = float(val.replace('+', ''))
                except ValueError:
                    pass
            result[our_key] = val

    return result


# ---------------------------------------------------------------------------
# Quality Assessment
# ---------------------------------------------------------------------------

def compute_image_quality(image: np.ndarray) -> Tuple[float, float]:
    """Compute blur metric (Laplacian variance) and mean intensity.

    Args:
        image: BGR image array (OpenCV format).

    Returns:
        Tuple of (laplacian_variance, mean_intensity).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    mean_intensity = float(np.mean(gray))
    return float(laplacian_var), mean_intensity


# ---------------------------------------------------------------------------
# Main Parser Class
# ---------------------------------------------------------------------------

class MetadataParser:
    """Parses EXIF metadata from drone images and applies quality gates.

    Attributes:
        laplacian_min: Minimum Laplacian variance for blur gate.
        intensity_min: Minimum mean intensity for underexposure gate.
        altitude_sigma: Number of sigma for altitude anomaly detection.
        temporal_gap_multiplier: Multiplier for temporal gap detection.

    Example:
        >>> parser = MetadataParser(config)
        >>> df = parser.parse_directory("data/raw/")
        >>> clean_df = parser.apply_quality_gates(df)
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialise MetadataParser with configuration parameters.

        Args:
            config: Dictionary of quality_gate parameters. If None, uses defaults.
        """
        config = config or {}
        qg = config.get('quality_gate', {})
        self.laplacian_min = qg.get('laplacian_variance_min', 5)
        self.intensity_min = qg.get('mean_intensity_min', 30)
        self.altitude_sigma = qg.get('altitude_anomaly_sigma', 2.0)
        self.temporal_gap_multiplier = qg.get('temporal_gap_multiplier', 3.0)

    def parse_single_image(self, filepath: str) -> ImageMetadata:
        """Parse metadata and compute quality metrics for a single image.

        Args:
            filepath: Path to the image file (JPG, DNG, TIFF).

        Returns:
            Populated ImageMetadata dataclass.
        """
        filepath = str(Path(filepath).resolve())
        filename = Path(filepath).name

        meta = ImageMetadata(filename=filename, filepath=filepath)

        # --- EXIF extraction: piexif first, exiftool fills gaps ---
        piexif_data = _parse_exif_piexif(filepath)
        exiftool_data = _parse_exif_exiftool(filepath)

        # Merge: exiftool overrides piexif for DJI-specific fields
        merged = {**piexif_data, **exiftool_data}

        for field_name, value in merged.items():
            if hasattr(meta, field_name) and value is not None:
                setattr(meta, field_name, value)

        # --- Populate image dimensions from actual image if missing ---
        try:
            image = cv2.imread(filepath)
            if image is not None:
                if meta.image_height_px is None:
                    meta.image_height_px = image.shape[0]
                if meta.image_width_px is None:
                    meta.image_width_px = image.shape[1]

                # Quality metrics
                lap_var, mean_int = compute_image_quality(image)
                meta.laplacian_variance = lap_var
                meta.mean_intensity = mean_int

                # Quality gates
                if lap_var < self.laplacian_min:
                    meta.is_blurry = True
                    meta.quality_passed = False
                    meta.warnings.append(
                        f"Blurry: Laplacian variance {lap_var:.1f} < {self.laplacian_min}"
                    )

                if mean_int < self.intensity_min:
                    meta.is_underexposed = True
                    meta.quality_passed = False
                    meta.warnings.append(
                        f"Underexposed: mean intensity {mean_int:.1f} < {self.intensity_min}"
                    )
            else:
                meta.quality_passed = False
                meta.warnings.append(f"Failed to load image: {filepath}")
        except Exception as e:
            meta.quality_passed = False
            meta.warnings.append(f"Image read error: {e}")

        # Warn on missing critical fields
        if meta.gps_latitude is None or meta.gps_longitude is None:
            meta.warnings.append("Missing GPS coordinates")
        if meta.focal_length_mm is None:
            meta.warnings.append("Missing focal length")
        if meta.relative_altitude is None and meta.gps_altitude is None:
            meta.warnings.append("Missing altitude data")

        # Scale Reference Validation
        if (meta.gps_latitude is None or meta.gps_longitude is None) and (meta.relative_altitude is None and meta.gps_altitude is None):
            meta.warnings.append("CRITICAL WARNING: No GPS coordinate or altitude scale reference found in image EXIF. Scale markers must be present for correct calibration. Reshoot suggested.")

        return meta

    def parse_directory(
        self,
        directory: str,
        extensions: Tuple[str, ...] = ('.jpg', '.jpeg', '.dng', '.tiff', '.tif', '.png')
    ) -> pd.DataFrame:
        """Parse all drone images in a directory and build metadata DataFrame.

        Args:
            directory: Path to directory containing drone images.
            extensions: Tuple of valid file extensions (case-insensitive).

        Returns:
            DataFrame with one row per image, columns matching ImageMetadata fields.
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise FileNotFoundError(f"Directory not found: {directory}")

        image_files = sorted([
            f for f in directory.iterdir()
            if f.is_file() and f.suffix.lower() in extensions
        ])

        if not image_files:
            logger.warning(f"No image files found in {directory}")
            return pd.DataFrame()

        logger.info(f"Parsing {len(image_files)} images from {directory}")

        records = []
        for img_path in image_files:
            logger.debug(f"Parsing: {img_path.name}")
            meta = self.parse_single_image(str(img_path))
            record = asdict(meta)
            # Convert warnings list to semicolon-separated string for DataFrame
            record['warnings'] = '; '.join(record['warnings']) if record['warnings'] else ''
            records.append(record)

        df = pd.DataFrame(records)
        logger.info(f"Parsed {len(df)} images; {df['quality_passed'].sum()} passed quality gate")
        return df

    def apply_quality_gates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply altitude anomaly and temporal gap detection to metadata DataFrame.

        This is a second-pass analysis that requires the full dataset to compute
        statistical thresholds (median altitude, median timestamp interval).

        Args:
            df: DataFrame from parse_directory().

        Returns:
            DataFrame with updated anomaly flags.
        """
        if df.empty:
            return df

        df = df.copy()

        # --- Altitude anomaly detection ---
        altitude_col = 'relative_altitude' if df['relative_altitude'].notna().any() else 'gps_altitude'

        if df[altitude_col].notna().sum() >= 3:
            median_alt = df[altitude_col].median()
            std_alt = df[altitude_col].std()

            if std_alt > 0:
                anomaly_mask = (
                    (df[altitude_col] - median_alt).abs() > self.altitude_sigma * std_alt
                )
                df.loc[anomaly_mask, 'altitude_anomaly'] = True

                n_anomalies = anomaly_mask.sum()
                if n_anomalies > 0:
                    logger.warning(
                        f"Altitude anomalies detected: {n_anomalies} frames "
                        f"(median={median_alt:.1f}m, σ={std_alt:.1f}m, "
                        f"threshold=±{self.altitude_sigma * std_alt:.1f}m)"
                    )

        # --- Temporal gap detection ---
        if df['timestamp'].notna().sum() >= 3:
            try:
                # Parse timestamps — handle EXIF format "YYYY:MM:DD HH:MM:SS"
                ts_series = pd.to_datetime(
                    df['timestamp'].str.replace(':', '-', 2),
                    errors='coerce'
                )

                if ts_series.notna().sum() >= 3:
                    sorted_ts = ts_series.sort_values()
                    intervals = sorted_ts.diff().dt.total_seconds().dropna()

                    if len(intervals) > 0:
                        median_interval = intervals.median()

                        if median_interval > 0:
                            gap_threshold = self.temporal_gap_multiplier * median_interval
                            gap_indices = intervals[intervals > gap_threshold].index

                            for idx in gap_indices:
                                df.loc[idx, 'temporal_gap'] = True

                            n_gaps = len(gap_indices)
                            if n_gaps > 0:
                                logger.warning(
                                    f"Temporal gaps detected: {n_gaps} gaps "
                                    f"(median interval={median_interval:.1f}s, "
                                    f"threshold={gap_threshold:.1f}s)"
                                )
            except Exception as e:
                logger.warning(f"Temporal gap detection failed: {e}")

        # Update overall quality flag
        df['quality_passed'] = df['quality_passed'] & ~df['altitude_anomaly']

        return df

    def get_clean_images(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter DataFrame to only quality-passed images.

        Args:
            df: DataFrame with quality gates applied.

        Returns:
            Filtered DataFrame.
        """
        clean = df[df['quality_passed']].copy()
        logger.info(
            f"Quality filter: {len(clean)}/{len(df)} images passed "
            f"({len(df) - len(clean)} rejected)"
        )
        return clean

    def to_json(self, df: pd.DataFrame, output_path: str) -> str:
        """Export metadata DataFrame to JSON file.

        Args:
            df: Metadata DataFrame.
            output_path: Path to output JSON file.

        Returns:
            Path to written JSON file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        records = df.to_dict(orient='records')
        with open(output_path, 'w') as f:
            json.dump(records, f, indent=2, default=str)

        logger.info(f"Metadata exported to {output_path}")
        return str(output_path)
