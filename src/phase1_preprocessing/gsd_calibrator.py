"""
gsd_calibrator.py — Ground Sampling Distance (GSD) Calibration Module

Computes GSD (cm/px) from UAV flight parameters and validates against
reference objects. GSD is the fundamental scale factor converting pixel
measurements to real-world dimensions.

Formula:
    GSD = (Altitude_m × Sensor_Width_mm) / (Focal_Length_mm × Image_Width_px)
    Result in cm/px (multiply by 100 to convert from m/px)

References:
    [R3] Agüera-Vega et al. (2017) — GSD calibration accuracy analysis
    [R4] Nex & Remondino (2014) — UAV photogrammetry GSD formula derivation

Author: Saugata Malakar | IIT Kharagpur
Organisation: Cortex Construction Solutions Pvt. Ltd.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

import numpy as np
import yaml

logger = logging.getLogger(__name__)


# ===========================================================================
# Camera Profile Management
# ===========================================================================

def load_camera_profiles(profiles_path: str) -> Dict[str, Dict]:
    """Load camera sensor profiles from YAML configuration.

    Args:
        profiles_path: Path to camera_profiles.yaml.

    Returns:
        Dictionary of camera profiles keyed by profile name.
    """
    try:
        with open(profiles_path, 'r') as f:
            data = yaml.safe_load(f)
        profiles = data.get('profiles', {})
        logger.info(f"Loaded {len(profiles)} camera profiles from {profiles_path}")
        return profiles
    except Exception as e:
        logger.error(f"Failed to load camera profiles: {e}")
        return {}


def get_camera_profile(
    profiles: Dict[str, Dict],
    profile_name: Optional[str] = None,
    focal_length_mm: Optional[float] = None,
    sensor_width_mm: Optional[float] = None,
    image_width_px: Optional[int] = None
) -> Dict[str, Any]:
    """Get camera parameters, prioritising EXIF data over profiles.

    Priority: explicit parameters > named profile > default profile.

    Args:
        profiles: Loaded camera profiles dictionary.
        profile_name: Name of camera profile to use.
        focal_length_mm: Override focal length from EXIF.
        sensor_width_mm: Override sensor width from EXIF.
        image_width_px: Override image width from EXIF.

    Returns:
        Dictionary with resolved camera parameters.
    """
    # Start with named or default profile
    if profile_name and profile_name in profiles:
        params = dict(profiles[profile_name])
    elif 'dji_phantom_4_pro' in profiles:
        params = dict(profiles['dji_phantom_4_pro'])
        logger.info("Using default camera profile: dji_phantom_4_pro")
    else:
        params = {}

    # Override with explicit values (EXIF data takes priority)
    if focal_length_mm is not None:
        params['focal_length_mm'] = focal_length_mm
    if sensor_width_mm is not None:
        params['sensor_width_mm'] = sensor_width_mm
    if image_width_px is not None:
        params['image_width_px'] = image_width_px

    return params


# ===========================================================================
# GSD Computation
# ===========================================================================

def compute_gsd(
    altitude_m: float,
    sensor_width_mm: float,
    focal_length_mm: float,
    image_width_px: int,
    sensor_height_mm: Optional[float] = None,
    image_height_px: Optional[int] = None,
    use_worst_case: bool = True
) -> float:
    """Compute Ground Sampling Distance in cm/px.

    Calculates GSD for both width and height dimensions and returns the
    larger (worst-case) value for conservative measurements.

    Formula:
        GSD_w = (Altitude × Sensor_Width) / (Focal_Length × Image_Width)
        GSD_h = (Altitude × Sensor_Height) / (Focal_Length × Image_Height)
        Final = max(GSD_w, GSD_h) if use_worst_case else GSD_w

    Args:
        altitude_m: Flight altitude in metres (relative altitude preferred).
        sensor_width_mm: Physical sensor width in millimetres.
        focal_length_mm: Lens focal length in millimetres.
        image_width_px: Image width in pixels.
        sensor_height_mm: Physical sensor height in mm (optional).
        image_height_px: Image height in pixels (optional).
        use_worst_case: If True, returns the larger of width/height GSD.

    Returns:
        GSD in centimetres per pixel.

    Raises:
        ValueError: If any input parameter is zero or negative.
    """
    # Validate inputs
    if altitude_m <= 0:
        raise ValueError(f"Altitude must be positive: {altitude_m}m")
    if sensor_width_mm <= 0:
        raise ValueError(f"Sensor width must be positive: {sensor_width_mm}mm")
    if focal_length_mm <= 0:
        raise ValueError(f"Focal length must be positive: {focal_length_mm}mm")
    if image_width_px <= 0:
        raise ValueError(f"Image width must be positive: {image_width_px}px")

    # GSD width (metres/pixel → cm/pixel)
    gsd_w_m = (altitude_m * sensor_width_mm) / (focal_length_mm * image_width_px)
    gsd_w_cm = gsd_w_m * 100  # Convert to cm/px

    gsd_h_cm = None
    if use_worst_case and sensor_height_mm and image_height_px:
        if sensor_height_mm > 0 and image_height_px > 0:
            gsd_h_m = (altitude_m * sensor_height_mm) / (focal_length_mm * image_height_px)
            gsd_h_cm = gsd_h_m * 100

    if gsd_h_cm is not None:
        final_gsd = max(gsd_w_cm, gsd_h_cm)
        logger.info(
            f"GSD computed: width={gsd_w_cm:.4f} cm/px, height={gsd_h_cm:.4f} cm/px, "
            f"using={'worst-case' if final_gsd == gsd_h_cm else 'width'} = {final_gsd:.4f} cm/px"
        )
    else:
        final_gsd = gsd_w_cm
        logger.info(f"GSD computed: {final_gsd:.4f} cm/px (width-only)")

    return final_gsd


def compute_gsd_from_metadata(
    metadata: Dict[str, Any],
    camera_profiles: Optional[Dict] = None,
    profile_name: Optional[str] = None,
    use_relative_altitude: bool = True
) -> Optional[float]:
    """Compute GSD from image metadata dictionary.

    Resolves altitude (preferring relative over GPS altitude), camera
    parameters (preferring EXIF over profile), and computes GSD.

    Args:
        metadata: Dictionary with keys from ImageMetadata dataclass.
        camera_profiles: Loaded camera profiles (optional).
        profile_name: Camera profile name (optional).
        use_relative_altitude: Prefer relative altitude over GPS altitude.

    Returns:
        GSD in cm/px or None if parameters unavailable.
    """
    # Resolve altitude
    altitude = None
    if use_relative_altitude and metadata.get('relative_altitude') is not None:
        altitude = abs(float(metadata['relative_altitude']))
    elif metadata.get('gps_altitude') is not None:
        altitude = abs(float(metadata['gps_altitude']))
        logger.info("Using GPS altitude (sea-level) — may be less accurate than relative")

    if altitude is None or altitude <= 0:
        logger.warning("Cannot compute GSD: no valid altitude")
        return None

    # Resolve camera parameters
    params = get_camera_profile(
        camera_profiles or {},
        profile_name,
        metadata.get('focal_length_mm'),
        metadata.get('sensor_width_mm'),
        metadata.get('image_width_px')
    )

    focal_length = params.get('focal_length_mm')
    sensor_width = params.get('sensor_width_mm')
    image_width = params.get('image_width_px')

    if not all([focal_length, sensor_width, image_width]):
        missing = []
        if not focal_length:
            missing.append('focal_length_mm')
        if not sensor_width:
            missing.append('sensor_width_mm')
        if not image_width:
            missing.append('image_width_px')
        logger.warning(f"Cannot compute GSD: missing {', '.join(missing)}")
        return None

    return compute_gsd(
        altitude_m=altitude,
        sensor_width_mm=sensor_width,
        focal_length_mm=focal_length,
        image_width_px=image_width,
        sensor_height_mm=params.get('sensor_height_mm'),
        image_height_px=params.get('image_height_px')
    )


# ===========================================================================
# GSD Validation
# ===========================================================================

def validate_gsd_with_reference(
    image: 'np.ndarray',
    gsd_cm_per_px: float,
    reference_length_m: float,
    reference_pixel_length: float,
    tolerance_percent: float = 5.0
) -> Tuple[bool, float, float]:
    """Cross-validate GSD using a reference object of known length.

    Measures the pixel length of a known reference object (e.g., 1m survey
    rod) and compares the GSD-predicted length to the actual length.

    Args:
        image: Image containing the reference object (unused, for context).
        gsd_cm_per_px: Computed GSD in cm/px.
        reference_length_m: Known length of the reference object in metres.
        reference_pixel_length: Measured pixel length of the reference object.
        tolerance_percent: Maximum acceptable deviation (%).

    Returns:
        Tuple of (passed, predicted_length_cm, actual_length_cm).
    """
    reference_length_cm = reference_length_m * 100.0
    predicted_length_cm = reference_pixel_length * gsd_cm_per_px

    if reference_length_cm == 0:
        logger.error("Reference length is zero")
        return False, predicted_length_cm, reference_length_cm

    deviation_percent = abs(predicted_length_cm - reference_length_cm) / reference_length_cm * 100

    passed = deviation_percent <= tolerance_percent

    if passed:
        logger.info(
            f"GSD validation PASSED: predicted={predicted_length_cm:.2f}cm, "
            f"actual={reference_length_cm:.2f}cm, deviation={deviation_percent:.2f}%"
        )
    else:
        logger.warning(
            f"GSD validation FAILED: predicted={predicted_length_cm:.2f}cm, "
            f"actual={reference_length_cm:.2f}cm, deviation={deviation_percent:.2f}% "
            f"(> tolerance {tolerance_percent}%)"
        )

    return passed, predicted_length_cm, reference_length_cm


# ===========================================================================
# GSD Calibrator Class
# ===========================================================================

class GSDCalibrator:
    """Manages GSD computation and validation for a set of drone images.

    Computes per-image GSD values, aggregates to a median GSD for the flight,
    and optionally validates against a reference object.

    Args:
        config: Pipeline configuration dictionary.
        camera_profiles_path: Path to camera_profiles.yaml.

    Example:
        >>> calibrator = GSDCalibrator(config, "config/camera_profiles.yaml")
        >>> gsd = calibrator.calibrate_from_metadata(metadata_df)
    """

    def __init__(
        self,
        config: Optional[Dict] = None,
        camera_profiles_path: Optional[str] = None
    ):
        config = config or {}
        gsd_config = config.get('gsd', {})

        self.reference_length_m = gsd_config.get('reference_object_length_m', 1.0)
        self.tolerance_percent = gsd_config.get('gsd_tolerance_percent', 5.0)
        self.use_relative_altitude = gsd_config.get('use_relative_altitude', True)

        self.camera_profiles = {}
        if camera_profiles_path:
            self.camera_profiles = load_camera_profiles(camera_profiles_path)

    def calibrate_single(
        self,
        metadata: Dict[str, Any],
        profile_name: Optional[str] = None
    ) -> Optional[float]:
        """Compute GSD for a single image from its metadata.

        Args:
            metadata: Image metadata dictionary.
            profile_name: Camera profile name override.

        Returns:
            GSD in cm/px or None.
        """
        return compute_gsd_from_metadata(
            metadata, self.camera_profiles, profile_name,
            self.use_relative_altitude
        )

    def calibrate_flight(
        self,
        metadata_list: list,
        profile_name: Optional[str] = None
    ) -> Tuple[Optional[float], Dict[str, Any]]:
        """Compute median GSD across all images in a flight.

        Args:
            metadata_list: List of metadata dictionaries (one per image).
            profile_name: Camera profile name override.

        Returns:
            Tuple of (median_gsd_cm_per_px, stats_dict).
        """
        gsd_values = []
        for meta in metadata_list:
            gsd = self.calibrate_single(meta, profile_name)
            if gsd is not None:
                gsd_values.append(gsd)

        if not gsd_values:
            logger.warning("No valid GSD values computed for this flight")
            return None, {'count': 0}

        gsd_array = np.array(gsd_values)
        stats = {
            'count': len(gsd_values),
            'median_cm_per_px': float(np.median(gsd_array)),
            'mean_cm_per_px': float(np.mean(gsd_array)),
            'std_cm_per_px': float(np.std(gsd_array)),
            'min_cm_per_px': float(np.min(gsd_array)),
            'max_cm_per_px': float(np.max(gsd_array)),
        }

        logger.info(
            f"Flight GSD: median={stats['median_cm_per_px']:.4f} cm/px "
            f"(σ={stats['std_cm_per_px']:.4f}, n={stats['count']})"
        )

        return stats['median_cm_per_px'], stats

    def calculate_gsd(
        self,
        altitude_m: float,
        camera_profile: str = "dji_phantom_4_pro"
    ) -> float:
        """Calculate GSD for a specific altitude and camera profile name.

        Parameters
        ----------
        altitude_m : float
            Flight altitude in metres.
        camera_profile : str
            Camera profile name (e.g., 'dji_phantom_4_pro').

        Returns
        -------
        float
            Ground Sample Distance (GSD) in cm/px.
        """
        if not self.camera_profiles:
            # Resolve relative configuration path
            possible_paths = [
                Path("config/camera_profiles.yaml"),
                Path(__file__).parents[2] / "config" / "camera_profiles.yaml",
                Path(__file__).parent / "camera_profiles.yaml"
            ]
            for path in possible_paths:
                if path.exists():
                    self.camera_profiles = load_camera_profiles(str(path))
                    break

        params = get_camera_profile(self.camera_profiles, camera_profile)
        focal_length = params.get('focal_length_mm', 8.8)
        sensor_width = params.get('sensor_width_mm', 13.2)
        image_width = params.get('image_width_px', 5472)
        sensor_height = params.get('sensor_height_mm', 8.8)
        image_height = params.get('image_height_px', 3648)

        return compute_gsd(
            altitude_m=altitude_m,
            sensor_width_mm=sensor_width,
            focal_length_mm=focal_length,
            image_width_px=image_width,
            sensor_height_mm=sensor_height,
            image_height_px=image_height
        )

