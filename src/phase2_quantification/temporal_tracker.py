"""
temporal_tracker.py — Multi-Cycle Temporal Defect Tracking Module
==================================================================

Enables change detection and growth monitoring between successive facade inspection cycles:
  - Mosaic alignment via SIFT + RANSAC homography.
  - Pixel-wise change mask computation via Gaussian-smoothed differences.
  - IoU-based defect tracking across inspection cycles (propagated vs. new vs. resolved).
  - Growth rate profiling: length/width/area delta and mm/month growth rates.
  - Color-coded change visualization overlay.

References:
  - [R17] Xu et al. (2022) Automated Structural Change Detection in Multitemporal UAV Imagery.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def compute_bbox_iou(box1: List[int], box2: List[int]) -> float:
    """Calculate the Intersection over Union (IoU) of two bounding boxes.

    Parameters
    ----------
    box1 : list of int
        Bounding box [x, y, width, height] in pixels.
    box2 : list of int
        Bounding box [x, y, width, height] in pixels.

    Returns
    -------
    float
        IoU score between 0.0 and 1.0.
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    
    # Intersection coordinates
    ix1 = max(x1, x2)
    iy1 = max(y1, y2)
    ix2 = min(x1 + w1, x2 + w2)
    iy2 = min(y1 + h1, y2 + h2)
    
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    
    intersection = iw * ih
    union = (w1 * h1) + (w2 * h2) - intersection
    
    if union <= 0:
        return 0.0
    return float(intersection / union)


class TemporalTracker:
    """Tracks defect growth and identifies new defect candidates across flight cycles.

    Parameters
    ----------
    config : dict
        Pipeline configuration dict (specifically uses 'temporal' parameters).
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        
        # Load parameters with safe defaults
        temp_cfg = config.get("temporal", {})
        self.gaussian_sigma = temp_cfg.get("gaussian_sigma", 2.0)
        self.iou_propagated = temp_cfg.get("iou_propagated_threshold", 0.3)
        self.iou_new = temp_cfg.get("iou_new_threshold", 0.1)
        self.registration_max_error = temp_cfg.get("registration_max_error_px", 3.0)
        self.morph_opening_kernel = temp_cfg.get("morph_opening_kernel", 3)
        
        logger.info("TemporalTracker initialized.")

    def register_mosaics(
        self,
        mosaic1: np.ndarray,
        mosaic2: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """Align Cycle 2 mosaic to Cycle 1 coordinate space using SIFT and Homography.

        Parameters
        ----------
        mosaic1 : np.ndarray
            Cycle 1 mosaic image (BGR).
        mosaic2 : np.ndarray
            Cycle 2 mosaic image (BGR) to align.

        Returns
        -------
        H : np.ndarray
            3x3 homography matrix. Defaults to Identity if matching fails.
        registration_error : float
            Root-mean-square registration error in pixels.
        """
        # Convert to grayscale
        g2 = cv2.cvtColor(mosaic2, cv2.COLOR_BGR2GRAY) if mosaic2.ndim == 3 else mosaic2
        
        # Check cache for mosaic1 features to avoid redundant SIFT extraction on the reference facade
        import hashlib
        ref_hash = hashlib.sha256(mosaic1.tobytes()).hexdigest()
        if hasattr(self, "_cached_ref_hash") and self._cached_ref_hash == ref_hash:
            kp1, des1 = self._cached_kp1, self._cached_des1
            logger.info("Retrieved reference mosaic SIFT features from cache.")
        else:
            g1 = cv2.cvtColor(mosaic1, cv2.COLOR_BGR2GRAY) if mosaic1.ndim == 3 else mosaic1
            sift = cv2.SIFT_create()
            h1, w1 = g1.shape[:2]
            max_dim = 1024
            if w1 > max_dim or h1 > max_dim:
                scale1 = max_dim / float(max(w1, h1))
                g1_small = cv2.resize(g1, (int(w1 * scale1), int(h1 * scale1)), interpolation=cv2.INTER_AREA)
                kp1_raw, des1 = sift.detectAndCompute(g1_small, None)
                
                kp1 = []
                inv_scale1 = 1.0 / scale1
                for kp in kp1_raw:
                    kp1.append(cv2.KeyPoint(kp.pt[0] * inv_scale1, kp.pt[1] * inv_scale1, kp.size * inv_scale1, kp.angle, kp.response, kp.octave, kp.class_id))
            else:
                kp1, des1 = sift.detectAndCompute(g1, None)
            
            # Cache reference features
            self._cached_ref_hash = ref_hash
            self._cached_kp1 = kp1
            self._cached_des1 = des1
            logger.info("Computed and cached SIFT features for reference mosaic.")
            
        h2, w2 = g2.shape[:2]
        sift = cv2.SIFT_create()
        if w2 > max_dim or h2 > max_dim:
            scale2 = max_dim / float(max(w2, h2))
            g2_small = cv2.resize(g2, (int(w2 * scale2), int(h2 * scale2)), interpolation=cv2.INTER_AREA)
            kp2_raw, des2 = sift.detectAndCompute(g2_small, None)
            
            kp2 = []
            inv_scale2 = 1.0 / scale2
            for kp in kp2_raw:
                kp2.append(cv2.KeyPoint(kp.pt[0] * inv_scale2, kp.pt[1] * inv_scale2, kp.size * inv_scale2, kp.angle, kp.response, kp.octave, kp.class_id))
        else:
            kp2, des2 = sift.detectAndCompute(g2, None)
        
        # Fallback if SIFT fails or has too few keypoints
        identity = np.eye(3, dtype=np.float32)
        if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
            logger.warning("Insufficient keypoints for homography. Using identity alignment.")
            return identity, 999.0
            
        # FLANN matching
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        try:
            matches = flann.knnMatch(des1, des2, k=2)
        except Exception as exc:
            logger.warning("FLANN matching failed: %s. Using identity.", str(exc))
            return identity, 999.0
            
        # Lowe's ratio test filter
        good_matches = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)
                
        if len(good_matches) < 8:
            logger.warning("Only %d good matches found. Identity alignment used.", len(good_matches))
            return identity, 999.0
            
        # Extract coordinates of good matches
        pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # Find homography aligning pts2 into pts1 coordinate frame
        H, mask = cv2.findHomography(pts2, pts1, cv2.USAC_MAGSAC, 3.0)
        
        if H is None:
            logger.warning("Homography estimation failed. Using identity alignment.")
            return identity, 999.0
            
        # Compute RMSE for the inlier matches
        inliers = mask.ravel() == 1
        if np.sum(inliers) >= 4:
            in_pts1 = pts1[inliers].squeeze()
            in_pts2 = pts2[inliers].squeeze()
            
            # Apply homography to pts2
            proj_pts2 = cv2.perspectiveTransform(in_pts2.reshape(-1, 1, 2), H).squeeze()
            
            # Compute distance
            errors = np.sqrt(np.sum((in_pts1 - proj_pts2) ** 2, axis=1))
            rmse = float(np.mean(errors))
            
            if rmse > self.registration_max_error:
                logger.warning("Registration RMSE (%.2f px) exceeds threshold (%.2f px).", rmse, self.registration_max_error)
        else:
            rmse = 999.0
            
        logger.info("Mosaics registered. SIFT matches=%d, Inliers=%d, RMSE=%.2f px", len(good_matches), np.sum(inliers), rmse)
        return H, rmse

    def detect_changes(
        self,
        mosaic1: np.ndarray,
        mosaic2: np.ndarray,
        H: np.ndarray,
    ) -> np.ndarray:
        """Align mosaic2 and find significant pixel intensity changes against mosaic1.

        Parameters
        ----------
        mosaic1 : np.ndarray
            Reference Cycle 1 mosaic.
        mosaic2 : np.ndarray
            Cycle 2 mosaic to align and check.
        H : np.ndarray
            3x3 Homography alignment matrix.

        Returns
        -------
        np.ndarray
            Binary change map (0 or 255) showing localized difference zones.
        """
        h, w = mosaic1.shape[:2]
        
        # Warp mosaic2
        warped2 = cv2.warpPerspective(mosaic2, H, (w, h))
        
        # Convert to grayscale
        g1 = cv2.cvtColor(mosaic1, cv2.COLOR_BGR2GRAY) if mosaic1.ndim == 3 else mosaic1
        g2 = cv2.cvtColor(warped2, cv2.COLOR_BGR2GRAY) if warped2.ndim == 3 else warped2
        
        # Absolute difference
        diff = cv2.absdiff(g1, g2)
        
        # Gaussian smoothing to reduce pixel noise
        k_size = int(2 * round(3 * self.gaussian_sigma) + 1)
        k_size = max(3, k_size | 1)  # Ensure odd and >= 3
        smoothed = cv2.GaussianBlur(diff, (k_size, k_size), self.gaussian_sigma)
        
        # Adaptive thresholding to extract high contrast change clusters
        _, binary = cv2.threshold(smoothed, 30, 255, cv2.THRESH_BINARY)
        
        # Morphological opening to clean up sparse noise
        elem_size = self.morph_opening_kernel
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (elem_size, elem_size))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        return cleaned

    def cluster_changes(self, change_map: np.ndarray) -> List[Dict[str, Any]]:
        """Group connected pixels in change map into discrete candidate change blocks.

        Parameters
        ----------
        change_map : np.ndarray
            Binary change map (0 or 255).

        Returns
        -------
        list of dict
            List of candidate change region records: { centroid_px, bbox_px, area_px }
        """
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(change_map)
        
        candidates = []
        for i in range(1, num_labels):  # Skip background index 0
            area = stats[i, cv2.CC_STAT_AREA]
            
            # Filter out tiny pixel clusters (less than 15 pixels)
            if area < 15:
                continue
                
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH])
            h = int(stats[i, cv2.CC_STAT_HEIGHT])
            cx, cy = centroids[i]
            
            candidates.append({
                "centroid_px": [int(cx), int(cy)],
                "bbox_px": [x, y, w, h],
                "area_px": int(area),
            })
            
        return candidates

    def match_defects(
        self,
        cycle1_defects: List[Dict[str, Any]],
        cycle2_defects: List[Dict[str, Any]],
        pipeline_warnings: List[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Track and match defects across inspection cycles using bounding-box IoUs.

        Classifies defects into:
          - 'propagated': defect in Cycle 2 matched to Cycle 1.
          - 'new': defect in Cycle 2 with no match in Cycle 1.
          - 'resolved': defect in Cycle 1 not seen in Cycle 2.

        Parameters
        ----------
        cycle1_defects : list of dict
            List of quantified defects in Cycle 1.
        cycle2_defects : list of dict
            List of quantified defects in Cycle 2.

        Returns
        -------
        list of dict
            List of Cycle 2 defects with temporal matching metadata added:
            { defect_id, type, ..., status ('new'/'propagated'), parent_defect_id }
        """
        results: List[Dict[str, Any]] = []
        
        matched_parent_ids = set()
        
        for d2 in cycle2_defects:
            d2_copy = d2.copy()
            bbox2 = d2_copy["bbox_px"]
            
            best_iou = 0.0
            best_parent_id = None
            best_parent_defect = None
            
            for d1 in cycle1_defects:
                bbox1 = d1["bbox_px"]
                iou = compute_bbox_iou(bbox1, bbox2)
                if iou > best_iou:
                    best_iou = iou
                    best_parent_id = d1.get("defect_id")
                    best_parent_defect = d1
                    
            if best_iou >= self.iou_propagated:
                d2_copy["temporal_status"] = "propagated"
                d2_copy["parent_defect_id"] = best_parent_id
                matched_parent_ids.add(best_parent_id)
                
                # Compute differences
                if best_parent_defect:
                    self.compute_deltas(d2_copy, best_parent_defect)
            elif best_iou < self.iou_new:
                d2_copy["temporal_status"] = "new"
                d2_copy["parent_defect_id"] = None
                d2_copy["delta_length_cm"] = 0.0
                d2_copy["delta_width_mm"] = 0.0
                d2_copy["delta_area_cm2"] = 0.0
                d2_copy["growth_rate_mm_per_month"] = 0.0
            else:
                d2_copy["temporal_status"] = "uncertain"
                d2_copy["parent_defect_id"] = best_parent_id
                
            d2_copy["crack_activity_status"] = classify_crack_activity(
                d2_copy.get("growth_rate_mm_per_month")
            )

            if d2_copy["crack_activity_status"] == "aggressive" and pipeline_warnings is not None:
                pipeline_warnings.append(
                    f"AGGRESSIVE CRACK DETECTED: {d2_copy['defect_id']} "
                    f"growth rate {d2_copy['growth_rate_mm_per_month']:.3f} mm/month — "
                    f"immediate structural review required"
                )

            results.append(d2_copy)
            
        logger.info(
            "Temporal tracking complete. Matched propagated defects=%d, Brand new defects=%d",
            sum(1 for d in results if d.get("temporal_status") == "propagated"),
            sum(1 for d in results if d.get("temporal_status") == "new")
        )
        return results

    def compute_deltas(self, current_defect: Dict[str, Any], parent_defect: Dict[str, Any]) -> None:
        """Calculate geometric changes and rates of change for matched defects.

        Assumes a standard 1-month difference between cycles unless configured otherwise.

        Parameters
        ----------
        current_defect : dict
            The current cycle (Cycle 2) defect dict. Modified in place.
        parent_defect : dict
            The parent cycle (Cycle 1) defect dict.
        """
        # Delta calculations
        d_len = current_defect.get("length_cm", 0.0) - parent_defect.get("length_cm", 0.0)
        d_w = current_defect.get("width_mm", 0.0) - parent_defect.get("width_mm", 0.0)
        d_area = current_defect.get("area_cm2", 0.0) - parent_defect.get("area_cm2", 0.0)
        
        current_defect["delta_length_cm"] = round(float(d_len), 3)
        current_defect["delta_width_mm"] = round(float(d_w), 3)
        current_defect["delta_area_cm2"] = round(float(d_area), 3)
        
        # Calculate rate of growth. Default: 1.0 month delta
        delta_months = 1.0
        # If dates are present, calculate exact delta in months
        # Let's say: rate = (width change in mm) / months
        growth_rate = max(0.0, d_w) / delta_months
        current_defect["growth_rate_mm_per_month"] = round(float(growth_rate), 3)

    def generate_change_map(
        self,
        mosaic1: np.ndarray,
        mosaic2: np.ndarray,
        matched_defects: List[Dict[str, Any]],
        H: np.ndarray,
    ) -> np.ndarray:
        """Generate a color-coded visual overlay showing defect progression.

        Delineation:
          - Green Bboxes: Propagated defects from Cycle 1 (shown on aligned canvas).
          - Red Bboxes: Brand new defects detected in Cycle 2.
          - Blue Bboxes: Uncertain or changing regions.

        Parameters
        ----------
        mosaic1 : np.ndarray
            Reference Cycle 1 mosaic (BGR).
        mosaic2 : np.ndarray
            Cycle 2 mosaic (BGR) to warp.
        matched_defects : list of dict
            Cycle 2 defects with 'temporal_status' keys.
        H : np.ndarray
            Alignment Homography matrix.

        Returns
        -------
        np.ndarray
            Overlay image (BGR) showing annotated alignment.
        """
        h, w = mosaic1.shape[:2]
        
        # Warp mosaic2 to align with mosaic1
        warped2 = cv2.warpPerspective(mosaic2, H, (w, h))
        
        # Create blending canvas
        overlay = warped2.copy()
        
        for d in matched_defects:
            status = d.get("temporal_status", "new")
            bbox = d.get("bbox_px", [0, 0, 0, 0])
            x, y, bw, bh = bbox
            
            if status == "propagated":
                # Propagated: draw green box
                color = (0, 255, 0)
                label = f"PROPAGATED ({d.get('defect_id')})"
            elif status == "new":
                # New: draw red box
                color = (0, 0, 255)
                label = f"NEW ({d.get('defect_id')})"
            else:
                # Uncertain: draw blue box
                color = (255, 0, 0)
                label = f"UNCERTAIN ({d.get('defect_id')})"
                
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), color, thickness=3)
            cv2.putText(
                overlay,
                label,
                (x, max(15, y - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                thickness=1,
                lineType=cv2.LINE_AA,
            )
            
        # Blend 70% aligned image, 30% annotations
        cv2.addWeighted(overlay, 0.8, warped2, 0.2, 0, overlay)
        return overlay

def classify_crack_activity(growth_rate_mm_per_month: float) -> str:
    """
    IS 13935 activity classification based on crack growth rate.
    """
    if growth_rate_mm_per_month is None:
        return "unmonitored"
    if growth_rate_mm_per_month < 0.01:
        return "dormant"
    if growth_rate_mm_per_month < 0.05:
        return "active"
    return "aggressive"
