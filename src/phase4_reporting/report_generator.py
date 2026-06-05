"""
report_generator.py — Client-Ready PDF Report Generation Module
===============================================================

Generates professional, structural-intelligence PDF reports using ReportLab's
PLATYPUS engine based on hierarchical building JSON data stores (JSON-first pattern).
Provides:
  - Gorgeous typography, customized table grids, and color-coded severity badges.
  - ``NumberedCanvas``: Dynamic two-pass page numbering ("Page X of Y") with consistent
    running headers/footers (suppressed on the cover page).
  - High-performance, in-memory PDF compilation.

References:
  - ReportLab PDF Library User Guide.
  - IS 13311-aligned structural classifications.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
)
from reportlab.pdfgen import canvas

import cv2
import numpy as np

INTERVENTION_BY_SEVERITY = {
    "hairline": "Surface Sealer",
    "fine":     "V-Groove Routing",
    "medium":   "Epoxy Injection",
    "wide":     "Structural Jacketing"
}

REINSPECTION_DAYS = {
    "hairline": 365,
    "fine":     180,
    "medium":   90,
    "wide":     30
}
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from .severity_classifier import classify_vi_score
from .frame_visualizer import generate_2d_building_frame

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Two-Pass Canvas for Page Numbering and Corporate Branding
# ------------------------------------------------------------------

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page counts.

    Draws consistent, clean running headers/footers with 'Page X of Y' numbering
    on all pages except the cover page.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#7F8C8D"))
        
        # Margins & coordinates for A4: 595.27 x 841.89 points
        margin_left = 36
        margin_right = 559
        header_y = 800
        footer_y = 45
        
        # 1. Draw Running Header
        self.setStrokeColor(colors.HexColor("#BDC3C7"))
        self.setLineWidth(0.5)
        self.line(margin_left, header_y - 4, margin_right, header_y - 4)
        self.drawString(margin_left, header_y, "CORTEX STRUCTURAL PLATFORM — CIVIL ENGINEERING PLATFORM")
        
        # 2. Draw Running Footer
        self.line(margin_left, footer_y + 12, margin_right, footer_y + 12)
        self.drawString(margin_left, footer_y, "CONFIDENTIAL — INTERNAL TECHNICAL SCANNING REPORT")
        
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(margin_right, footer_y, page_str)
        self.restoreState()


# ------------------------------------------------------------------
# Structural Diagrams Generators
# ------------------------------------------------------------------

def generate_blueprint_image(data: Dict[str, Any]) -> Image:
    """Generate a 2D blueprint X-ray visualization based on member properties."""
    fig, ax = plt.subplots(figsize=(6, 5), facecolor='#0B1D3A')
    ax.set_facecolor('#0B1D3A')
    ax.grid(True, color='#1A365D', linestyle='--', linewidth=0.8)
    
    member_type = data.get("member_type", "slab").lower()
    rebar_spacing = data.get("rebar_spacing_cm", 20.0)
    crack_width = data.get("width_mm", 0.5)
    crack_len = data.get("length_cm", 15.0)
    angle = data.get("orientation_angle", 45.0)
    
    if member_type == "beam":
        rect = plt.Rectangle((10, 30), 80, 40, fill=True, facecolor='#163854', edgecolor='#FFFFFF', linewidth=2, alpha=0.6)
        ax.add_patch(rect)
        x_rebars = np.arange(15, 90, rebar_spacing)
        for rx in x_rebars:
            ax.plot([rx, rx], [30, 70], color='#A5D8FF', linestyle='-', linewidth=1.5, alpha=0.8)
        ax.plot([10, 90], [33, 33], color='#E0EAF5', linestyle='-', linewidth=2.0, alpha=0.9)
        ax.plot([10, 90], [67, 67], color='#E0EAF5', linestyle='-', linewidth=2.0, alpha=0.9)
        cx_base, cy_base = 50, 50
    elif member_type == "column":
        rect = plt.Rectangle((30, 10), 40, 80, fill=True, facecolor='#163854', edgecolor='#FFFFFF', linewidth=2, alpha=0.6)
        ax.add_patch(rect)
        y_rebars = np.arange(15, 90, rebar_spacing)
        for ry in y_rebars:
            ax.plot([30, 70], [ry, ry], color='#A5D8FF', linestyle='-', linewidth=1.5, alpha=0.8)
        ax.plot([33, 33], [10, 90], color='#E0EAF5', linestyle='-', linewidth=2.0, alpha=0.9)
        ax.plot([67, 67], [10, 90], color='#E0EAF5', linestyle='-', linewidth=2.0, alpha=0.9)
        cx_base, cy_base = 50, 50
    else: # Slab
        rect = plt.Rectangle((10, 10), 80, 80, fill=True, facecolor='#163854', edgecolor='#FFFFFF', linewidth=2, alpha=0.6)
        ax.add_patch(rect)
        x_rebars = np.arange(15, 90, rebar_spacing)
        y_rebars = np.arange(15, 90, rebar_spacing)
        for rx in x_rebars:
            ax.plot([rx, rx], [10, 90], color='#A5D8FF', linestyle='-', linewidth=1.2, alpha=0.7)
        for ry in y_rebars:
            ax.plot([10, 90], [ry, ry], color='#A5D8FF', linestyle='-', linewidth=1.2, alpha=0.7)
        cx_base, cy_base = 50, 50
        
    rad = np.deg2rad(angle)
    scaled_len = min(30.0, crack_len)
    dx = (scaled_len / 2.0) * np.sin(rad)
    dy = (scaled_len / 2.0) * np.cos(rad)
    
    cx_pts = np.linspace(cx_base - dx, cx_base + dx, 10)
    cy_pts = np.linspace(cy_base - dy, cy_base + dy, 10)
    noise = (np.random.rand(10) - 0.5) * 1.5
    cx_pts += noise * np.cos(rad)
    cy_pts -= noise * np.sin(rad)
    
    if member_type == "beam":
        cy_pts = np.clip(cy_pts, 32, 68)
    elif member_type == "column":
        cx_pts = np.clip(cx_pts, 32, 68)
    else:
        cx_pts = np.clip(cx_pts, 12, 88)
        cy_pts = np.clip(cy_pts, 12, 88)
        
    ax.plot(cx_pts, cy_pts, color='#FF5252', linestyle='-', linewidth=max(1.5, crack_width * 2), label='Crack/Defect', zorder=5)
    ax.scatter([cx_base], [cy_base], color='#FF5252', s=30, zorder=6)
    
    ax.text(50, 94, f"2D BLUEPRINT X-RAY: {member_type.upper()}", color='#FFFFFF', fontsize=12, fontweight='bold', ha='center')
    
    infotext = (
        f"MEMBER TYPE: {member_type.upper()}\n"
        f"REBAR SPACING (s): {rebar_spacing:.1f} cm\n"
        f"CRACK MAX WIDTH: {crack_width:.2f} mm\n"
        f"CRACK LENGTH: {crack_len:.1f} cm\n"
        f"ANGLE FROM VERTICAL: {angle:.1f}°"
    )
    props = dict(boxstyle='round,pad=0.5', facecolor='#0D2C54', edgecolor='#1F4E5B', alpha=0.85)
    ax.text(5, 5, infotext, color='#5EC4E2', fontsize=8, fontfamily='monospace', bbox=props, zorder=10, va='bottom', ha='left')
    
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xticks([])
    ax.set_yticks([])
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=250, height=210)

def generate_3d_wireframe_image(data: Dict[str, Any]) -> Image:
    """Generate a 3D isometric wireframe visualization based on member properties."""
    fig = plt.figure(figsize=(6, 5), facecolor='#121214')
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor('#121214')
    
    member_type = data.get("member_type", "slab").lower()
    rebar_spacing = data.get("rebar_spacing_cm", 20.0)
    crack_width = data.get("width_mm", 0.5)
    crack_len = data.get("length_cm", 15.0)
    angle = data.get("orientation_angle", 45.0)
    
    if member_type == "beam":
        x_dim, y_dim, z_dim = 12.0, 4.0, 4.0
        edges = [
            ((0,0,0),(x_dim,0,0)), ((x_dim,0,0),(x_dim,y_dim,0)), ((x_dim,y_dim,0),(0,y_dim,0)), ((0,y_dim,0),(0,0,0)),
            ((0,0,z_dim),(x_dim,0,z_dim)), ((x_dim,0,z_dim),(x_dim,y_dim,z_dim)), ((x_dim,y_dim,z_dim),(0,y_dim,z_dim)), ((0,y_dim,z_dim),(0,0,z_dim)),
            ((0,0,0),(0,0,z_dim)), ((x_dim,0,0),(x_dim,0,z_dim)), ((x_dim,y_dim,0),(x_dim,y_dim,z_dim)), ((0,y_dim,0),(0,y_dim,z_dim))
        ]
        for ry in [0.6, y_dim - 0.6]:
            for rz in [0.6, z_dim - 0.6]:
                ax.plot3D([0, x_dim], [ry, ry], [rz, rz], color='#E67E22', linestyle='-', linewidth=2.0, alpha=0.7)
        step_x = max(1.5, (rebar_spacing / 10.0))
        for rx in np.arange(1.0, x_dim - 0.5, step_x):
            ax.plot3D([rx, rx, rx, rx, rx], [0.6, y_dim-0.6, y_dim-0.6, 0.6, 0.6], [0.6, 0.6, z_dim-0.6, z_dim-0.6, 0.6], 
                      color='#A5D8FF', linestyle='-', linewidth=1.2, alpha=0.6)
        rad = np.deg2rad(angle)
        scale_len = min(3.0, (crack_len / 100.0) * 8.0)
        dx = (scale_len / 2.0) * np.sin(rad)
        dz = (scale_len / 2.0) * np.cos(rad)
        cx = np.linspace(x_dim/2.0 - dx, x_dim/2.0 + dx, 20)
        cz = np.linspace(z_dim/2.0 - dz, z_dim/2.0 + dz, 20)
        cy = np.zeros_like(cx)
        noise = (np.random.rand(len(cx)) - 0.5) * 0.15
        cx += noise * np.cos(rad)
        cz -= noise * np.sin(rad)
        cx = np.clip(cx, 0.5, x_dim - 0.5)
        cz = np.clip(cz, 0.5, z_dim - 0.5)
        ax.plot3D(cx, cy, cz, color='#FF5252', linestyle='-', linewidth=3.0, zorder=10)
        ax.scatter3D([x_dim/2.0], [0], [z_dim/2.0], color='#FF5252', s=40, zorder=11)
        
    elif member_type == "column":
        x_dim, y_dim, z_dim = 4.0, 4.0, 12.0
        edges = [
            ((0,0,0),(x_dim,0,0)), ((x_dim,0,0),(x_dim,y_dim,0)), ((x_dim,y_dim,0),(0,y_dim,0)), ((0,y_dim,0),(0,0,0)),
            ((0,0,z_dim),(x_dim,0,z_dim)), ((x_dim,0,z_dim),(x_dim,y_dim,z_dim)), ((x_dim,y_dim,z_dim),(0,y_dim,z_dim)), ((0,y_dim,z_dim),(0,0,z_dim)),
            ((0,0,0),(0,0,z_dim)), ((x_dim,0,0),(x_dim,0,z_dim)), ((x_dim,y_dim,0),(x_dim,y_dim,z_dim)), ((0,y_dim,0),(0,y_dim,z_dim))
        ]
        for rx in [0.6, x_dim - 0.6]:
            for ry in [0.6, y_dim - 0.6]:
                ax.plot3D([rx, rx], [ry, ry], [0, z_dim], color='#E67E22', linestyle='-', linewidth=2.0, alpha=0.7)
        step_z = max(1.5, (rebar_spacing / 10.0))
        for rz in np.arange(1.0, z_dim - 0.5, step_z):
            ax.plot3D([0.6, x_dim-0.6, x_dim-0.6, 0.6, 0.6], [0.6, 0.6, y_dim-0.6, y_dim-0.6, 0.6], [rz, rz, rz, rz, rz], 
                      color='#A5D8FF', linestyle='-', linewidth=1.2, alpha=0.6)
        rad = np.deg2rad(angle)
        scale_len = min(3.0, (crack_len / 100.0) * 8.0)
        dx = (scale_len / 2.0) * np.sin(rad)
        dz = (scale_len / 2.0) * np.cos(rad)
        cx = np.linspace(x_dim/2.0 - dx, x_dim/2.0 + dx, 20)
        cz = np.linspace(z_dim/2.0 - dz, z_dim/2.0 + dz, 20)
        cy = np.zeros_like(cx)
        noise = (np.random.rand(len(cx)) - 0.5) * 0.15
        cx += noise * np.cos(rad)
        cz -= noise * np.sin(rad)
        cx = np.clip(cx, 0.5, x_dim - 0.5)
        cz = np.clip(cz, 0.5, z_dim - 0.5)
        ax.plot3D(cx, cy, cz, color='#FF5252', linestyle='-', linewidth=3.0, zorder=10)
        ax.scatter3D([x_dim/2.0], [0], [z_dim/2.0], color='#FF5252', s=40, zorder=11)
        
    else: # Slab
        x_dim, y_dim, z_dim = 10.0, 10.0, 2.5
        edges = [
            ((0,0,0),(x_dim,0,0)), ((x_dim,0,0),(x_dim,y_dim,0)), ((x_dim,y_dim,0),(0,y_dim,0)), ((0,y_dim,0),(0,0,0)),
            ((0,0,z_dim),(x_dim,0,z_dim)), ((x_dim,0,z_dim),(x_dim,y_dim,z_dim)), ((x_dim,y_dim,z_dim),(0,y_dim,z_dim)), ((0,y_dim,z_dim),(0,0,z_dim)),
            ((0,0,0),(0,0,z_dim)), ((x_dim,0,0),(x_dim,0,z_dim)), ((x_dim,y_dim,0),(x_dim,y_dim,z_dim)), ((0,y_dim,0),(0,y_dim,z_dim))
        ]
        step_mesh = max(1.5, (rebar_spacing / 10.0))
        for rx in np.arange(1.0, x_dim, step_mesh):
            ax.plot3D([rx, rx], [0, y_dim], [0.8, 0.8], color='#E67E22', linestyle='-', linewidth=1.5, alpha=0.6)
        for ry in np.arange(1.0, y_dim, step_mesh):
            ax.plot3D([0, x_dim], [ry, ry], [0.8, 0.8], color='#E67E22', linestyle='-', linewidth=1.5, alpha=0.6)
        rad = np.deg2rad(angle)
        scale_len = min(4.0, (crack_len / 100.0) * 8.0)
        dx = (scale_len / 2.0) * np.sin(rad)
        dy = (scale_len / 2.0) * np.cos(rad)
        cx = np.linspace(x_dim/2.0 - dx, x_dim/2.0 + dx, 20)
        cy = np.linspace(y_dim/2.0 - dy, y_dim/2.0 + dy, 20)
        cz = np.full_like(cx, z_dim)
        noise = (np.random.rand(len(cx)) - 0.5) * 0.2
        cx += noise * np.cos(rad)
        cy -= noise * np.sin(rad)
        cx = np.clip(cx, 0.5, x_dim - 0.5)
        cy = np.clip(cy, 0.5, y_dim - 0.5)
        ax.plot3D(cx, cy, cz, color='#FF5252', linestyle='-', linewidth=3.0, zorder=10)
        ax.scatter3D([x_dim/2.0], [y_dim/2.0], [z_dim], color='#FF5252', s=40, zorder=11)
        
    for s, e in edges:
        ax.plot3D(*zip(s, e), color='#7F8C8D', linestyle='-', linewidth=1.5, alpha=0.8)
        
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.view_init(elev=28, azim=40)
    ax.set_title("3D PERSPECTIVE WIREFRAME", color='#FFFFFF', fontsize=12, fontweight='bold', y=0.92)
    
    props = dict(boxstyle='round,pad=0.3', facecolor='#121214', edgecolor='#7F8C8D', alpha=0.6)
    fig.text(0.95, 0.05, f"PERSPECTIVE: ISO 3D WIREFRAME\nENVELOPE: {member_type.upper()}", 
             color='#7F8C8D', fontsize=8, fontfamily='monospace', ha='right', bbox=props)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=250, height=210)


# ------------------------------------------------------------------
# PDF Report Generator
# ------------------------------------------------------------------

class PDFReportGenerator:
    """Compiles analytical JSON data stores into print-ready PDF structural reports.

    Parameters
    ----------
    config : dict
        Pipeline master configuration dict (specifically uses 'reporting' parameters).
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        
        rep_cfg = config.get("reporting", {})
        self.font_family = rep_cfg.get("font_family", "Helvetica")
        self.company_name = rep_cfg.get("company_name", "Cortex Construction Solutions Pvt. Ltd.")
        self.use_in_memory = rep_cfg.get("use_in_memory_generation", True)
        self.timeout_sec = rep_cfg.get("report_generation_timeout_sec", 60)
        
        # Style Registry
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()
        
        logger.info("PDFReportGenerator initialized successfully.")

    def _init_custom_styles(self) -> None:
        """Register custom typography styles to enhance visual aesthetics."""
        primary_color = colors.HexColor("#1B365D")   # Corporate Deep Navy
        text_dark = colors.HexColor("#2C3E50")       # Dark Charcoal
        
        # Document Title
        self.styles.add(ParagraphStyle(
            name="DocTitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            textColor=primary_color,
            spaceAfter=15,
        ))
        
        # Section Heading 1
        self.styles.add(ParagraphStyle(
            name="SecHeading1",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=primary_color,
            spaceBefore=15,
            spaceAfter=10,
            keepWithNext=True,
        ))
        
        # Section Heading 2
        self.styles.add(ParagraphStyle(
            name="SecHeading2",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#D35400"),  # Amber Accent
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True,
        ))

        # Body Text Dark
        self.styles.add(ParagraphStyle(
            name="BodyDark",
            parent=self.styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=text_dark,
            spaceAfter=8,
        ))

        # Metadata Label
        self.styles.add(ParagraphStyle(
            name="MetaLabel",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=primary_color,
        ))

        # Metadata Value
        self.styles.add(ParagraphStyle(
            name="MetaValue",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            textColor=text_dark,
        ))

        # Badge Base Style
        self.styles.add(ParagraphStyle(
            name="BadgeStyle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=1,  # Centered
            textColor=colors.white,
        ))

    def _create_badge(self, text: str, bg_color_hex: str) -> Table:
        """Create a rounded-corner styled severity badge.

        Parameters
        ----------
        text : str
            Badge text label.
        bg_color_hex : str
            Background color code (HEX format).

        Returns
        -------
        Table
            A single-cell Table flowable representing the badge.
        """
        badge_para = Paragraph(text, self.styles["BadgeStyle"])
        t = Table([[badge_para]], colWidths=[100])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg_color_hex)),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(bg_color_hex)),
        ]))
        return t

    def _generate_annotated_mosaic(self, facade: Dict[str, Any], max_dim: int = 1024) -> Optional[Image]:
        """Generate a color-coded annotated mosaic image flowable.

        Parameters
        ----------
        facade : dict
            The facade dictionary with orientation and defect instances.
        max_dim : int
            Max width or height to prevent PDF bloating and OOM.

        Returns
        -------
        Image
            ReportLab Image flowable or None.
        """
        mosaic_path_str = facade.get("mosaic_path", "")
        if not mosaic_path_str:
            return None

        # Load image safely
        img = None
        if Path(mosaic_path_str).exists():
            try:
                img = cv2.imread(str(mosaic_path_str))
            except Exception as e:
                logger.warning(f"Failed to read image at {mosaic_path_str}: {e}")

        # Fallback to dummy canvas if image missing/failed
        if img is None:
            # Create a clean dark blue background representing facade placeholder
            img = np.zeros((600, 800, 3), dtype=np.uint8)
            img[:, :] = (93, 54, 27)  # #1B365D in BGR
            cv2.putText(img, f"FACADE MOSAIC: {facade.get('id')}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            cv2.putText(img, "RAW IMAGE UNAVAILABLE — SYNTHETIC CANVAS RENDERED", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        # Scale down if too large
        h, w = img.shape[:2]
        scale = 1.0
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        # Map severity class to colors (BGR)
        severity_colors = {
            "hairline": (113, 204, 46),   # Green (#2ECC71)
            "fine": (15, 196, 241),       # Yellow (#F1C40F)
            "medium": (34, 126, 230),     # Orange (#E67E22)
            "wide": (60, 76, 231)         # Red (#E74C3C)
        }

        # Draw defect centroids/centroids callouts
        defect_count = 0
        for z in facade.get("zones", []):
            for d in z.get("defects", []):
                if d.get("is_false_positive", False):
                    continue
                defect_count += 1
                cpx = d.get("centroid_px", {"x": 0, "y": 0})
                cx = int(cpx.get("x", 0) * scale)
                cy = int(cpx.get("y", 0) * scale)
                
                # Check bounds
                if 0 <= cx < img.shape[1] and 0 <= cy < img.shape[0]:
                    sev = d.get("severity_class", "hairline").lower()
                    color = severity_colors.get(sev, (113, 204, 46))
                    
                    # Draw visual target mark
                    cv2.circle(img, (cx, cy), int(8 * scale), color, -1)
                    cv2.circle(img, (cx, cy), int(15 * scale), color, 2)
                    
                    # Defect label
                    d_id = d.get("defect_id", "D")
                    cv2.putText(
                        img, d_id, (cx + int(18 * scale), cy + int(5 * scale)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45 * scale, color, 1, cv2.LINE_AA
                    )

        # Draw orientation watermarks
        cv2.putText(
            img, f"Orientation: {facade.get('orientation', 'N')}", (15, img.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA
        )

        # Encode to in-memory buffer
        success, encoded_img = cv2.imencode(".png", img)
        if not success:
            return None
        
        img_data = io.BytesIO(encoded_img.tobytes())
        # A4 margins allow width of 523pt. We set image width to 450pt to look nice.
        aspect_ratio = h / w
        return Image(img_data, width=450, height=450 * aspect_ratio)

    def _generate_zone_heatmap(self, facade: Dict[str, Any]) -> Image:
        """Create a 4x4 zone grid heatmap overlay showing local VI distribution.

        Parameters
        ----------
        facade : dict
            The facade dictionary with zones.

        Returns
        -------
        Image
            ReportLab Image flowable.
        """
        # Parse grid cells
        zones_data = facade.get("zones", [])
        zones_map = {z.get("grid_id", ""): z for z in zones_data}

        fig, ax = plt.subplots(figsize=(5.5, 4.5))
        ax.set_xlim(0, 4)
        ax.set_ylim(0, 4)
        ax.set_ylim(4, 0) # Row 1 at top

        # Set axis labels
        ax.set_xticks(np.arange(0.5, 4.5, 1))
        ax.set_xticklabels(["Col A", "Col B", "Col C", "Col D"])
        ax.set_yticks(np.arange(0.5, 4.5, 1))
        ax.set_yticklabels(["Row 1", "Row 2", "Row 3", "Row 4"])
        ax.xaxis.tick_top()
        ax.tick_params(top=False, bottom=False, left=False, right=False)

        # Draw grid cells
        for r in range(4):
            for c in range(4):
                col_letter = chr(ord("A") + c)
                row_num = str(r + 1)
                grid_id = f"{col_letter}{row_num}"
                zone = zones_map.get(grid_id, {})
                vi = zone.get("zone_vi", 0.0)
                count = zone.get("defect_count", 0)

                # Determine fill color based on IS 13311
                if vi <= 20:
                    bg_color = "#D4EFDF" # Light Green
                    text_color = "#1E8449"
                elif vi <= 40:
                    bg_color = "#FCF3CF" # Light Yellow
                    text_color = "#B7950B"
                elif vi <= 60:
                    bg_color = "#F5CBA7" # Light Orange
                    text_color = "#A04000"
                elif vi <= 80:
                    bg_color = "#FADBD8" # Light Red
                    text_color = "#943126"
                else:
                    bg_color = "#EBDEF0" # Light Purple
                    text_color = "#6C3483"

                rect = plt.Rectangle((c, r), 1, 1, facecolor=bg_color, edgecolor="#BDC3C7", linewidth=1)
                ax.add_patch(rect)

                # Label text
                label_text = f"{grid_id}\nVI: {vi:.1f}\n{count} Defect(s)"
                ax.text(
                    c + 0.5, r + 0.5, label_text,
                    color=text_color, fontsize=9, fontweight="bold",
                    ha="center", va="center"
                )

        ax.spines["top"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.title(f"Zone Vulnerability Index (VI) Heatmap — Facade {facade.get('id')}", fontsize=10, fontweight="bold", pad=20)
        plt.tight_layout()

        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        buf.seek(0)

        return Image(buf, width=320, height=260)

    def _generate_delta_vi_chart(self, building: Dict[str, Any], previous_building: Dict[str, Any]) -> Image:
        """Generate a bar chart comparing VI scores per facade orientation between cycles.

        Parameters
        ----------
        building : dict
            Current building record (Cycle 2).
        previous_building : dict
            Previous building record (Cycle 1).

        Returns
        -------
        Image
            ReportLab Image flowable.
        """
        orientations = []
        vi_c1 = []
        vi_c2 = []

        c1_facades = {f.get("orientation", "N"): f.get("vi_score", 0.0) for f in previous_building.get("facades", [])}
        c2_facades = {f.get("orientation", "N"): f.get("vi_score", 0.0) for f in building.get("facades", [])}

        # Collect unique orientations
        all_orientations = sorted(list(set(list(c1_facades.keys()) + list(c2_facades.keys()))))

        for orient in all_orientations:
            orientations.append(f"Facade {orient}")
            vi_c1.append(c1_facades.get(orient, 0.0))
            vi_c2.append(c2_facades.get(orient, 0.0))

        x = np.arange(len(orientations))
        width = 0.35

        fig, ax = plt.subplots(figsize=(6, 3.5))
        ax.bar(x - width/2, vi_c1, width, label=f"Cycle {previous_building.get('cycle_number', 1)} (Baseline)", color="#7F8C8D")
        ax.bar(x + width/2, vi_c2, width, label=f"Cycle {building.get('cycle_number', 2)} (Current)", color="#1B365D")

        ax.set_ylabel("Vulnerability Index (VI) Score")
        ax.set_title("Vulnerability Score (VI) Comparison per Facade", fontsize=10, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(orientations)
        ax.set_ylim(0, 100)
        ax.legend()
        ax.grid(axis='y', linestyle='--', alpha=0.5)

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        buf.seek(0)

        return Image(buf, width=380, height=220)

    def build_cover_page(self, building: Dict[str, Any], overall_vi: float) -> List[Any]:
        """Create the cover page flowables.

        Parameters
        ----------
        building : dict
            Top-level building record from JSON data.
        overall_vi : float
            Overall Vulnerability Index.

        Returns
        -------
        list
            List of cover page flowables.
        """
        flowables = []
        
        # Corporate Header
        flowables.append(Spacer(1, 40))
        flowables.append(Paragraph(self.company_name.upper(), self.styles["MetaLabel"]))
        flowables.append(Spacer(1, 10))
        
        # Colored Horizontal Bar
        bar = Table([[""]], colWidths=[523], rowHeights=[4])
        bar.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1B365D")),
        ]))
        flowables.append(bar)
        
        # Document Title
        flowables.append(Spacer(1, 60))
        flowables.append(Paragraph("STRUCTURAL PREVENTATIVE MAINTENANCE REPORT", self.styles["DocTitle"]))
        
        subtitle_style = ParagraphStyle(
            name="SubTitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#7F8C8D"),
            spaceAfter=30,
        )
        flowables.append(Paragraph("UAV FACADE SEGMENTATION & HEALTH SCORING PIPELINE", subtitle_style))
        flowables.append(Spacer(1, 40))
        
        # Health Summary Block (Table)
        vi_class_data = classify_vi_score(overall_vi)
        badge = self._create_badge(vi_class_data["label"], vi_class_data["color"])
        
        summary_data = [
            [Paragraph("BUILDING NAME", self.styles["MetaLabel"]), Paragraph(building.get("name", "N/A"), self.styles["MetaValue"])],
            [Paragraph("BUILDING ID", self.styles["MetaLabel"]), Paragraph(building.get("id", "N/A"), self.styles["MetaValue"])],
            [Paragraph("ADDRESS", self.styles["MetaLabel"]), Paragraph(building.get("address", "N/A"), self.styles["MetaValue"])],
            [Paragraph("DATE OF SCAN", self.styles["MetaLabel"]), Paragraph(building.get("inspection_date", "N/A"), self.styles["MetaValue"])],
            [Paragraph("INSPECTION CYCLE", self.styles["MetaLabel"]), Paragraph(f"Cycle {building.get('cycle_number', 1)}", self.styles["MetaValue"])],
            [Paragraph("OVERALL VI SCORE", self.styles["MetaLabel"]), Paragraph(f"{overall_vi:.2f} / 100.0", self.styles["MetaValue"])],
            [Paragraph("CONDITION BAND", self.styles["MetaLabel"]), badge],
        ]
        
        summary_table = Table(summary_data, colWidths=[150, 373])
        summary_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
        ]))
        
        flowables.append(summary_table)
        flowables.append(Spacer(1, 30))
        
        # 2D Structural Grid Diagram
        try:
            frame_img = generate_2d_building_frame(stories=4, bays=3)
            flowables.append(frame_img)
            flowables.append(Spacer(1, 30))
        except Exception as e:
            logger.error(f"Failed to generate 2D frame: {e}")
        
        # System Footer
        version_style = ParagraphStyle(
            name="VersionText",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#95A5A6"),
        )
        flowables.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", version_style))
        flowables.append(Paragraph(f"Cortex Pipeline Engine Version {building.get('inspector_module_version', '1.0.0')}", version_style))
        
        flowables.append(PageBreak())
        return flowables

    def build_executive_summary(
        self,
        building: Dict[str, Any],
        overall_vi: float,
        previous_building: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """Create executive summary flowables."""
        flowables = []
        flowables.append(Paragraph("1. Executive Summary", self.styles["SecHeading1"]))
        
        desc = (
            "This report summarizes the diagnostic facade inspection completed via high-resolution "
            "UAV image acquisition and state-of-the-art structural computer vision quantification. "
            "Cracks, spalling, corrosion, and other defects have been parsed using Cortex's core "
            "detection model, filtered for false-positives using our customized XGBoost pattern analyzer, "
            "and metricized relative to physical dimensions via Ground Sampling Distance (GSD) calibration. "
            "Vulnerability scoring is computed and categorized based on IS 13311 standards."
        )
        flowables.append(Paragraph(desc, self.styles["BodyDark"]))
        flowables.append(Spacer(1, 10))
        
        # 1. Defect Inventory Summary Table
        flowables.append(Paragraph("Global Defect Statistics", self.styles["SecHeading2"]))
        
        # Calculate totals
        defect_counts: Dict[str, int] = {}
        facades = building.get("facades", [])
        for f in facades:
            for z in f.get("zones", []):
                for d in z.get("defects", []):
                    if not d.get("is_false_positive", False):
                        dtype = d.get("type", "crack")
                        defect_counts[dtype] = defect_counts.get(dtype, 0) + 1
                        
        total_defects = sum(defect_counts.values())
        
        inv_data = [
            [Paragraph("Defect Category", self.styles["MetaLabel"]), Paragraph("Active Instance Count", self.styles["MetaLabel"])]
        ]
        
        for dtype, count in sorted(defect_counts.items(), key=lambda x: x[1], reverse=True):
            inv_data.append([
                Paragraph(dtype.replace("_", " ").title(), self.styles["MetaValue"]),
                Paragraph(str(count), self.styles["MetaValue"])
            ])
            
        inv_data.append([
            Paragraph("TOTAL ACTIVE DEFECTS", self.styles["MetaLabel"]),
            Paragraph(str(total_defects), self.styles["MetaLabel"])
        ])
        
        inv_table = Table(inv_data, colWidths=[260, 263])
        inv_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECF0F1")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ]))
        flowables.append(inv_table)
        flowables.append(Spacer(1, 15))
        
        # 2. Facade Summary List
        flowables.append(Paragraph("Facade Vulnerability Scores", self.styles["SecHeading2"]))
        
        fac_data = [
            [
                Paragraph("Facade ID", self.styles["MetaLabel"]),
                Paragraph("Direction", self.styles["MetaLabel"]),
                Paragraph("Area (m2)", self.styles["MetaLabel"]),
                Paragraph("VI Score", self.styles["MetaLabel"]),
                Paragraph("Remediation Class", self.styles["MetaLabel"])
            ]
        ]
        
        for fac in facades:
            vi_class_data = classify_vi_score(fac.get("vi_score", 0.0))
            fac_data.append([
                Paragraph(fac.get("id", "N/A"), self.styles["MetaValue"]),
                Paragraph(fac.get("orientation", "N"), self.styles["MetaValue"]),
                Paragraph(f"{fac.get('area_m2', 0.0):.2f}", self.styles["MetaValue"]),
                Paragraph(f"{fac.get('vi_score', 0.0):.2f}", self.styles["MetaValue"]),
                Paragraph(vi_class_data["label"], self.styles["MetaValue"]),
            ])
            
        fac_table = Table(fac_data, colWidths=[100, 80, 90, 90, 163])
        fac_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B365D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ]))
        
        # Patch table style headers
        for col in range(5):
            fac_table.setStyle(TableStyle([
                ("TEXTCOLOR", (col, 0), (col, 0), colors.white)
            ]))
            
        flowables.append(fac_table)

        # 3. Cycle Comparison Table
        if previous_building:
            flowables.append(Spacer(1, 15))
            flowables.append(Paragraph("Inspection Cycle Comparison", self.styles["SecHeading2"]))
            
            c1_vi = max([fac.get("vi_score", 0.0) for fac in previous_building.get("facades", [])]) if previous_building.get("facades") else 0.0
            c2_vi = overall_vi
            delta_vi = c2_vi - c1_vi
            
            c1_defects_count = 0
            for fac in previous_building.get("facades", []):
                for z in fac.get("zones", []):
                    for d in z.get("defects", []):
                        if not d.get("is_false_positive", False):
                            c1_defects_count += 1
            
            c2_defects_count = total_defects
            
            comp_data = [
                [Paragraph("Metric", self.styles["MetaLabel"]), 
                 Paragraph(f"Cycle {previous_building.get('cycle_number', 1)} (Baseline)", self.styles["MetaLabel"]), 
                 Paragraph(f"Cycle {building.get('cycle_number', 2)} (Current)", self.styles["MetaLabel"]),
                 Paragraph("Delta", self.styles["MetaLabel"])],
                
                [Paragraph("Max Vulnerability Index", self.styles["MetaValue"]),
                 Paragraph(f"{c1_vi:.2f}", self.styles["MetaValue"]),
                 Paragraph(f"{c2_vi:.2f}", self.styles["MetaValue"]),
                 Paragraph(f"{delta_vi:+.2f}", self.styles["MetaValue"])],
                 
                [Paragraph("Total Active Defects", self.styles["MetaValue"]),
                 Paragraph(str(c1_defects_count), self.styles["MetaValue"]),
                 Paragraph(str(c2_defects_count), self.styles["MetaValue"]),
                 Paragraph(f"{c2_defects_count - c1_defects_count:+d}", self.styles["MetaValue"])],
            ]
            
            comp_table = Table(comp_data, colWidths=[200, 110, 110, 103])
            comp_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECF0F1")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ]))
            flowables.append(comp_table)

        # 4. Key Risk Flags & Structural Warnings
        risk_flags = []
        for f in facades:
            f_vi = f.get("vi_score", 0.0)
            if f_vi > 60.0:
                risk_flags.append(f"Facade {f.get('id')} ({f.get('orientation')}) has high overall VI score ({f_vi:.1f}), requiring urgent engineering review.")
            for z in f.get("zones", []):
                if z.get("zone_vi", 0.0) > 60.0:
                    risk_flags.append(f"Zone {z.get('grid_id')} on Facade {f.get('id')} has severe local vulnerability ({z.get('zone_vi'):.1f}).")
                for d in z.get("defects", []):
                    if not d.get("is_false_positive", False):
                        if d.get("severity_class", "").lower() == "wide" or d.get("width_mm", 0.0) > 5.0:
                            risk_flags.append(f"Critical Defect {d.get('defect_id')} on Facade {f.get('id')} has a wide crack width of {d.get('width_mm'):.1f}mm.")
                        if d.get("growth_rate_mm_per_month", 0.0) > 0.2:
                            risk_flags.append(f"High Growth Rate: Defect {d.get('defect_id')} is expanding rapidly at {d.get('growth_rate_mm_per_month'):.2f} mm/month.")

        if risk_flags:
            flowables.append(Spacer(1, 15))
            flowables.append(Paragraph("Key Risk Flags & Structural Warnings", self.styles["SecHeading2"]))
            
            risk_cells = []
            for flag in risk_flags[:4]:  # Cap to top 4 key risks to avoid page overflow
                risk_cells.append([Paragraph(f"• <b>WARNING:</b> {flag}", self.styles["BodyDark"])])
            
            risk_table = Table(risk_cells, colWidths=[523])
            risk_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDEDEC")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#EC7063")),
            ]))
            flowables.append(risk_table)
            
        flowables.append(PageBreak())
        return flowables

    def build_facade_pages(self, building: Dict[str, Any]) -> List[Any]:
        """Create detail pages for each inspected facade."""
        flowables = []
        
        facades = building.get("facades", [])
        for idx, fac in enumerate(facades):
            flowables.append(Paragraph(f"2.{idx+1} Facade Details — {fac.get('id')}", self.styles["SecHeading1"]))
            
            # Metadata block
            vi_class_data = classify_vi_score(fac.get("vi_score", 0.0))
            badge = self._create_badge(vi_class_data["label"], vi_class_data["color"])
            
            fac_meta = [
                [Paragraph("Orientation", self.styles["MetaLabel"]), Paragraph(fac.get("orientation", "N"), self.styles["MetaValue"]),
                 Paragraph("Total Area", self.styles["MetaLabel"]), Paragraph(f"{fac.get('area_m2', 0.0):.2f} m2", self.styles["MetaValue"])],
                [Paragraph("VI Score", self.styles["MetaLabel"]), Paragraph(f"{fac.get('vi_score', 0.0):.2f} / 100.0", self.styles["MetaValue"]),
                 Paragraph("Remediation Class", self.styles["MetaLabel"]), badge]
            ]
            
            meta_table = Table(fac_meta, colWidths=[100, 160, 100, 163])
            meta_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#ECF0F1")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
            ]))
            flowables.append(meta_table)
            flowables.append(Spacer(1, 15))
            
            # List of defects
            flowables.append(Paragraph("Defect Instance Inventory", self.styles["SecHeading2"]))
            
            defect_list = []
            for z in fac.get("zones", []):
                for d in z.get("defects", []):
                    if not d.get("is_false_positive", False):
                        defect_list.append(d)
                        
            if not defect_list:
                flowables.append(Paragraph("No active structural defects detected on this facade.", self.styles["BodyDark"]))
            else:
                table_headers = [
                    Paragraph("Defect ID", self.styles["MetaLabel"]),
                    Paragraph("Type", self.styles["MetaLabel"]),
                    Paragraph("Length (cm)", self.styles["MetaLabel"]),
                    Paragraph("Width (mm)", self.styles["MetaLabel"]),
                    Paragraph("Area (cm2)", self.styles["MetaLabel"]),
                    Paragraph("Severity", self.styles["MetaLabel"]),
                    Paragraph("Conf.", self.styles["MetaLabel"])
                ]
                
                def_rows = [table_headers]
                for d in defect_list:
                    def_rows.append([
                        Paragraph(d.get("defect_id", "N/A"), self.styles["MetaValue"]),
                        Paragraph(d.get("type", "crack").replace("_", " ").title(), self.styles["MetaValue"]),
                        Paragraph(f"{d.get('length_cm', 0.0):.2f}", self.styles["MetaValue"]),
                        Paragraph(f"{d.get('width_mm', 0.0):.2f}", self.styles["MetaValue"]),
                        Paragraph(f"{d.get('area_cm2', 0.0):.2f}", self.styles["MetaValue"]),
                        Paragraph(d.get("severity_class", "minor").title(), self.styles["MetaValue"]),
                        Paragraph(f"{d.get('confidence_score', 0.0) * 100.0:.1f}%", self.styles["MetaValue"]),
                    ])
                    
                def_table = Table(def_rows, colWidths=[75, 90, 75, 75, 75, 80, 53])
                def_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECF0F1")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ]))
                
                # Highlight alternating rows
                for r_idx in range(1, len(def_rows)):
                    if r_idx % 2 == 0:
                        def_table.setStyle(TableStyle([
                            ("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F8F9FA"))
                        ]))
                        
                flowables.append(def_table)
                
            # Page Break to start Page 2 of facade details: Visual Diagnostics
            flowables.append(PageBreak())
            flowables.append(Paragraph(f"2.{idx+1}.2 Facade Visual Diagnostics — {fac.get('id')}", self.styles["SecHeading1"]))
            flowables.append(Spacer(1, 10))
            
            # Generate annotated mosaic
            annotated_img = self._generate_annotated_mosaic(fac, max_dim=512)
            # Generate zone heatmap
            zone_heatmap = self._generate_zone_heatmap(fac)
            
            visuals_data = []
            if annotated_img and zone_heatmap:
                visuals_data = [[annotated_img, zone_heatmap]]
            elif annotated_img:
                visuals_data = [[annotated_img, Paragraph("Zone heatmap unavailable.", self.styles["BodyDark"])]]
            elif zone_heatmap:
                visuals_data = [[Paragraph("Annotated mosaic unavailable.", self.styles["BodyDark"]), zone_heatmap]]
                
            if visuals_data:
                visuals_table = Table(visuals_data, colWidths=[260, 263])
                visuals_table.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                ]))
                flowables.append(visuals_table)
                
            # Filter defects to try to find one with structural information
            struct_data = fac
            for d in defect_list:
                if d.get("member_type") or d.get("rebar_spacing_cm"):
                    struct_data = d
                    break
                    
            bp_img = generate_blueprint_image(struct_data)
            wf_img = generate_3d_wireframe_image(struct_data)
            
            flowables.append(Spacer(1, 15))
            flowables.append(Paragraph("Facade Structural Diagrams (Representative)", self.styles["SecHeading2"]))
            flowables.append(Spacer(1, 5))
            
            diag_table = Table([[bp_img, wf_img]], colWidths=[260, 263])
            diag_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            flowables.append(diag_table)
            
            # Page Break to start Page 3 of facade details: Structural Analysis
            flowables.append(PageBreak())
            flowables.append(Paragraph(f"2.{idx+1}.3 Facade Structural Analysis — {fac.get('id')}", self.styles["SecHeading1"]))
            flowables.append(Spacer(1, 10))
            
            # Filter cracks and rebar defects
            crack_list = [d for d in defect_list if "crack" in str(d.get("crack_type") or d.get("type") or "").lower()]
            rebar_list = [d for d in defect_list if d.get("visible_bar_diameter_mm") is not None or "corrosion" in str(d.get("type")).lower() or "spalling" in str(d.get("type")).lower()]
            
            # Crack Schedule
            flowables.append(Paragraph("Facade Structural Crack Schedule", self.styles["SecHeading2"]))
            
            crack_rows = [[
                Paragraph("Crack ID", self.styles["MetaLabel"]),
                Paragraph("Grid Ref", self.styles["MetaLabel"]),
                Paragraph("Subtype", self.styles["MetaLabel"]),
                Paragraph("Orientation", self.styles["MetaLabel"]),
                Paragraph("Remedial Action", self.styles["MetaLabel"])
            ]]
            
            for d in crack_list:
                ctype = str(d.get("crack_type") or d.get("type") or "Crack").replace("_", " ").title()
                grid_ref = str(d.get("grid_reference") or "B4")
                orient = f"{d.get('orientation_angle', 45.0):.1f}°"
                action = d.get("recommended_intervention") or d.get("recommendation") or "Inject with epoxy mortar and monitor."
                
                crack_rows.append([
                    Paragraph(d.get("defect_id", "N/A"), self.styles["MetaValue"]),
                    Paragraph(grid_ref, self.styles["MetaValue"]),
                    Paragraph(ctype, self.styles["MetaValue"]),
                    Paragraph(orient, self.styles["MetaValue"]),
                    Paragraph(action, self.styles["MetaValue"])
                ])
                
            if len(crack_rows) <= 1:
                flowables.append(Paragraph("No active structural cracks detected on this facade.", self.styles["BodyDark"]))
            else:
                crack_table = Table(crack_rows, colWidths=[65, 55, 110, 75, 218])
                crack_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECF0F1")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ]))
                for r_idx in range(1, len(crack_rows)):
                    if r_idx % 2 == 0:
                        crack_table.setStyle(TableStyle([
                            ("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F8F9FA"))
                        ]))
                flowables.append(crack_table)
            
            flowables.append(Spacer(1, 15))
            
            # Rebar Schedule
            flowables.append(Paragraph("exposed Reinforcement & Rebar Exposure Schedule", self.styles["SecHeading2"]))
            
            rebar_rows = [[
                Paragraph("Defect ID", self.styles["MetaLabel"]),
                Paragraph("Grid Ref", self.styles["MetaLabel"]),
                Paragraph("Bar Dia (mm)", self.styles["MetaLabel"]),
                Paragraph("Cover Loss (mm)", self.styles["MetaLabel"]),
                Paragraph("Capacity Loss", self.styles["MetaLabel"]),
                Paragraph("Cover Status", self.styles["MetaLabel"])
            ]]
            
            for d in rebar_list:
                grid_ref = str(d.get("grid_reference") or "B4")
                bar_dia = d.get("visible_bar_diameter_mm")
                bar_dia_str = f"{bar_dia:.1f} mm" if bar_dia is not None else "12.0 mm (Est)"
                cover_loss = d.get("estimated_cover_loss_mm")
                cover_loss_str = f"{cover_loss:.1f} mm" if cover_loss is not None else "0.0 mm"
                cap_loss = d.get("capacity_reduction_pct")
                cap_loss_str = f"{cap_loss:.1f}%" if cap_loss is not None else "0.0%"
                loss_val = cover_loss if cover_loss is not None else 0.0
                cover_status = '<font color="#E74C3C"><b>Deficient</b></font>' if loss_val > 15.0 else '<font color="#2ECC71"><b>Adequate</b></font>'
                
                rebar_rows.append([
                    Paragraph(d.get("defect_id", "N/A"), self.styles["MetaValue"]),
                    Paragraph(grid_ref, self.styles["MetaValue"]),
                    Paragraph(bar_dia_str, self.styles["MetaValue"]),
                    Paragraph(cover_loss_str, self.styles["MetaValue"]),
                    Paragraph(cap_loss_str, self.styles["MetaValue"]),
                    Paragraph(cover_status, self.styles["MetaValue"])
                ])
                
            if len(rebar_rows) <= 1:
                flowables.append(Paragraph("No active exposed reinforcement or rebar corrosion-induced spalls detected.", self.styles["BodyDark"]))
            else:
                rebar_table = Table(rebar_rows, colWidths=[70, 70, 95, 95, 95, 98])
                rebar_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECF0F1")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ]))
                for r_idx in range(1, len(rebar_rows)):
                    if r_idx % 2 == 0:
                        rebar_table.setStyle(TableStyle([
                            ("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F8F9FA"))
                        ]))
                flowables.append(rebar_table)
            
            flowables.append(Spacer(1, 15))
            
            # IS 13935 / ACI 224R Compliance
            flowables.append(Paragraph("IS 13935 & ACI 224R Compliance Statement", self.styles["SecHeading2"]))
            compliance_text = (
                "<b>Notice:</b> This diagnostic assessment has been compiled in accordance with standard civil engineering guidelines: "
                "<b>IS 13935:2009</b> (Seismic Evaluation, Repair and Strengthening of Masonry Buildings - Guidelines) and "
                "<b>ACI 224R-01</b> (Control of Cracking in Concrete Structures). "
                "The estimated rebar diameter loss, spacing, concrete cover loss, and calculated structural capacity reduction percentage "
                "serve as engineering estimation indicators to assist professional inspection engineers. Any remedial injection, grouting, or carbon fiber wrap (CFRP) "
                "rehabilitation must be validated on-site using structural non-destructive testing (NDT) like rebound hammer or ultrasonic pulse velocity (UPV)."
            )
            flowables.append(Paragraph(compliance_text, self.styles["BodyDark"]))
                
            flowables.append(PageBreak())
            
        return flowables

    def build_temporal_comparison_page(self, building: Dict[str, Any], previous_building: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Create the temporal comparison page flowables.

        Parameters
        ----------
        building : dict
            Current building record (Cycle 2).
        previous_building : dict, optional
            Previous building record (Cycle 1).

        Returns
        -------
        list
            List of flowables representing the temporal comparison page.
        """
        flowables = []
        flowables.append(Paragraph("3. Temporal Comparison (Multi-Cycle Evolution)", self.styles["SecHeading1"]))
        
        if not previous_building:
            desc = (
                "<b>Baseline Scan Status:</b> No previous inspection cycles are registered in this building's "
                "data store. Cycle-to-cycle trend analytics, delta-VI progression charts, and growth rate computations "
                "will automatically populate when subsequent flight scans (Cycle 2+) are compiled.<br/><br/>"
                "A comparative analysis of Cycle 1 and subsequent Cycles will appear in this section in future reports."
            )
            flowables.append(Paragraph(desc, self.styles["BodyDark"]))
            flowables.append(Spacer(1, 15))
            
            # Generate a baseline placeholder chart (Cycle 1 scores only)
            orientations = []
            vi_c1 = []
            for fac in building.get("facades", []):
                orientations.append(f"Facade {fac.get('orientation', 'N')}")
                vi_c1.append(fac.get("vi_score", 0.0))
                
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.bar(orientations, vi_c1, width=0.4, label=f"Cycle {building.get('cycle_number', 1)} (Baseline)", color="#1B365D")
            ax.set_ylabel("Vulnerability Index (VI)")
            ax.set_title("Vulnerability Index (VI) — Baseline Cycle 1", fontsize=9, fontweight="bold")
            ax.set_ylim(0, 100)
            ax.legend()
            ax.grid(axis='y', linestyle='--', alpha=0.5)
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=120)
            plt.close(fig)
            buf.seek(0)
            
            flowables.append(Image(buf, width=380, height=200))
            flowables.append(PageBreak())
            return flowables

        desc = (
            f"This section presents comparative diagnostics tracking structural progression between "
            f"Cycle {previous_building.get('cycle_number', 1)} (Baseline: {previous_building.get('inspection_date', 'N/A')}) "
            f"and Cycle {building.get('cycle_number', 2)} (Current: {building.get('inspection_date', 'N/A')})."
        )
        flowables.append(Paragraph(desc, self.styles["BodyDark"]))
        flowables.append(Spacer(1, 10))

        # 1. Delta-VI Chart
        flowables.append(Paragraph("Facade Vulnerability Progression Chart", self.styles["SecHeading2"]))
        delta_chart = self._generate_delta_vi_chart(building, previous_building)
        flowables.append(delta_chart)
        flowables.append(Spacer(1, 10))

        # 2. Side-by-Side Mosaics
        flowables.append(Paragraph("Side-by-Side Facade Comparison (Cycle 1 vs. Cycle 2)", self.styles["SecHeading2"]))
        
        c1_facade = previous_building.get("facades", [{}])[0]
        c2_facade = building.get("facades", [{}])[0]
        
        c1_img = self._generate_annotated_mosaic(c1_facade, max_dim=256)
        c2_img = self._generate_annotated_mosaic(c2_facade, max_dim=256)
        
        if c1_img and c2_img:
            # Wrap side-by-side in a layout table
            mosaic_layout = Table([[c1_img, c2_img]], colWidths=[260, 263])
            mosaic_layout.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            flowables.append(mosaic_layout)
            
        flowables.append(Spacer(1, 10))

        # 3. New Defect List
        flowables.append(Paragraph("New Defect Instances Detected in Cycle 2", self.styles["SecHeading2"]))
        new_defects = []
        for fac in building.get("facades", []):
            for z in fac.get("zones", []):
                for d in z.get("defects", []):
                    if not d.get("is_false_positive", False) and d.get("temporal_status") == "new":
                        d_copy = d.copy()
                        d_copy["facade_id"] = fac.get("id", "N/A")
                        new_defects.append(d_copy)

        if not new_defects:
            flowables.append(Paragraph("No new structural defects detected in this cycle. Overall conditions stable.", self.styles["BodyDark"]))
        else:
            table_headers = [
                Paragraph("Defect ID", self.styles["MetaLabel"]),
                Paragraph("Location", self.styles["MetaLabel"]),
                Paragraph("Type", self.styles["MetaLabel"]),
                Paragraph("Width (mm)", self.styles["MetaLabel"]),
                Paragraph("Area (cm2)", self.styles["MetaLabel"])
            ]
            new_rows = [table_headers]
            for d in new_defects:
                new_rows.append([
                    Paragraph(d.get("defect_id", "N/A"), self.styles["MetaValue"]),
                    Paragraph(d.get("facade_id", "N/A"), self.styles["MetaValue"]),
                    Paragraph(d.get("type", "crack").replace("_", " ").title(), self.styles["MetaValue"]),
                    Paragraph(f"{d.get('width_mm', 0.0):.2f}", self.styles["MetaValue"]),
                    Paragraph(f"{d.get('area_cm2', 0.0):.2f}", self.styles["MetaValue"])
                ])
                
            new_table = Table(new_rows, colWidths=[100, 100, 120, 100, 103])
            new_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FDEDEC")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ]))
            flowables.append(new_table)

        flowables.append(PageBreak())
        return flowables

    def build_recommendations_page(self, building: Dict[str, Any]) -> List[Any]:
        """Create standard recommendations table page."""
        flowables = []
        flowables.append(Paragraph("3. Remediation & Action Recommendations", self.styles["SecHeading1"]))
        
        desc = (
            "The following table collects all identified defect instances requiring remediation, "
            "ordered by severity. Repair instructions and response timelines conform strictly to "
            "the Indian Standard IS 13311 protocol."
        )
        flowables.append(Paragraph(desc, self.styles["BodyDark"]))
        flowables.append(Spacer(1, 15))
        
        # Compile all active defects
        all_defects = []
        facades = building.get("facades", [])
        for f in facades:
            for z in f.get("zones", []):
                for d in z.get("defects", []):
                    if not d.get("is_false_positive", False):
                        # Attach facade ID to defect context
                        d_copy = d.copy()
                        d_copy["facade_id"] = f.get("id", "N/A")
                        all_defects.append(d_copy)
                        
        if not all_defects:
            flowables.append(Paragraph("No active structural defects require intervention.", self.styles["BodyDark"]))
            return flowables
            
        # Sort defects by severity: wide -> medium -> fine -> hairline
        sev_priority = {"wide": 0, "medium": 1, "fine": 2, "hairline": 3}
        all_defects.sort(key=lambda x: sev_priority.get(x.get("severity_class", "hairline"), 4))
        
        table_headers = [
            Paragraph("Defect ID", self.styles["MetaLabel"]),
            Paragraph("Location", self.styles["MetaLabel"]),
            Paragraph("Type & Size", self.styles["MetaLabel"]),
            Paragraph("Remediation Action (IS 13311)", self.styles["MetaLabel"]),
            Paragraph("Priority", self.styles["MetaLabel"]),
            Paragraph("Timeline", self.styles["MetaLabel"]),
            Paragraph("Responsible Eng.", self.styles["MetaLabel"])
        ]
        
        rec_rows = [table_headers]
        for d in all_defects:
            
            # Tailor recommendation based on category
            dtype = d.get("type", "crack")
            sev = d.get("severity_class", "hairline").lower()
            
            # Determine Priority & color-coded string
            if sev == "wide":
                priority_html = '<font color="#E74C3C"><b>Critical</b></font>'
                action = "Structural pressure grouting with low-viscosity epoxy resins. Core drill validation."
                timeline = "Within 2 weeks."
            elif sev == "medium":
                priority_html = '<font color="#E67E22"><b>High</b></font>'
                action = "Polyurethane injection resin seal. Grind crack lips and seal with epoxy mortar."
                timeline = "Within 60 days."
            elif sev == "fine":
                priority_html = '<font color="#F1C40F"><b>Medium</b></font>'
                action = "Surface crack sealer and flexible elastomeric protective coating. Monitor annually."
                timeline = "Within 3 months."
            else:
                priority_html = '<font color="#2ECC71"><b>Low</b></font>'
                action = "Surface crack sealer. Monitor at next scheduled inspection."
                timeline = "Within 6 months."
                
            if dtype == "spalling":
                action = "Hacksaw boundaries, remove loose concrete, clean rebar, coat with anti-rust, re-profile mortar."
                if sev in ("wide", "medium"):
                    priority_html = '<font color="#E74C3C"><b>Critical</b></font>'
                    timeline = "Within 2 weeks."
                else:
                    priority_html = '<font color="#E67E22"><b>High</b></font>'
                    timeline = "Within 30 days."
            elif dtype == "corrosion":
                action = "Chisel concrete, brush clean rebar, apply zinc-rich protective primer, polymer concrete patch."
                priority_html = '<font color="#E67E22"><b>High</b></font>'
                timeline = "Within 30 days."
            elif dtype not in ("crack", "spalling", "corrosion"):
                action = "Clean surface deposits using mild washing agents. Seal facade with water-repellant silane sealer."
                priority_html = '<font color="#2ECC71"><b>Low</b></font>'
                timeline = "Next maintenance cycle."
                
            # Responsible Engineer sign-off line
            eng_signoff = Paragraph("<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>", self.styles["MetaValue"])
            
            rec_rows.append([
                Paragraph(d.get("defect_id", "N/A"), self.styles["MetaValue"]),
                Paragraph(d.get("facade_id", "N/A"), self.styles["MetaValue"]),
                Paragraph(f"{dtype.replace('_', ' ').title()} ({sev.title()}, {d.get('width_mm', 0.0):.2f}mm)", self.styles["MetaValue"]),
                Paragraph(action, self.styles["MetaValue"]),
                Paragraph(priority_html, self.styles["MetaValue"]),
                Paragraph(timeline, self.styles["MetaValue"]),
                eng_signoff
            ])
            
        rec_table = Table(rec_rows, colWidths=[65, 55, 85, 138, 55, 65, 60])
        rec_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B365D")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ]))
        
        # Color table headers
        for col in range(7):
            rec_table.setStyle(TableStyle([
                ("TEXTCOLOR", (col, 0), (col, 0), colors.white)
            ]))
            
        # Alternate backgrounds
        for r_idx in range(1, len(rec_rows)):
            if r_idx % 2 == 0:
                rec_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F8F9FA"))
                ]))
                
        flowables.append(rec_table)
        return flowables

    def _add_crack_schedule_table(self, story, defects):
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        
        story.append(Paragraph("Detailed Crack Schedule", self.styles['Heading2']))
        story.append(Spacer(1, 10))
        
        table_data = [["ID", "Type", "Width (mm)", "Length (cm)", "Grid Ref", "Intervention"]]
        for d in defects:
            sev = d.get("severity_class", "hairline").lower()
            table_data.append([
                d.get("defect_id", "N/A"),
                d.get("crack_subtype", d.get("type", "crack")),
                f"{d.get('width_mm', 0):.2f}",
                f"{d.get('length_cm', 0):.2f}",
                d.get("grid_ref", d.get("grid_reference", "N/A")),
                INTERVENTION_BY_SEVERITY.get(sev, "Review")
            ])
            
        if len(table_data) > 1:
            t = Table(table_data, colWidths=[60, 100, 70, 70, 60, 140])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            story.append(t)
        else:
            story.append(Paragraph("No defects detected.", self.styles['Normal']))
        story.append(Spacer(1, 20))

    def _add_rebar_summary_table(self, story, rebar_results):
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        
        story.append(Paragraph("Rebar Exposure & Cover Summary", self.styles['Heading2']))
        story.append(Spacer(1, 10))
        
        if not rebar_results:
            story.append(Paragraph("No exposed rebar detected.", self.styles['Normal']))
            story.append(Spacer(1, 20))
            return
            
        table_data = [["Defect ID", "Grid Ref", "Meas. Cover", "Req. Cover", "Status", "Bars Visible"]]
        for r in rebar_results:
            table_data.append([
                r.get("defect_id", "N/A"),
                r.get("grid_ref", "N/A"),
                f"{r.get('measured_cover_mm', 0)} mm",
                f"{r.get('required_cover_mm', 0)} mm",
                r.get("cover_status", "N/A"),
                str(r.get("bar_count_visible", 0))
            ])
            
        t = Table(table_data, colWidths=[80, 80, 80, 80, 80, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))

    def generate(self, json_data: Dict[str, Any], output_path: Union[str, Path]) -> str:
        """Process assembled building inspection data and compile the PDF document.

        Parameters
        ----------
        json_data : dict
            Input dictionary conforming to the output schema.
        output_path : str or Path
            File destination path.

        Returns
        -------
        str
            Absolute path to the compiled PDF file.
        """
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        
        # Resolve building and previous_building
        buildings = json_data.get("buildings", [])
        building = None
        previous_building = None
        
        if isinstance(buildings, list) and len(buildings) > 0:
            sorted_buildings = sorted(buildings, key=lambda b: b.get("cycle_number", 1), reverse=True)
            building = sorted_buildings[0]
            if len(sorted_buildings) > 1:
                previous_building = sorted_buildings[1]
        else:
            building = json_data.get("building")
            if not building:
                building = json_data

        # If previous_building is None but building contains temporal_comparison, reconstruct previous_building dynamically
        if not previous_building and isinstance(building, dict) and "temporal_comparison" in building:
            comp = building["temporal_comparison"]
            prev_cycle = comp.get("comparison_cycle", 1)
            previous_building = {
                "id": building.get("id"),
                "cycle_number": prev_cycle,
                "inspection_date": "Previous Cycle",
                "facades": []
            }
            delta_vi = comp.get("delta_vi", 0.0)
            for f in building.get("facades", []):
                previous_building["facades"].append({
                    "id": f.get("id"),
                    "orientation": f.get("orientation"),
                    "vi_score": max(0.0, f.get("vi_score", 0.0) - delta_vi)
                })
        
        # Calculate building level composite VI
        facades = building.get("facades", [])
        vi_scores = [f.get("vi_score", 0.0) for f in facades]
        overall_vi = max(vi_scores) if vi_scores else 0.0
        
        # Setup document template A4 size (595.27 x 841.89 points)
        # Margin: 36pt (0.5 inch)
        doc = SimpleDocTemplate(
            str(out_p),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=54,
            bottomMargin=54,
        )
        
        story = []
        
        # 1. Build Cover Page
        story.extend(self.build_cover_page(building, overall_vi))
        
        # 2. Build Executive Summary
        story.extend(self.build_executive_summary(building, overall_vi, previous_building))
        
        # Collect all defects flat
        all_defects = []
        for f in building.get("facades", []):
            for z in f.get("zones", []):
                all_defects.extend(z.get("defects", []))
                
        # 2.5 New Step 6 additions
        self._add_crack_schedule_table(story, all_defects)
        self._add_rebar_summary_table(story, json_data.get("rebar_analysis", []))
        
        # 3. Build Facades details pages
        story.extend(self.build_facade_pages(building))
        
        # 3.5 Build Temporal Comparison Page
        story.extend(self.build_temporal_comparison_page(building, previous_building))
        
        # 4. Build recommendations table
        story.extend(self.build_recommendations_page(building))
        
        # Build PDF using NumberedCanvas
        doc.build(story, canvasmaker=NumberedCanvas)
        
        logger.info("PDF inspection report generated successfully at %s", out_p)
        return str(out_p)


def generate_single_defect_pdf(data: Dict[str, Any]) -> bytes:
    """
    Generates a single-page professional structural diagnostic report for an analyzed defect image.
    
    Parameters
    ----------
    data : dict
        A dictionary of the analyzed defect attributes.

    Returns
    -------
    bytes
        Compiled PDF binary data.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from datetime import datetime
    import io

    # 1. Setup in-memory document
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    primary_color = colors.HexColor("#1B365D")  # Deep Corporate Navy
    text_dark = colors.HexColor("#2C3E50")      # Charcoal
    
    # Header title
    title_style = ParagraphStyle(
        name="SingleTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.white,
        alignment=1 # Centered
    )
    
    sec_heading = ParagraphStyle(
        name="SingleSec",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=primary_color,
        spaceBefore=10,
        spaceAfter=5,
    )
    
    label_style = ParagraphStyle(
        name="SingleLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=primary_color
    )
    
    val_style = ParagraphStyle(
        name="SingleValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=10,
        textColor=text_dark
    )
    
    body_style = ParagraphStyle(
        name="SingleBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13.5,
        textColor=text_dark,
        spaceAfter=4
    )

    story = []

    # --- HEADER BLOCK ---
    header_data = [
        [Paragraph("CORTEX VISUAL PLATFORM &mdash; CONCRETE DEFECT MANUAL", title_style)]
    ]
    header_table = Table(header_data, colWidths=[523], rowHeights=[30])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary_color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # --- DEFECT METADATA ---
    story.append(Paragraph("1. General Inspection Metadata", sec_heading))
    
    # Severity Badge
    sev = data.get("severity", "minor").lower()
    sev_bg = "#2ECC71"  # green
    if sev == "critical": sev_bg = "#E74C3C"  # red
    elif sev == "severe": sev_bg = "#E67E22"  # orange
    elif sev == "moderate": sev_bg = "#F1C40F"  # yellow
    
    badge_style = ParagraphStyle(
        name="SingleBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        alignment=1,
        textColor=colors.white
    )
    badge_p = Paragraph(sev.upper(), badge_style)
    badge_table = Table([[badge_p]], colWidths=[70], rowHeights=[12])
    badge_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(sev_bg)),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(sev_bg)),
    ]))
    
    meta_data = [
        [Paragraph("SOURCE IMAGE:", label_style), Paragraph(data.get("filename", "N/A"), val_style),
         Paragraph("GRID REF:", label_style), Paragraph(data.get("grid_reference", "B4"), val_style)],
        [Paragraph("MEMBER TYPE:", label_style), Paragraph(str(data.get("member_type", "slab")).upper(), val_style),
         Paragraph("SEVERITY CLASS:", label_style), badge_table],
        [Paragraph("PROPAGATION:", label_style), Paragraph(str(data.get("propagation_rate", "dormant")).upper(), val_style),
         Paragraph("RE-INSPECT DATE:", label_style), Paragraph(data.get("reinspection_date", "N/A"), val_style)]
    ]
    meta_table = Table(meta_data, colWidths=[110, 150, 110, 153])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDC3C7")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # --- DEFECT PHYSICAL QUANTIFICATION ---
    story.append(Paragraph("2. Physical Metric Quantification", sec_heading))
    
    measure_data = [
        [Paragraph("CRACK MAXIMUM WIDTH:", label_style), Paragraph(f"{data.get('width_mm', 0.0):.2f} mm", val_style),
         Paragraph("CRACK TOTAL LENGTH:", label_style), Paragraph(f"{data.get('length_cm', 0.0):.1f} cm", val_style)],
        [Paragraph("REBAR SPACING (s):", label_style), Paragraph(f"{data.get('rebar_spacing_cm', 0.0):.1f} cm", val_style),
         Paragraph("ORIENTATION ANGLE:", label_style), Paragraph(f"{data.get('orientation_angle', 45.0):.1f}&deg; from vertical", val_style)]
    ]
    measure_table = Table(measure_data, colWidths=[150, 110, 150, 113])
    measure_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDC3C7")),
    ]))
    story.append(measure_table)
    story.append(Spacer(1, 8))

    # --- REBAR DEGRADATION ANALYSIS ---
    if data.get("visible_bar_diameter_mm") is not None:
        story.append(Paragraph("3. Exposed Reinforcement & Cover Loss Diagnostics", sec_heading))
        
        loss_val = data.get("estimated_cover_loss_mm", 0.0)
        c_status = '<font color="#E74C3C"><b>DEFICIENT</b></font>' if loss_val > 15.0 else '<font color="#2ECC71"><b>ADEQUATE</b></font>'
        
        rebar_data = [
            [Paragraph("ESTIMATED ROD DIA:", label_style), Paragraph(f"{data.get('visible_bar_diameter_mm', 0.0):.1f} mm", val_style),
             Paragraph("COVER DEPTH LOSS:", label_style), Paragraph(f"{data.get('estimated_cover_loss_mm', 0.0):.1f} mm", val_style)],
            [Paragraph("CAPACITY REDUCTION:", label_style), Paragraph(f"<font color='#E74C3C'><b>{data.get('capacity_reduction_pct', 0.0):.1f}%</b></font>", val_style),
             Paragraph("COVER DESIGN STATUS:", label_style), Paragraph(c_status, val_style)],
            [Paragraph("ROD TYPE:", label_style), Paragraph(f"<b>{data.get('rod_type', 'N/A')}</b>", val_style),
             Paragraph("CLEAR GAP:", label_style), Paragraph(f"{data.get('clear_gap_mm', 0.0):.1f} mm", val_style)]
        ]
        rebar_table = Table(rebar_data, colWidths=[150, 110, 150, 113])
        rebar_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDC3C7")),
        ]))
        story.append(rebar_table)
        story.append(Spacer(1, 8))

    # --- STRUCTURAL DIAGRAMS ---
    story.append(Paragraph("3b. Member Structural Diagnostics (X-Ray & 3D)", sec_heading))
    bp_img = generate_blueprint_image(data)
    wf_img = generate_3d_wireframe_image(data)
    
    diag_table = Table([[bp_img, wf_img]], colWidths=[250, 250])
    diag_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(diag_table)
    story.append(Spacer(1, 8))

    # --- REMEDIAL ACTION SPECIFICATION ---
    story.append(Paragraph("4. Engineering Action & Remedial Specifications", sec_heading))
    story.append(Paragraph(data.get("recommendation", "N/A"), body_style))
    story.append(Spacer(1, 8))

    # --- COMPLIANCE AND GUIDELINES ---
    story.append(Paragraph("5. Regulatory Compliance & Structural Standards", sec_heading))
    compliance_text = (
        "This diagnostic evaluation was processed in conformity with standard civil engineering design guidelines "
        "<b>IS 13935:2009</b> (Seismic Evaluation, Repair and Strengthening of Masonry Buildings) and "
        "<b>ACI 224R-01</b> (Control of Cracking in Concrete Structures). "
        "Values for rebar spacing, diameter, and cover loss are estimated based on visual GSD markers. "
        "Before applying structural repairs, a field engineer must verify reinforcement integrity using "
        "destructive (core extraction) or non-destructive (rebound hammer, ultrasonic pulse velocity) tests."
    )
    # --- SIGN-OFF BLOCK ---
    sign_data = [
        [Paragraph("<b>PREPARED BY:</b> Cortex AI Vision Pipeline", val_style), Paragraph("<b>VERIFIED BY (STRUCTURAL ENG):</b>", val_style)],
        [Paragraph("Signature: <i>Automated Verification</i>", val_style), Paragraph("Signature: __________________________", val_style)],
        [Paragraph("Date: " + datetime.now().strftime("%Y-%m-%d"), val_style), Paragraph("Date: _________________________", val_style)]
    ]
    sign_table = Table(sign_data, colWidths=[260, 263])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
    ]))
    story.append(sign_table)

    # 4. Build A4 Document
    doc.build(story)
    
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


def generate_compiled_defects_pdf(data_list: list) -> bytes:
    """
    Generates a multi-page compiled structural diagnostic report PDF for a list of defects.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from datetime import datetime
    import io

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    primary_color = colors.HexColor("#1B365D")
    text_dark = colors.HexColor("#2C3E50")
    
    title_style = ParagraphStyle(
        name="CompTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.white,
        alignment=1
    )
    
    sec_heading = ParagraphStyle(
        name="CompSec",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=primary_color,
        spaceBefore=8,
        spaceAfter=4,
    )
    
    label_style = ParagraphStyle(
        name="CompLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=9.5,
        textColor=primary_color
    )
    
    val_style = ParagraphStyle(
        name="CompValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=9.5,
        textColor=text_dark
    )
    
    body_style = ParagraphStyle(
        name="CompBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=text_dark,
        spaceAfter=3
    )

    badge_style = ParagraphStyle(
        name="CompBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        alignment=1,
        textColor=colors.white
    )

    story = []

    # --- COVER / SUMMARY PAGE ---
    story.append(Paragraph("CORTEX VISUAL PLATFORM &mdash; COMPILED STRUCTURAL REPORT", ParagraphStyle(
        name="CoverHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=primary_color, alignment=1
    )))
    story.append(Spacer(1, 15))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", val_style))
    story.append(Spacer(1, 15))
    
    # Overview Table Header
    overview_data = [
        [
            Paragraph("<b>Slot</b>", label_style),
            Paragraph("<b>Defect / Crack Type</b>", label_style),
            Paragraph("<b>Severity</b>", label_style),
            Paragraph("<b>Width (mm)</b>", label_style),
            Paragraph("<b>Length (cm)</b>", label_style),
            Paragraph("<b>V-Index</b>", label_style),
        ]
    ]
    
    for i, defect in enumerate(data_list):
        sev = defect.get("severity", "minor").lower()
        sev_bg = "#2ECC71"
        if sev == "critical": sev_bg = "#E74C3C"
        elif sev == "severe": sev_bg = "#E67E22"
        elif sev == "moderate": sev_bg = "#F1C40F"
        
        badge_p = Paragraph(sev.upper(), badge_style)
        badge_table = Table([[badge_p]], colWidths=[55], rowHeights=[11])
        badge_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(sev_bg)),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(sev_bg)),
        ]))
        
        overview_data.append([
            Paragraph(f"Slot {i+1}", val_style),
            Paragraph(defect.get("crack_type", "N/A"), val_style),
            badge_table,
            Paragraph(f"{defect.get('width_mm', 0.0):.2f}", val_style),
            Paragraph(f"{defect.get('length_cm', 0.0):.1f}", val_style),
            Paragraph(f"{defect.get('v_index', 0.0):.2f}", val_style),
        ])
        
    overview_table = Table(overview_data, colWidths=[40, 160, 70, 80, 80, 93])
    overview_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECF0F1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 20))
    
    # Executive Summary Paragraph
    exec_summary_text = (
        "<b>Executive Summary:</b> This compiled structural diagnostic report provides a comparative side-by-side analysis "
        "of the three evaluated UAV visual slots. High-severity defects (such as shear cracks and compression splits) "
        "require immediate physical shoring and low-viscosity structural epoxy injection as specified in the individual "
        "diagnostic pages. All measurements are calibrated from UAV ground sampling distance (GSD)."
    )
    story.append(Paragraph(exec_summary_text, body_style))
    story.append(Spacer(1, 25))
    
    # Sign-off block at bottom of summary page
    summary_sign_data = [
        [Paragraph("<b>PREPARED BY:</b> Cortex AI Vision Pipeline", val_style), Paragraph("<b>VERIFIED BY (STRUCTURAL ENG):</b>", val_style)],
        [Paragraph("Signature: <i>Automated Verification</i>", val_style), Paragraph("Signature: __________________________", val_style)],
        [Paragraph("Date: " + datetime.now().strftime("%Y-%m-%d"), val_style), Paragraph("Date: _________________________", val_style)]
    ]
    summary_sign_table = Table(summary_sign_data, colWidths=[260, 263])
    summary_sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
    ]))
    story.append(summary_sign_table)
    
    # PageBreak after summary page
    story.append(PageBreak())

    # ── DETAIL PAGES ──
    for i, defect in enumerate(data_list):
        # Header block for this defect page
        header_data = [
            [Paragraph(f"CORTEX VISUAL PLATFORM &mdash; SLOT {i+1} DIAGNOSTIC SPECIFICATION", title_style)]
        ]
        header_table = Table(header_data, colWidths=[523], rowHeights=[26])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), primary_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 6))

        # Metadata
        story.append(Paragraph("1. General Inspection Metadata", sec_heading))
        sev = defect.get("severity", "minor").lower()
        sev_bg = "#2ECC71"
        if sev == "critical": sev_bg = "#E74C3C"
        elif sev == "severe": sev_bg = "#E67E22"
        elif sev == "moderate": sev_bg = "#F1C40F"
        
        badge_p = Paragraph(sev.upper(), badge_style)
        badge_table = Table([[badge_p]], colWidths=[65], rowHeights=[11])
        badge_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(sev_bg)),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(sev_bg)),
        ]))
        
        meta_data = [
            [Paragraph("SOURCE IMAGE:", label_style), Paragraph(defect.get("filename", "N/A"), val_style),
             Paragraph("GRID REF:", label_style), Paragraph(defect.get("grid_reference", "B4"), val_style)],
            [Paragraph("MEMBER TYPE:", label_style), Paragraph(str(defect.get("member_type", "slab")).upper(), val_style),
             Paragraph("SEVERITY CLASS:", label_style), badge_table],
            [Paragraph("PROPAGATION:", label_style), Paragraph(str(defect.get("propagation_rate", "dormant")).upper(), val_style),
             Paragraph("RE-INSPECT DATE:", label_style), Paragraph(defect.get("reinspection_date", "N/A"), val_style)]
        ]
        meta_table = Table(meta_data, colWidths=[110, 150, 110, 153])
        meta_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDC3C7")),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 6))

        # Metrics
        story.append(Paragraph("2. Physical Metric Quantification", sec_heading))
        measure_data = [
            [Paragraph("CRACK MAXIMUM WIDTH:", label_style), Paragraph(f"{defect.get('width_mm', 0.0):.2f} mm", val_style),
             Paragraph("CRACK TOTAL LENGTH:", label_style), Paragraph(f"{defect.get('length_cm', 0.0):.1f} cm", val_style)],
            [Paragraph("REBAR SPACING (s):", label_style), Paragraph(f"{defect.get('rebar_spacing_cm', 0.0):.1f} cm", val_style),
             Paragraph("ORIENTATION ANGLE:", label_style), Paragraph(f"{defect.get('orientation_angle', 45.0):.1f}&deg; from vertical", val_style)]
        ]
        measure_table = Table(measure_data, colWidths=[150, 110, 150, 113])
        measure_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#BDC3C7")),
        ]))
        story.append(measure_table)
        story.append(Spacer(1, 6))

        # Drawings
        story.append(Paragraph("3. Member Structural Diagnostics (X-Ray & 3D)", sec_heading))
        bp_img = generate_blueprint_image(defect)
        wf_img = generate_3d_wireframe_image(defect)
        
        diag_table = Table([[bp_img, wf_img]], colWidths=[250, 250])
        diag_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(diag_table)
        story.append(Spacer(1, 6))

        # Remedial
        story.append(Paragraph("4. Engineering Action & Remedial Specifications", sec_heading))
        story.append(Paragraph(defect.get("recommendation", "N/A"), body_style))
        story.append(Spacer(1, 6))

        # Regulatory Compliance
        story.append(Paragraph("5. Regulatory Compliance & Structural Standards", sec_heading))
        compliance_text = (
            "This diagnostic evaluation was processed in conformity with standard civil engineering design guidelines "
            "<b>IS 13935:2009</b> (Seismic Evaluation, Repair and Strengthening of Masonry Buildings) and "
            "<b>ACI 224R-01</b> (Control of Cracking in Concrete Structures). "
            "Values for rebar spacing, diameter, and cover loss are estimated based on visual GSD markers. "
            "Before applying structural repairs, a field engineer must verify reinforcement integrity."
        )
        story.append(Paragraph(compliance_text, body_style))
        
        # If it is not the last page, add page break
        if i < len(data_list) - 1:
            story.append(PageBreak())

    # Build A4 Document
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()
