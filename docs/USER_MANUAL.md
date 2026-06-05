# Cortex Structural Intelligence Platform — User Manual

This manual explains how to install, configure, and operate the Cortex AI-Based Drone Image Processing & Structural Defect Quantification Pipeline.

---

## 1. Overview

The Cortex Platform is a monolithic pipeline designed to process raw aerial facade images captured by inspection drones, automatically enhance and stitch them into visual mosaics, measure physical defect geometries (lengths, widths, and areas), filter false-positives using machine learning, and compile client-ready inspection reports in JSON and PDF formats.

---

## 2. Installation & Prerequisites

The platform is built on Python 3.12 and relies on standard open-source libraries for computer vision and PDF rendering.

### 2.1 Dependencies Installation
Install all required libraries pinned in the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

*Note: If a GPU is present, PyTorch will automatically run ResNet-50 feature extraction on CUDA. Otherwise, it falls back to CPU execution (inference time < 50ms per defect).*

---

## 3. Operations & Command Line Interface

You can execute the entire pipeline with a single command.

### 3.1 Running the Master Pipeline
Run the master orchestrator using the main entry point:
```bash
python -m src.pipeline --config config/pipeline_config.yaml --input data/raw --output data/reports
```

*   `--config`: Path to the master YAML configuration file containing tuneable tolerances.
*   `--input`: Directory containing raw JPEG/JPG drone images.
*   `--output`: Destination directory for the generated analytical stores.

### 3.2 Automation via Makefile
For developer convenience, standard commands are wrapped in the `Makefile`:
*   **Run Pipeline**: `make run`
*   **Run Test Suite**: `make test`
*   **Clean Temporary Outputs**: `make clean`

---

## 4. Input Requirements

To achieve accurate physical measurements and geotagging:
1.  **Format**: Drone images must be saved as JPEGs (`.jpg` or `.jpeg`).
2.  **EXIF tags**: The images must contain the following EXIF headers:
    *   `GPSLatitude` and `GPSLongitude` for georeferencing.
    *   `GPSAltitude` (specifically `RelativeAltitude` tags used by DJI) for altitude-relative GSD calibration.
    *   `FocalLength` and camera sensor properties (sensor width/height) to resolve pixels to metric units.
3.  **Overlap**: Adjacent drone frames should have at least **30% overlap** for successful SIFT keypoint matching and homography registration.

---

## 5. Understanding the Pipeline Outputs

Every successful pipeline run produces two final outputs in the specified output directory:

### 5.1 Hierarchical JSON Data Store (`inspection_results.json`)
A four-level JSON database conforming strictly to the Draft-07 schema:
1.  **Building**: GPS centroid, inspection date, cycle number, and aggregate vulnerability indices.
2.  **Facade**: Orientation, total area in $m^2$, and overall VI score.
3.  **Zone**: 4x4 spatial grid cells (A1–D4) with localized defect counts and dominant defect categories.
4.  **Defect Instance**: Physical properties (length in cm, width in mm, area in $cm^2$), GPS centroid, pixel location on mosaic, and classification (including false-positive filtering confidence).

### 5.2 Client-Ready PDF Report (`structural_inspection_report.pdf`)
A print-ready automated diagnostic report compiled via ReportLab Platypus:
*   **Cover Page**: Summarizes the building ID, scan date, and overall condition band.
*   **Executive Summary**: Contains global defect inventory statistics, facade VI tables, multi-cycle comparisons, and critical risk flags.
*   **Facade Details**: Detail pages for each facade, incorporating annotated mosaics and color-coded zone heatmaps.
*   **Temporal Comparison**: Progression charts tracking change rates and new defect lists between flight cycles.
*   **Recommendations**: Actionable remediation steps with priority levels and handwriting sign-off lines.
