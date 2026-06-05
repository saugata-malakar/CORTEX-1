"""
geo_referencer.py — GPS-Pixel Coordinate Mapping & Geo-Reference Module

Generates a geo-reference grid mapping pixel coordinates in the stitched
mosaic to real-world GPS coordinates. Enables spatial querying of defect
locations and integration with GIS systems.

References:
    [R3] Agüera-Vega et al. (2017) — Photogrammetric mapping accuracy
    [R4] Nex & Remondino (2014) — UAV geo-referencing methodology

Author: Saugata Malakar | IIT Kharagpur
Organisation: Cortex Construction Solutions Pvt. Ltd.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

try:
    import pyproj  # noqa: F401
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False

logger = logging.getLogger(__name__)


# ===========================================================================
# GPS Interpolation
# ===========================================================================

def build_gps_pixel_mapping(
    image_metadata: List[Dict[str, Any]],
    mosaic_shape: Tuple[int, int],
    homographies: Optional[List[np.ndarray]] = None
) -> List[Dict[str, Any]]:
    """Build GPS-pixel mapping from image metadata and stitching transforms.

    Maps each source image's GPS coordinates to its position in the mosaic
    using the homography transforms from the stitching process.

    Args:
        image_metadata: List of metadata dicts with gps_latitude, gps_longitude.
        mosaic_shape: (height, width) of the stitched mosaic.
        homographies: List of homography matrices from stitching (optional).

    Returns:
        List of control point dicts: {pixel_x, pixel_y, gps_lat, gps_lon}.
    """
    control_points = []

    for i, meta in enumerate(image_metadata):
        lat = meta.get('gps_latitude')
        lon = meta.get('gps_longitude')
        img_w = meta.get('image_width_px')
        img_h = meta.get('image_height_px')

        if lat is None or lon is None:
            continue

        # Image centre in source image coordinates
        if img_w and img_h:
            cx, cy = img_w / 2.0, img_h / 2.0
        else:
            cx, cy = 0, 0

        # Transform to mosaic coordinates if homography available
        if homographies and i < len(homographies) and homographies[i] is not None:
            H = homographies[i]
            pt = np.float32([[cx, cy]]).reshape(-1, 1, 2)
            import cv2
            transformed = cv2.perspectiveTransform(pt, H)
            px, py = transformed[0][0]
        else:
            # Approximate: distribute evenly across mosaic
            n = len(image_metadata)
            px = (i / max(n - 1, 1)) * mosaic_shape[1]
            py = mosaic_shape[0] / 2.0

        control_points.append({
            'pixel_x': float(px),
            'pixel_y': float(py),
            'gps_latitude': float(lat),
            'gps_longitude': float(lon),
            'source_image': meta.get('filename', f'image_{i}')
        })

    logger.info(f"Built {len(control_points)} GPS-pixel control points")
    return control_points


# ===========================================================================
# Geo-Reference Grid
# ===========================================================================

class GeoReferencer:
    """Generates and manages geo-reference grids for mosaic images.

    Creates a regular grid of sample points across the mosaic and interpolates
    GPS coordinates using available control points.

    Args:
        config: Pipeline configuration dictionary.

    Example:
        >>> georef = GeoReferencer(config)
        >>> grid = georef.generate_grid(mosaic_shape, control_points)
        >>> georef.save_grid(grid, "data/geo_reference.json")
    """

    def __init__(self, config: Optional[Dict] = None):
        config = config or {}
        geo_config = config.get('geo_reference', {})

        self.grid_spacing_px = geo_config.get('grid_sample_spacing_px', 500)
        self.gps_rmse_target = geo_config.get('gps_rmse_target_m', 0.5)

    def generate_grid(
        self,
        mosaic_shape: Tuple[int, int],
        control_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate a geo-reference grid for the mosaic.

        Interpolates GPS coordinates at regular grid intervals using
        linear interpolation from control points.

        Args:
            mosaic_shape: (height, width) of the mosaic.
            control_points: List of GPS-pixel control point dicts.

        Returns:
            Dictionary with grid data and metadata.
        """
        h, w = mosaic_shape

        if len(control_points) < 2:
            logger.warning("Insufficient control points for geo-referencing (need >= 2)")
            return self._empty_grid(mosaic_shape)

        # Extract control point arrays
        cp_px = np.array([[cp['pixel_x'], cp['pixel_y']] for cp in control_points])
        cp_lat = np.array([cp['gps_latitude'] for cp in control_points])
        cp_lon = np.array([cp['gps_longitude'] for cp in control_points])

        # Generate regular grid
        grid_x = np.arange(0, w, self.grid_spacing_px)
        grid_y = np.arange(0, h, self.grid_spacing_px)

        grid_points = []
        for gx in grid_x:
            for gy in grid_y:
                # Inverse distance weighted interpolation
                lat, lon = self._interpolate_gps(
                    gx, gy, cp_px, cp_lat, cp_lon
                )
                grid_points.append({
                    'pixel_x': int(gx),
                    'pixel_y': int(gy),
                    'gps_latitude': float(lat),
                    'gps_longitude': float(lon)
                })

        grid_data = {
            'mosaic_width_px': int(w),
            'mosaic_height_px': int(h),
            'grid_spacing_px': self.grid_spacing_px,
            'num_control_points': len(control_points),
            'num_grid_points': len(grid_points),
            'control_points': control_points,
            'grid_points': grid_points,
            'coordinate_system': 'WGS84 (EPSG:4326)',
            'interpolation_method': 'inverse_distance_weighted'
        }

        logger.info(
            f"Geo-reference grid generated: {len(grid_points)} points "
            f"({len(grid_x)}×{len(grid_y)}) from {len(control_points)} control points"
        )

        return grid_data

    def _interpolate_gps(
        self,
        px: float,
        py: float,
        control_pixels: np.ndarray,
        control_lat: np.ndarray,
        control_lon: np.ndarray,
        power: float = 2.0
    ) -> Tuple[float, float]:
        """Interpolate GPS coordinates using inverse distance weighting (IDW).

        Args:
            px: Query pixel x-coordinate.
            py: Query pixel y-coordinate.
            control_pixels: Nx2 array of control point pixel coordinates.
            control_lat: N array of control point latitudes.
            control_lon: N array of control point longitudes.
            power: IDW power parameter (higher = more local).

        Returns:
            Tuple of (interpolated_latitude, interpolated_longitude).
        """
        distances = np.sqrt(
            (control_pixels[:, 0] - px) ** 2 +
            (control_pixels[:, 1] - py) ** 2
        )

        # Handle exact match
        min_dist_idx = np.argmin(distances)
        if distances[min_dist_idx] < 1.0:
            return float(control_lat[min_dist_idx]), float(control_lon[min_dist_idx])

        # Inverse distance weights
        weights = 1.0 / (distances ** power)
        weights /= weights.sum()

        lat = float(np.sum(weights * control_lat))
        lon = float(np.sum(weights * control_lon))

        return lat, lon

    def pixel_to_gps(
        self,
        pixel_x: float,
        pixel_y: float,
        grid_data: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[float]]:
        """Convert a pixel coordinate to GPS using the geo-reference grid.

        Finds the nearest grid point and interpolates.

        Args:
            pixel_x: X pixel coordinate in mosaic.
            pixel_y: Y pixel coordinate in mosaic.
            grid_data: Grid data from generate_grid().

        Returns:
            Tuple of (latitude, longitude) or (None, None) if unavailable.
        """
        control_points = grid_data.get('control_points', [])
        if not control_points:
            return None, None

        cp_px = np.array([[cp['pixel_x'], cp['pixel_y']] for cp in control_points])
        cp_lat = np.array([cp['gps_latitude'] for cp in control_points])
        cp_lon = np.array([cp['gps_longitude'] for cp in control_points])

        lat, lon = self._interpolate_gps(pixel_x, pixel_y, cp_px, cp_lat, cp_lon)
        return lat, lon

    def compute_gps_rmse(
        self,
        grid_data: Dict[str, Any],
        validation_points: List[Dict[str, Any]]
    ) -> float:
        """Compute GPS RMSE against known validation points.

        Args:
            grid_data: Grid data from generate_grid().
            validation_points: List of {pixel_x, pixel_y, gps_latitude, gps_longitude}.

        Returns:
            RMSE in metres.
        """
        if not validation_points:
            return float('inf')

        errors_m = []
        for vp in validation_points:
            pred_lat, pred_lon = self.pixel_to_gps(
                vp['pixel_x'], vp['pixel_y'], grid_data
            )
            if pred_lat is None:
                continue

            # Approximate distance in metres (Haversine simplified for small distances)
            dlat = (pred_lat - vp['gps_latitude']) * 111320  # metres per degree lat
            dlon = (pred_lon - vp['gps_longitude']) * 111320 * np.cos(np.radians(vp['gps_latitude']))
            error_m = np.sqrt(dlat ** 2 + dlon ** 2)
            errors_m.append(error_m)

        if not errors_m:
            return float('inf')

        rmse = float(np.sqrt(np.mean(np.array(errors_m) ** 2)))
        passed = rmse < self.gps_rmse_target

        status = "PASSED" if passed else "FAILED"
        logger.info(
            f"GPS RMSE {status}: {rmse:.3f}m (target < {self.gps_rmse_target}m, "
            f"n={len(errors_m)} validation points)"
        )

        return rmse

    def save_grid(
        self,
        grid_data: Dict[str, Any],
        output_path: str
    ) -> str:
        """Save geo-reference grid to JSON file.

        Args:
            grid_data: Grid data from generate_grid().
            output_path: Output JSON file path.

        Returns:
            Path to saved file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(grid_data, f, indent=2)

        logger.info(f"Geo-reference grid saved to {output_path}")
        return str(output_path)

    def _empty_grid(self, mosaic_shape: Tuple[int, int]) -> Dict[str, Any]:
        """Return an empty grid structure for cases with no control points."""
        return {
            'mosaic_width_px': int(mosaic_shape[1]),
            'mosaic_height_px': int(mosaic_shape[0]),
            'grid_spacing_px': self.grid_spacing_px,
            'num_control_points': 0,
            'num_grid_points': 0,
            'control_points': [],
            'grid_points': [],
            'coordinate_system': 'WGS84 (EPSG:4326)',
            'interpolation_method': 'inverse_distance_weighted',
            'warning': 'Insufficient control points for geo-referencing'
        }
