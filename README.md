<p align="center">
  <strong>CORTEX STRUCTURAL DEFECT PIPELINE</strong>
</p>

<p align="center">
  <em>AI-Based Drone Image Processing, Web Visualizer &amp; Structural Defect Quantification Platform</em>
</p>

<!-- Badges -->
<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue?style=flat-square&logo=python" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/next.js-16.2-black?style=flat-square&logo=nextdotjs" alt="Next.js 16.2" />
  <img src="https://img.shields.io/badge/react-19.0-blue?style=flat-square&logo=react" alt="React 19.0" />
  <img src="https://img.shields.io/badge/fastapi-0.109-green?style=flat-square&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/opencv-4.9-5C3EE8?style=flat-square&logo=opencv" alt="OpenCV 4.9" />
  <img src="https://img.shields.io/badge/license-proprietary-red?style=flat-square" alt="License" />
</p>

<p align="center">
  <strong>Live Deployment:</strong> <a href="https://cortex-1-1.onrender.com" target="_blank">cortex-1-1.onrender.com</a>
</p>

---

## Overview

The **Cortex Structural Defect Pipeline & UI Platform** is an end-to-end industrial system for processing drone-captured imagery of civil infrastructure, detecting and quantifying structural defects (cracks, spalling, corrosion, delamination), and producing geo-referenced engineering reports. 

Featuring a modern dark-themed Next.js dashboard, a FastAPI backend server, and an SQLite database, it provides instant, interactive defect cataloging and structural health modeling.

---

## Technology Stack

The platform is split into a robust analytical backend and a responsive, data-rich frontend:

### Backend (Analytical Engine & APIs)
*   **Core Language**: Python 3.11
*   **Web Framework**: FastAPI (running on port `8000`)
*   **Computer Vision**: OpenCV (image enhancement via CLAHE, homography stitching, Canny edge detection, Hough Line Transforms)
*   **Machine Learning**: XGBoost (false-positive filter) + SHAP (explainable feature importance)
*   **Datastore**: SQLite (under `data/reports/defects.db`) with Write-Ahead Logging (WAL) enabled for high concurrent read/write performance
*   **Task Queue**: Celery (integrated with Redis for asynchronous flight-frame jobs)

### Frontend (Interactive Dashboard)
*   **Framework**: Next.js 16.2 (App Router with Turbopack compilation)
*   **UI Library**: React 19.0 (Hooks, Context Provider, forwardRef primitives)
*   **Styling**: Pure CSS + Tailwinds CSS (configured with a custom Dark Slate palette `#0A0B0F` and vibrant warning/yellow accents `#FFE600`)
*   **3D Sandbox**: Three.js WebGL rendering for 3D concrete rebar stress model visualizers
*   **Interactive Maps**: Leaflet.js for geo-referenced defect mappings

---

## Architecture

The system operates across five distinct processing phases:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 CORTEX PIPELINE & INTERACTIVE UI SYSTEM                     │
├──────────────┬──────────────┬──────────────────┬──────────────┬─────────────┤
│  PHASE 1     │  PHASE 2     │  PHASE 3         │  PHASE 4     │  PHASE 5    │
│  Preprocess  │  Quantify    │  Filter          │  Report      │  Rebar      │
│              │              │                  │              │  Exposure   │
│ ┌──────────┐ │ ┌──────────┐ │ ┌───────────────┐ │ ┌──────────┐ │ ┌─────────┐ │
│ │ Quality  │ │ │ Crack    │ │ │ XGBoost       │ │ │ PDF      │ │ │ Cover   │ │
│ │ Gate     │ │ │ Width    │ │ │ False-Positive│ │ │ Report   │ │ │ Depth   │ │
│ ├──────────┤ │ │ Depth    │ │ │ Reduction     │ │ ├──────────┤ │ ├─────────┤ │
│ │ CLAHE    │ │ │ Length   │ │ ├───────────────┤ │ │ JSON     │ │ │ Spacing │ │
│ │ Enhance  │ │ ├──────────┤ │ │ SHAP          │ │ │ Schema   │ │ │ Dia     │ │
│ ├──────────┤ │ │ Spalling │ │ │ Explain-      │ │ └──────────┘ │ │ Loss    │ │
│ │ Stitch   │ │ │ Area     │ │ │ ability       │ │              │ └─────────┘ │
│ ├──────────┤ │ │ Vulner-  │ │ └───────────────┘ │              │             │
│ │ GSD      │ │ │ ability  │ │                   │              │             │
│ │ Calibrate│ │ │ Index    │ │                   │              │             │
│ └──────────┘ │ └──────────┘ │                   │              │             │
└──────────────┴──────────────┴──────────────────┴──────────────┴─────────────┘
```

---

## Core Calculations & Formulas

### 1. Ground Sampling Distance (GSD) Calibration
GSD is the scale factor converting visual pixel dimensions to physical metrics (centimeters per pixel, `cm/px`). The platform computes both vertical ($\text{GSD}_h$) and horizontal ($\text{GSD}_w$) values, selecting the **worst-case (larger) GSD** for conservative measurements:

$$\text{GSD}_w = \frac{\text{Altitude}_m \times \text{Sensor Width}_{mm}}{\text{Focal Length}_{mm} \times \text{Image Width}_{px}} \times 100 \quad [\text{cm/px}]$$

$$\text{GSD}_h = \frac{\text{Altitude}_m \times \text{Sensor Height}_{mm}}{\text{Focal Length}_{mm} \times \text{Image Height}_{px}} \times 100 \quad [\text{cm/px}]$$

$$\text{Final GSD} = \max(\text{GSD}_w, \text{GSD}_h)$$

*   **Altitude**: Vertical distance from the camera lens to the facade.
*   **Sensor Parameters**: Default sensor configurations loaded from `camera_profiles.yaml` (e.g., DJI Phantom 4 Pro sensor: $13.2\text{mm} \times 8.8\text{mm}$, $5472 \times 3648$ resolution, $8.8\text{mm}$ focal length).

**Metric Scalings:**
*   **Width (mm)**: $\text{Width (pixels)} \times \text{GSD (cm/px)} \times 10$
*   **Length (cm)**: $\text{Length (pixels)} \times \text{GSD (cm/px)}$
*   **Rebar Spacing (cm)**: $\text{Spacing (pixels)} \times \text{GSD (cm/px)}$

---

## Vulnerability Index (V-Index) Score
The V-Index evaluates structural risk based on damage severity, element category, and environmental exposures, aligned with Indian Standard **IS 13311** and **IS 13935** structural auditing guidelines.

#### Defect V-Index Contribution
Each defect $i$ contributes a vulnerability rating calculated by:

$$VI_{\text{defect}} = w_i \times s_i \times A_i \times R_{\text{subtype}} \times C_{\text{member}} \times E_{\text{exposure}}$$

Where:
*   **Defect Weight ($w_i$)**: Base weight coefficient (e.g. `crack` / `displacement` = $1.0$, `spalling` = $0.8$, `corrosion` = $0.6$, `seepage` = $0.5$, `efflorescence` = $0.3$).
*   **Severity Multiplier ($s_i$)**: Classifies crack widths (e.g., `wide` ($>5\text{mm}$) = $1.0$, `medium` ($1-5\text{mm}$) = $0.8$, `fine` ($0.2-1\text{mm}$) = $0.5$, `hairline` ($<0.2\text{mm}$) = $0.3$).
*   **Defect Area ($A_i$)**: Footprint area in $cm^2$.
*   **Subtype Risk ($R_{\text{subtype}}$)**: Multiplier for structural threat (e.g. `shear` = $2.5$, `corrosion_induced` = $2.0$, `settlement` = $1.8$, `flexural` = $1.0$, `shrinkage_crazing` = $0.8$).
*   **Member Criticality ($C_{\text{member}}$)**: Structural load-path importance (e.g. `column` = $3.0$, `beam` = $2.0$, `slab` = $1.0$, `wall` = $0.5$).
*   **Exposure Multiplier ($E_{\text{exposure}}$)**: `extreme`/`coastal`/`severe` environment = $1.5$, `normal` = $1.0$.

#### Facade-Level Composite V-Index
To determine the composite Vulnerability Index for the entire facade (capped at $100.0$):

$$VI_{\text{facade}} = \left( \frac{\sum_{i=1}^{n} VI_{\text{defect}_i}}{A_{\text{facade}}} \right) \times 100.0$$

*Where $A_{\text{facade}}$ is the total facade surface area in square centimeters ($cm^2$).*

---

## Hardening Improvements

*   **WAL Mode SQLite Engine**: Enabled Write-Ahead Logging (WAL), foreign keys, and `synchronous=NORMAL` connection event listeners in `sqlite_store.py` to prevent database locks during multi-user uploads.
*   **DB Retry Decorator**: Applied exponential backoff retry loops on database session operations to handle locking issues gracefully.
*   **SIFT Hash-based Cache**: Swapped SIFT descriptor caching to key on SHA-256 file contents instead of filenames, preventing collision bugs when processing separate images sharing names.
*   **Bounded Parallel Workers**: Capped parallel thread pool executors to CPU cores minus one (`max(1, CPU-1)`) to avoid execution gridlocks on target VM machines.
*   **Synchronous Direct Save API**: Created a direct intercept in the POST `/api/inspections` endpoint, enabling manual form entries in the frontend to write instantly and update catalog listings in real-time.

---

## Installation & Setup

### Prerequisites
*   Python 3.11+
*   Node.js 18+ & npm 9+

### Backend Setup
```bash
# Initialize venv and install dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Start backend server
python run_frontend.py --no-browser
```

### Frontend Setup
```bash
# Navigate to frontend and install dependencies
cd frontend
npm install

# Run development server
npm run dev
# OR compile a production build
npm run build
```

---

## License

> **Confidential** — Cortex Construction Solutions Pvt. Ltd.  
> All rights reserved. Unauthorized copying, distribution, or modification of this software is strictly prohibited.
