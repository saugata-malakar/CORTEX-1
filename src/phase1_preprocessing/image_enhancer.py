"""
image_enhancer.py — Image Enhancement & Perspective Correction Module

Multi-step enhancement pipeline preserving structural edge fidelity:
  1. CLAHE on L-channel in LAB colour space
  2. Gaussian denoising (edge-preserving)
  3. White balance correction (gray-world assumption)
  4. Post-enhancement quality validation
  5. Perspective correction via vanishing point detection + homography

References:
    [R4] Nex & Remondino (2014) — UAV imagery enhancement challenges
    [R5] Hartley & Zisserman (2004) — Homography and perspective geometry

Author: Saugata Malakar | IIT Kharagpur
Organisation: Cortex Construction Solutions Pvt. Ltd.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ===========================================================================
# CLAHE Enhancement
# ===========================================================================

def apply_clahe(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_size: Tuple[int, int] = (8, 8)
) -> np.ndarray:
    """Apply CLAHE on the L-channel in LAB colour space.

    Improves shadow detail without over-exposing sunlit areas — critical for
    facade images with mixed lighting conditions.

    Args:
        image: BGR input image (uint8).
        clip_limit: CLAHE contrast limiting threshold.
        tile_size: Grid size for local histogram equalisation.

    Returns:
        Enhanced BGR image (uint8).
    """
    if image is None or image.size == 0:
        raise ValueError("Input image is empty or None")

    # Convert to LAB colour space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    # Apply CLAHE to L-channel only
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
    l_enhanced = clahe.apply(l_channel)

    # Merge back and convert to BGR
    lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
    result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

    logger.debug(
        f"CLAHE applied: clip_limit={clip_limit}, tile_size={tile_size}, "
        f"L-channel mean {l_channel.mean():.1f} → {l_enhanced.mean():.1f}"
    )
    return result


# ===========================================================================
# Gaussian Denoising
# ===========================================================================

def apply_gaussian_denoise(
    image: np.ndarray,
    kernel_size: Tuple[int, int] = (5, 5),
    sigma: float = 1.0
) -> np.ndarray:
    """Apply Gaussian denoising preserving edge structure.

    Suppresses sensor noise while maintaining structural edges critical for
    crack detection. Uses a modest kernel to avoid blurring fine crack details.

    Args:
        image: BGR input image (uint8).
        kernel_size: Gaussian kernel dimensions (must be odd).
        sigma: Gaussian standard deviation.

    Returns:
        Denoised BGR image (uint8).
    """
    # Ensure kernel dimensions are odd
    kw = kernel_size[0] if kernel_size[0] % 2 == 1 else kernel_size[0] + 1
    kh = kernel_size[1] if kernel_size[1] % 2 == 1 else kernel_size[1] + 1

    result = cv2.GaussianBlur(image, (kw, kh), sigma)

    logger.debug(f"Gaussian denoise applied: kernel=({kw},{kh}), σ={sigma}")
    return result


# ===========================================================================
# White Balance Correction
# ===========================================================================

def apply_white_balance(image: np.ndarray) -> np.ndarray:
    """Apply white balance correction using the gray-world assumption.

    Assumes the average colour of the scene should be neutral gray. Corrects
    colour casts from variable skylight / artificial lighting on facades.

    Args:
        image: BGR input image (uint8).

    Returns:
        White-balanced BGR image (uint8).
    """
    # Compute per-channel means
    b_mean, g_mean, r_mean = cv2.mean(image)[:3]
    overall_mean = (b_mean + g_mean + r_mean) / 3.0

    # Avoid division by zero
    if b_mean == 0 or g_mean == 0 or r_mean == 0:
        logger.warning("White balance skipped: zero-mean channel detected")
        return image

    # Scale factors
    b_scale = overall_mean / b_mean
    g_scale = overall_mean / g_mean
    r_scale = overall_mean / r_mean

    # Apply scaling
    result = image.astype(np.float64)
    result[:, :, 0] *= b_scale
    result[:, :, 1] *= g_scale
    result[:, :, 2] *= r_scale

    result = np.clip(result, 0, 255).astype(np.uint8)

    logger.debug(
        f"White balance: scale factors B={b_scale:.3f}, G={g_scale:.3f}, R={r_scale:.3f}"
    )
    return result


# ===========================================================================
# Quality Validation
# ===========================================================================

def validate_sharpness(
    image: np.ndarray,
    min_laplacian_variance: float = 100.0
) -> Tuple[bool, float]:
    """Validate image sharpness after enhancement.

    Args:
        image: BGR or grayscale image.
        min_laplacian_variance: Minimum acceptable Laplacian variance.

    Returns:
        Tuple of (passed: bool, laplacian_variance: float).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    passed = lap_var >= min_laplacian_variance

    if not passed:
        logger.warning(
            f"Sharpness validation FAILED: Laplacian variance {lap_var:.1f} < {min_laplacian_variance}"
        )
    return passed, lap_var


# ===========================================================================
# Perspective Correction — Vanishing Point Detection
# ===========================================================================

def detect_vanishing_points(
    image: np.ndarray,
    hough_rho: int = 1,
    hough_theta_degrees: float = 1.0,
    hough_threshold: int = 100,
    hough_min_line_length: int = 100,
    hough_max_line_gap: int = 10
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], List[np.ndarray]]:
    """Detect dominant vanishing points from line segments using HoughLinesP.

    Clusters detected lines by orientation to identify horizontal and vertical
    vanishing points. Essential for facade rectification.

    Args:
        image: BGR input image.
        hough_rho: Distance resolution in pixels.
        hough_theta_degrees: Angle resolution in degrees.
        hough_threshold: Accumulator threshold.
        hough_min_line_length: Minimum line segment length.
        hough_max_line_gap: Maximum gap between line segments.

    Returns:
        Tuple of (vertical_vp, horizontal_vp, detected_lines) where vp is
        (x, y) in image coordinates or None if not detected.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    edges = cv2.Canny(gray, 50, 150)

    theta = np.deg2rad(hough_theta_degrees)
    lines = cv2.HoughLinesP(
        edges, hough_rho, theta, hough_threshold,
        minLineLength=hough_min_line_length,
        maxLineGap=hough_max_line_gap
    )

    if lines is None or len(lines) == 0:
        logger.warning("No lines detected for vanishing point estimation")
        return None, None, []

    # Classify lines as near-vertical (±30° from vertical) or near-horizontal
    vertical_lines = []
    horizontal_lines = []

    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = x2 - x1
        dy = y2 - y1
        angle = np.degrees(np.arctan2(abs(dy), abs(dx)))

        if angle > 60:  # Near-vertical
            vertical_lines.append(line[0])
        elif angle < 30:  # Near-horizontal
            horizontal_lines.append(line[0])

    vertical_vp = _compute_vanishing_point(vertical_lines) if len(vertical_lines) >= 2 else None
    horizontal_vp = _compute_vanishing_point(horizontal_lines) if len(horizontal_lines) >= 2 else None

    logger.info(
        f"Lines detected: {len(lines)} total, "
        f"{len(vertical_lines)} vertical, {len(horizontal_lines)} horizontal"
    )

    return vertical_vp, horizontal_vp, [l[0] for l in lines]


def _compute_vanishing_point(lines: List[np.ndarray]) -> Optional[np.ndarray]:
    """Compute vanishing point as least-squares intersection of line segments.

    Args:
        lines: List of line segments [[x1, y1, x2, y2], ...].

    Returns:
        Vanishing point as np.array([x, y]) or None.
    """
    if len(lines) < 2:
        return None

    # Build system: each line contributes one equation
    # Line through (x1,y1)-(x2,y2): a*x + b*y + c = 0
    # where a = y2-y1, b = x1-x2, c = x2*y1 - x1*y2
    A = []
    for x1, y1, x2, y2 in lines:
        a = y2 - y1
        b = x1 - x2
        c = x2 * y1 - x1 * y2
        norm = np.sqrt(a * a + b * b)
        if norm > 0:
            A.append([a / norm, b / norm, c / norm])

    if len(A) < 2:
        return None

    A = np.array(A)

    # SVD solution: point that minimises sum of squared distances to all lines
    try:
        _, _, Vt = np.linalg.svd(A)
        vp_homogeneous = Vt[-1]
        if abs(vp_homogeneous[2]) < 1e-10:
            return None
        vp = vp_homogeneous[:2] / vp_homogeneous[2]
        return vp.astype(np.float64)
    except np.linalg.LinAlgError:
        return None


# ===========================================================================
# Perspective Rectification
# ===========================================================================

def compute_rectification_homography(
    image: np.ndarray,
    vertical_vp: Optional[np.ndarray] = None,
    horizontal_vp: Optional[np.ndarray] = None,
    gcp_points: Optional[List[Tuple[float, float]]] = None,
    gcp_targets: Optional[List[Tuple[float, float]]] = None
) -> Optional[np.ndarray]:
    """Compute rectification homography for facade images.

    Two modes:
    1. Vanishing-point based: projects vanishing points to infinity to
       make vertical/horizontal lines parallel.
    2. GCP-based: four-point homography using ground control points for
       metric accuracy (< 0.1° residual tilt).

    Args:
        image: BGR input image.
        vertical_vp: Vertical vanishing point (x, y) or None.
        horizontal_vp: Horizontal vanishing point (x, y) or None.
        gcp_points: Source GCP pixel coordinates [(x,y), ...] (4 points).
        gcp_targets: Target GCP coordinates [(x,y), ...] (4 points).

    Returns:
        3×3 homography matrix or None if rectification not possible.
    """
    h, w = image.shape[:2]

    # Mode 1: GCP-based (higher accuracy)
    if gcp_points is not None and gcp_targets is not None:
        if len(gcp_points) >= 4 and len(gcp_targets) >= 4:
            src = np.float32(gcp_points[:4])
            dst = np.float32(gcp_targets[:4])
            H = cv2.getPerspectiveTransform(src, dst)
            logger.info("Computed GCP-based rectification homography (4-point)")
            return H

    # Mode 2: Vanishing-point based
    if vertical_vp is None:
        logger.warning("Cannot compute rectification: no vertical vanishing point")
        return None

    # Construct homography that maps vertical VP to point at infinity [0, 1, 0]
    # This makes vertical lines in the scene parallel in the rectified image
    vp = np.array([vertical_vp[0], vertical_vp[1], 1.0])

    # Simple affine rectification: map VP to infinity via a projective transform
    # H = [[1, 0, 0], [0, 1, 0], [l1, l2, l3]]
    # where line at infinity l passes through VP
    cx, cy = w / 2.0, h / 2.0
    l1 = (vp[1] - cy) / ((vp[0] - cx) ** 2 + (vp[1] - cy) ** 2 + 1e-10)
    l2 = -(vp[0] - cx) / ((vp[0] - cx) ** 2 + (vp[1] - cy) ** 2 + 1e-10)

    H = np.eye(3, dtype=np.float64)
    H[2, 0] = l1 * 0.001  # Scale down for stability
    H[2, 1] = l2 * 0.001

    logger.info(f"Computed VP-based rectification homography (VP at {vertical_vp})")
    return H


def apply_perspective_correction(
    image: np.ndarray,
    H: np.ndarray,
    output_size: Optional[Tuple[int, int]] = None
) -> np.ndarray:
    """Apply perspective correction using a homography matrix.

    Args:
        image: BGR input image.
        H: 3×3 homography matrix from compute_rectification_homography().
        output_size: Optional (width, height) of output. Defaults to input size.

    Returns:
        Rectified BGR image.
    """
    h, w = image.shape[:2]
    if output_size is None:
        output_size = (w, h)

    rectified = cv2.warpPerspective(
        image, H, output_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0)
    )

    logger.debug(f"Perspective correction applied: output size {output_size}")
    return rectified


def validate_rectification(
    rectified_image: np.ndarray,
    tolerance_degrees: float = 0.5,
    hough_threshold: int = 80,
    hough_min_line_length: int = 80
) -> Tuple[bool, float]:
    """Validate that vertical lines are parallel after rectification.

    Measures the angular deviation of detected near-vertical lines from
    true vertical (90°). Target: < 0.5° mean deviation.

    Args:
        rectified_image: Rectified BGR image.
        tolerance_degrees: Maximum acceptable mean angle deviation.
        hough_threshold: HoughLinesP accumulator threshold.
        hough_min_line_length: Minimum line segment length.

    Returns:
        Tuple of (passed: bool, mean_deviation_degrees: float).
    """
    gray = cv2.cvtColor(rectified_image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, hough_threshold,
        minLineLength=hough_min_line_length,
        maxLineGap=10
    )

    if lines is None or len(lines) == 0:
        logger.warning("No lines detected for rectification validation")
        return False, float('inf')

    # Measure deviation from true vertical (90°)
    deviations = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = x2 - x1
        dy = y2 - y1
        angle_from_horizontal = np.degrees(np.arctan2(abs(dy), abs(dx)))

        # Only consider near-vertical lines (>60° from horizontal)
        if angle_from_horizontal > 60:
            deviation = abs(90.0 - angle_from_horizontal)
            deviations.append(deviation)

    if not deviations:
        logger.warning("No vertical lines found for validation")
        return False, float('inf')

    mean_deviation = float(np.mean(deviations))
    passed = mean_deviation < tolerance_degrees

    if passed:
        logger.info(
            f"Rectification validated: mean deviation = {mean_deviation:.3f}° "
            f"(< {tolerance_degrees}°)"
        )
    else:
        logger.warning(
            f"Rectification validation FAILED: mean deviation = {mean_deviation:.3f}° "
            f"(>= {tolerance_degrees}°)"
        )

    return passed, mean_deviation


# ===========================================================================
# Integrated Enhancement Pipeline
# ===========================================================================

class ImageEnhancer:
    """Complete image enhancement and perspective correction pipeline.

    Orchestrates: CLAHE → Denoise → White Balance → Quality Check →
    Perspective Detection → Rectification → Validation.

    Args:
        config: Dictionary of enhancement and perspective_correction parameters.

    Example:
        >>> enhancer = ImageEnhancer(config)
        >>> result = enhancer.enhance(image)
        >>> if result['quality_passed']:
        ...     rectified = result['enhanced_image']
    """

    def __init__(self, config: Optional[Dict] = None):
        config = config or {}
        enh = config.get('enhancement', {})
        pc = config.get('perspective_correction', {})

        # Enhancement parameters
        self.clahe_clip_limit = enh.get('clahe_clip_limit', 2.0)
        self.clahe_tile_size = tuple(enh.get('clahe_tile_size', [8, 8]))
        self.gaussian_kernel = tuple(enh.get('gaussian_kernel_size', [5, 5]))
        self.gaussian_sigma = enh.get('gaussian_sigma', 1.0)
        self.post_enhance_laplacian_min = enh.get('post_enhance_laplacian_min', 5.0)

        # Perspective correction parameters
        self.hough_rho = pc.get('hough_rho', 1)
        self.hough_theta = pc.get('hough_theta_degrees', 1.0)
        self.hough_threshold = pc.get('hough_threshold', 100)
        self.hough_min_line = pc.get('hough_min_line_length', 100)
        self.hough_max_gap = pc.get('hough_max_line_gap', 10)
        self.parallelism_tolerance = pc.get('parallelism_tolerance_degrees', 0.5)

    def enhance(
        self,
        image: np.ndarray,
        apply_rectification: bool = True,
        gcp_points: Optional[List] = None,
        gcp_targets: Optional[List] = None
    ) -> Dict[str, Any]:
        """Run the full enhancement pipeline on a single image.

        Args:
            image: BGR input image (uint8).
            apply_rectification: Whether to attempt perspective correction.
            gcp_points: Optional GCP source coordinates for rectification.
            gcp_targets: Optional GCP target coordinates for rectification.

        Returns:
            Dictionary with:
                - enhanced_image: Final processed image (np.ndarray)
                - quality_passed: bool
                - laplacian_variance: float
                - rectification_applied: bool
                - rectification_deviation: float (degrees)
                - warnings: list of warning strings
        """
        result = {
            'enhanced_image': None,
            'quality_passed': True,
            'laplacian_variance': 0.0,
            'rectification_applied': False,
            'rectification_deviation': float('inf'),
            'warnings': [],
            'steps_applied': []
        }

        current = image.copy()

        # Step 1: CLAHE
        try:
            current = apply_clahe(current, self.clahe_clip_limit, self.clahe_tile_size)
            result['steps_applied'].append('clahe')
        except Exception as e:
            result['warnings'].append(f"CLAHE failed: {e}")
            logger.error(f"CLAHE failed: {e}")

        # Step 2: Gaussian denoise
        try:
            current = apply_gaussian_denoise(current, self.gaussian_kernel, self.gaussian_sigma)
            result['steps_applied'].append('gaussian_denoise')
        except Exception as e:
            result['warnings'].append(f"Denoising failed: {e}")
            logger.error(f"Denoising failed: {e}")

        # Step 3: White balance
        try:
            current = apply_white_balance(current)
            result['steps_applied'].append('white_balance')
        except Exception as e:
            result['warnings'].append(f"White balance failed: {e}")
            logger.error(f"White balance failed: {e}")

        # Step 4: Quality validation
        passed, lap_var = validate_sharpness(current, self.post_enhance_laplacian_min)
        result['laplacian_variance'] = lap_var
        if not passed:
            result['quality_passed'] = False
            result['warnings'].append(
                f"Post-enhancement sharpness check failed (Laplacian={lap_var:.1f})"
            )

        # Step 5: Perspective correction (optional)
        if apply_rectification:
            try:
                vert_vp, horiz_vp, lines = detect_vanishing_points(
                    current,
                    self.hough_rho, self.hough_theta, self.hough_threshold,
                    self.hough_min_line, self.hough_max_gap
                )

                H = compute_rectification_homography(
                    current, vert_vp, horiz_vp, gcp_points, gcp_targets
                )

                if H is not None:
                    rectified = apply_perspective_correction(current, H)
                    rect_passed, deviation = validate_rectification(
                        rectified, self.parallelism_tolerance
                    )

                    result['rectification_deviation'] = deviation

                    if rect_passed:
                        current = rectified
                        result['rectification_applied'] = True
                        result['steps_applied'].append('perspective_correction')
                    else:
                        result['warnings'].append(
                            f"Rectification rejected: deviation {deviation:.2f}° "
                            f"> tolerance {self.parallelism_tolerance}°"
                        )
                else:
                    result['warnings'].append("No homography computed — rectification skipped")

            except Exception as e:
                result['warnings'].append(f"Perspective correction failed: {e}")
                logger.error(f"Perspective correction failed: {e}")

        result['enhanced_image'] = current
        return result

    def enhance_batch(
        self,
        images: List[np.ndarray],
        apply_rectification: bool = True
    ) -> List[Dict[str, Any]]:
        """Run enhancement pipeline on a batch of images.

        Args:
            images: List of BGR images.
            apply_rectification: Whether to attempt perspective correction.

        Returns:
            List of result dictionaries (one per image).
        """
        results = []
        for i, img in enumerate(images):
            logger.info(f"Enhancing image {i + 1}/{len(images)}")
            result = self.enhance(img, apply_rectification)
            results.append(result)

        passed = sum(1 for r in results if r['quality_passed'])
        logger.info(f"Batch enhancement complete: {passed}/{len(images)} passed quality check")
        return results

    def save_enhanced(
        self,
        image: np.ndarray,
        output_path: str,
        quality: int = 95
    ) -> str:
        """Save enhanced image to disk.

        Args:
            image: Enhanced BGR image.
            output_path: Output file path.
            quality: JPEG quality (1-100) or PNG compression.

        Returns:
            Path to saved file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ext = output_path.suffix.lower()
        if ext in ('.jpg', '.jpeg'):
            cv2.imwrite(str(output_path), image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        elif ext == '.png':
            compression = max(0, min(9, (100 - quality) // 10))
            cv2.imwrite(str(output_path), image, [cv2.IMWRITE_PNG_COMPRESSION, compression])
        else:
            cv2.imwrite(str(output_path), image)

        logger.debug(f"Enhanced image saved to {output_path}")
        return str(output_path)
