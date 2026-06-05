"""
Geo-spatial Utilities
=====================

GPS coordinate extraction from EXIF metadata, decimal degree conversion,
and CRS (Coordinate Reference System) transforms via *pyproj*.

Usage::

    from src.utils.geo_utils import exif_gps_to_decimal, transform_crs

    lat, lon = exif_gps_to_decimal(exif_dict)
    x, y = transform_crs(lat, lon, from_crs="EPSG:4326", to_crs="EPSG:32643")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple


try:
    import piexif
except ImportError:
    piexif = None  # type: ignore[assignment]

try:
    from pyproj import CRS, Transformer
except ImportError:
    CRS = None  # type: ignore[assignment,misc]
    Transformer = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# EXIF GPS parsing
# ------------------------------------------------------------------

def _dms_to_decimal(dms_tuple: tuple, ref: str) -> float:
    """Convert (degrees, minutes, seconds) EXIF rational tuples to decimal degrees.

    Each element is a tuple ``(numerator, denominator)`` as stored by piexif.
    """
    degrees = dms_tuple[0][0] / dms_tuple[0][1]
    minutes = dms_tuple[1][0] / dms_tuple[1][1]
    seconds = dms_tuple[2][0] / dms_tuple[2][1]
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def exif_gps_to_decimal(
    exif_dict: Dict[str, Any],
) -> Optional[Tuple[float, float]]:
    """Extract GPS latitude and longitude from an EXIF dictionary.

    Parameters
    ----------
    exif_dict : dict
        EXIF dictionary as returned by ``piexif.load()``.

    Returns
    -------
    tuple[float, float] | None
        ``(latitude, longitude)`` in decimal degrees, or ``None``
        if GPS data is absent.
    """
    gps_data = exif_dict.get("GPS", {})
    if not gps_data:
        logger.debug("No GPS IFD found in EXIF data.")
        return None

    try:
        lat_dms = gps_data[piexif.GPSIFD.GPSLatitude]
        lat_ref = gps_data[piexif.GPSIFD.GPSLatitudeRef].decode("ascii")
        lon_dms = gps_data[piexif.GPSIFD.GPSLongitude]
        lon_ref = gps_data[piexif.GPSIFD.GPSLongitudeRef].decode("ascii")
    except (KeyError, AttributeError):
        logger.debug("Incomplete GPS tags in EXIF data.")
        return None

    lat = _dms_to_decimal(lat_dms, lat_ref)
    lon = _dms_to_decimal(lon_dms, lon_ref)
    logger.debug("Parsed GPS: lat=%.6f, lon=%.6f", lat, lon)
    return lat, lon


def extract_altitude(exif_dict: Dict[str, Any]) -> Optional[float]:
    """Extract GPS altitude (metres above sea level) from EXIF data.

    Returns
    -------
    float | None
        Altitude in metres, or ``None`` if unavailable.
    """
    gps_data = exif_dict.get("GPS", {})
    if not gps_data:
        return None
    try:
        alt = gps_data[piexif.GPSIFD.GPSAltitude]
        alt_val = alt[0] / alt[1]
        # Ref: 0 = above sea level, 1 = below
        ref = gps_data.get(piexif.GPSIFD.GPSAltitudeRef, 0)
        if ref == 1:
            alt_val = -alt_val
        return float(alt_val)
    except (KeyError, TypeError, ZeroDivisionError):
        return None


# ------------------------------------------------------------------
# CRS transforms
# ------------------------------------------------------------------

def transform_crs(
    lat: float,
    lon: float,
    *,
    from_crs: str = "EPSG:4326",
    to_crs: str = "EPSG:32643",
) -> Tuple[float, float]:
    """Transform coordinates between Coordinate Reference Systems.

    Parameters
    ----------
    lat : float
        Latitude (or northing) in the source CRS.
    lon : float
        Longitude (or easting) in the source CRS.
    from_crs : str
        Source CRS identifier (default: WGS-84 geographic).
    to_crs : str
        Target CRS identifier (default: UTM zone 43N — typical for India).

    Returns
    -------
    tuple[float, float]
        ``(easting, northing)`` in the target CRS.

    Raises
    ------
    RuntimeError
        If *pyproj* is not installed.
    """
    if Transformer is None:
        raise RuntimeError("pyproj is required for CRS transforms.")

    transformer = Transformer.from_crs(from_crs, to_crs, always_xy=False)
    easting, northing = transformer.transform(lat, lon)
    logger.debug(
        "CRS transform (%s → %s): (%.6f, %.6f) → (%.2f, %.2f)",
        from_crs, to_crs, lat, lon, easting, northing,
    )
    return easting, northing


def compute_gsd(
    focal_length_mm: float,
    sensor_width_mm: float,
    image_width_px: int,
    altitude_m: float,
) -> float:
    """Compute Ground Sampling Distance (GSD) in cm/pixel.

    GSD = (altitude × sensor_width) / (focal_length × image_width) × 100

    Parameters
    ----------
    focal_length_mm : float
        Camera focal length in millimetres.
    sensor_width_mm : float
        Physical sensor width in millimetres.
    image_width_px : int
        Image width in pixels.
    altitude_m : float
        Flight altitude above ground in metres.

    Returns
    -------
    float
        GSD in **cm/pixel**.
    """
    if focal_length_mm <= 0 or image_width_px <= 0:
        raise ValueError("Focal length and image width must be positive.")
    gsd = (altitude_m * sensor_width_mm) / (focal_length_mm * image_width_px) * 100.0
    logger.debug(
        "GSD = %.4f cm/px  (focal=%.1f mm, sensor=%.1f mm, "
        "width=%d px, alt=%.1f m)",
        gsd, focal_length_mm, sensor_width_mm, image_width_px, altitude_m,
    )
    return gsd


def pixels_to_metres(pixel_value: float, gsd_cm_per_px: float) -> float:
    """Convert a pixel measurement to metres using GSD.

    Parameters
    ----------
    pixel_value : float
        Measurement in pixels.
    gsd_cm_per_px : float
        Ground Sampling Distance (cm per pixel).

    Returns
    -------
    float
        Measurement in metres.
    """
    return pixel_value * gsd_cm_per_px / 100.0
