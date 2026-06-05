# Edge Case Documentation — Cortex Structural Inspection Pipeline

This document compiles the known failure modes, extreme operational conditions, and environmental anomalies that the Cortex pipeline may encounter, along with the expected vs. actual behaviors and built-in mitigations.

---

## 1. Large Facade Mosaics (> 30,000 px)

High-resolution camera sensors on modern inspection drones can produce stitched mosaics exceeding $30,000\text{ px}$ in width or height, which would cause Out-Of-Memory (OOM) errors during feature extraction or PDF reporting.

* **Expected Behavior**: The system should ingest the full mosaic, process every defect in its original pixel coordinates, and render them in the PDF report.
* **Actual Behavior / Mitigation**:
  * **Memory Guard**: During mosaic ingestion in `ImageProcessor.stitch_facades`, if the estimated dimension exceeds `max_mosaic_dimension` (default: $50,000\text{ px}$), the image is dynamically downsampled for SIFT processing. Coordinate transformations are scaled back to the original resolution to retain physical precision.
  * **Reporting Guard**: In `PDFReportGenerator._generate_annotated_mosaic`, if the mosaic exceeds $1024\text{ px}$, it is downscaled to $512\text{ px}$ for annotation drawing. This keeps the resulting PDF file size small (under 5MB) and generation time under 5 seconds, preventing ReportLab from running out of heap space.

---

## 2. Nighttime & Low-Contrast Imagery

Inspections conducted in poor lighting, at dusk, or under overcast conditions yield low-contrast images where defects (especially hairline cracks) are visually indistinguishable from shadows.

* **Expected Behavior**: The pipeline should enhance contrast to identify cracks or gracefully reject images that are too dark.
* **Actual Behavior / Mitigation**:
  * **Intensity Quality Gate**: `MetadataParser.apply_quality_gates` rejects any frame with a mean pixel intensity of less than 30 (on a 0-255 scale) before stitching, preventing low-quality inputs from corrupting the mosaic.
  * **Histogram Equalization**: `ImageEnhancer.enhance` applies Contrast-Limited Adaptive Histogram Equalization (CLAHE) on the L-channel in the LAB color space. This enhances localized contrast, making thin cracks stand out from the concrete background without amplifying noise.

---

## 3. Partially Occluded Facades (Vegetation, Scaffolding, Pipes)

Real-world building facades are frequently occluded by trees, scaffolding, wiring, or external drainage pipes, which can cause false-positive detections.

* **Expected Behavior**: The pipeline should identify and segment defects without being confused by regular metal poles or organic foliage textures.
* **Actual Behavior / Mitigation**:
  * **Multi-Modal Filtering**: The primary YOLO/segmentation model (Cortex API) might output candidate bounding boxes around scaffolding poles or tree branches. However, the secondary **XGBoost False Positive Filter** extracts:
    * **Edge sharpness**: regular metal poles have very sharp, straight edges, whereas cracks are irregular.
    * **LBP & GLCM texture**: leaves have high-frequency isotropic texture, distinct from concrete cracks.
    * **Shape metrics**: elongation ratio (joints have a ratio of 2–4; cracks are >5; leaf clusters are near 1).
  * This secondary classifier filters out these non-defects, achieving a Precision > 0.90.

---

## 4. Multi-Storey Buildings (Varying Flight Altitudes)

Inspecting a tall tower requires the drone to fly at multiple vertical tiers, resulting in varying distances to the facade and different focal lengths/altitudes.

* **Expected Behavior**: Physical dimensions of defects (length in cm, width in mm) must remain accurate regardless of whether the image was captured at the top floor or the ground floor.
* **Actual Behavior / Mitigation**:
  * **Dynamic GSD Calibration**: Rather than applying a single global GSD, `GSDCalibrator` reads the `RelativeAltitude` metadata from the EXIF of each individual drone frame. Bounding box coordinates and mask pixels are mapped to physical dimensions using the frame-specific GSD calculated at that specific altitude tier.

---

## 5. SIFT Match Gate Failures (Low Overlap / Uniform Textures)

Stitching requires at least 30% overlap and a minimum number of SIFT keypoints. Uniform glass facades or concrete walls with no features may fail to register SIFT points, breaking the homography chain.

* **Expected Behavior**: The pipeline should not crash if stitching fails, but should still deliver an inspection report.
* **Actual Behavior / Mitigation**:
  * **Per-Image Fallback**: If `ImageProcessor.stitch_facades` fails to stitch the sequence or keypoint counts are insufficient, the orchestrator catches the exception and automatically falls back to **per-image processing**. The first enhanced frame is treated as the primary facade canvas, and defects are quantified and reported individually, guaranteeing a completed PDF.

---

## 6. Cortex Detection API Schema Changes

Mid-project API schema modifications by the upstream Cortex detection service can break downstream quantification engines.

* **Expected Behavior**: The pipeline should decouple its data ingestion validation from direct vendor schema dependencies.
* **Actual Behavior / Mitigation**:
  * **Versioned Adapter**: The `CortexAdapter` wraps vendor API responses and parses base64-PNG and COCO-style Run-Length Encoded (RLE) binary masks.
  * **Pinned Schema Contract**: The adapter validates structures using a strict, flat schema config contract. If vendor structures change, only the adapter requires updates (completed within 1 day), keeping the core quantification engines untouched.

---

## 7. Manual Measurement Ground Truth Unavailable

Obtaining precise physical manual measurements of facade defects for accuracy validations is highly unsafe and often impossible.

* **Expected Behavior**: The platform must verify the pixel-to-metric length, width, and area measurement accuracy of the quantifier engines.
* **Actual Behavior / Mitigation**:
  * **Synthetic Calibration Testing**: The test suite uses synthetic calibration images generated via OpenCV drawing APIs. Crack lines of mathematically predetermined lengths (e.g. 15.2 cm) and widths (e.g. 1.2 mm) are drawn on clean canvases, allowing unit tests to assert measurement tolerances within a strict 2% accuracy bound.

---

## 8. Data Privacy Concerns with Real Building Images

Publishing raw building facades and real-world geographical coordinates in inspection reports can trigger privacy and security complaints.

* **Expected Behavior**: The system must inspect structural integrity without exposing sensitive identity or owner coordinates.
* **Actual Behavior / Mitigation**:
  * **Anonymised Data Schema**: The final JSON database and PDF manual contain only anonymised Building IDs. No personal information or identifiable owner fields are registered.
  * **Synthetic Fallback Mode**: For client presentations or public demonstrations where real data cannot be shared, the pipeline can run entirely on synthetic test datasets.
