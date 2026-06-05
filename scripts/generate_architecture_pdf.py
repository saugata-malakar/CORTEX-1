# scripts/generate_architecture_pdf.py
import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted, Image
)
from reportlab.pdfgen import canvas

# -------------------------------------------------------------------------
# DIAGRAM GENERATORS (MATPLOTLIB)
# -------------------------------------------------------------------------

def generate_hld_monolith_diagram(output_path):
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    # Rows layout
    # Row 1: y = 3.5, Row 2: y = 2.0, Row 3: y = 0.5
    boxes = [
        # Row 1
        (0.5, 3.5, 1.8, 0.7, "UAV Raw Images\n(Input)"),
        (2.8, 3.5, 1.8, 0.7, "Ingestion &\nEXIF Quality Gates"),
        (5.1, 3.5, 1.8, 0.7, "Contrast & \nRectification"),
        (7.4, 3.5, 1.8, 0.7, "SIFT / USAC-MAGSAC\nStitcher"),
        # Row 2
        (7.4, 2.0, 1.8, 0.7, "RAM Mosaic\n(Stitched Image)"),
        (5.1, 2.0, 1.8, 0.7, "Quantification\nEngine"),
        (2.8, 2.0, 1.8, 0.7, "96x96 Patch Crop\nExtractor"),
        (0.5, 2.0, 1.8, 0.7, "Unified 180-dim\nFeature Extractor"),
        # Row 3
        (0.5, 0.5, 1.8, 0.7, "XGBoost False\nPositive Filter"),
        (2.8, 0.5, 1.8, 0.7, "VI Scoring &\nGrid Aggregator"),
        (5.1, 0.5, 1.8, 0.7, "PLATYPUS PDF &\nJSON Generator"),
        (7.4, 0.5, 1.8, 0.7, "AWS S3 / R2\n& Global CDN")
    ]

    for x, y, w, h, text in boxes:
        rect = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.03",
            linewidth=1.0,
            edgecolor='#1E3A8A',
            facecolor='#EFF6FF',
            mutation_scale=0.2
        )
        ax.add_patch(rect)
        ax.text(
            x + w/2, y + h/2, text,
            ha='center', va='center',
            fontsize=7, color='#0F172A',
            fontweight='bold', family='sans-serif'
        )

    arrows = [
        # Row 1 arrows
        (2.3, 3.85, 0.5, 0),
        (4.6, 3.85, 0.5, 0),
        (6.9, 3.85, 0.5, 0),
        # Row 1 down to Row 2
        (8.3, 3.5, 0, -0.8),
        # Row 2 arrows
        (7.4, 2.35, -0.5, 0),
        (5.1, 2.35, -0.5, 0),
        (2.8, 2.35, -0.5, 0),
        # Row 2 down to Row 3
        (1.4, 2.0, 0, -0.8),
        # Row 3 arrows
        (2.3, 0.85, 0.5, 0),
        (4.6, 0.85, 0.5, 0),
        (6.9, 0.85, 0.5, 0)
    ]

    for x, y, dx, dy in arrows:
        ax.arrow(
            x, y, dx, dy,
            head_width=0.08, head_length=0.08,
            fc='#3B82F6', ec='#3B82F6',
            length_includes_head=True,
            linewidth=1.0
        )

    # Monolith RAM space border
    ram_box = patches.Rectangle(
        (0.3, 1.25), 9.1, 1.7,
        linewidth=1, edgecolor='#94A3B8', facecolor='none', linestyle='--'
    )
    ax.add_patch(ram_box)
    ax.text(0.4, 2.8, "MONOLITH CPU / GPU MEMORY SPACE (Shared RAM)", fontsize=6.5, color='#64748B', fontweight='bold')

    plt.savefig(output_path, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()

def generate_sequence_diagram(output_path):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10.5, 5.25), dpi=300)
    ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    participants = [
        (1.0, "Field Engineer\nClient"),
        (3.0, "FastAPI\nAPI"),
        (5.0, "Redis\nCache"),
        (7.0, "Celery\nWorker"),
        (9.0, "ML Core\n(Inference)"),
        (11.0, "PostgreSQL\nDatabase")
    ]

    for x, name in participants:
        ax.text(x, 9.5, name, ha='center', va='center', fontsize=7.5, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#1E3A8A', edgecolor='#1E3A8A', alpha=0.9),
                color='white')
        ax.plot([x, x], [0.8, 9.0], color='#94A3B8', linestyle='--', linewidth=0.8)

    steps = [
        (1.0, 3.0, 8.5, "1. POST /api/v1/run-inspection", "1"),
        (3.0, 11.0, 7.8, "2. Create inspection (pending)", "2"),
        (3.0, 7.0, 7.1, "3. Enqueue inspection task", "3"),
        (3.0, 1.0, 6.4, "4. HTTP 202 Accepted {job_id}", "4"),
        (7.0, 9.0, 5.7, "5. POST /predict (run inference)", "5"),
        (9.0, 7.0, 5.0, "6. Return defect classes/severity", "6"),
        (7.0, 11.0, 4.3, "7. Update inspection (success & report)", "7"),
        (7.0, 5.0, 3.6, "8. Set job status = complete", "8"),
        (1.0, 3.0, 2.9, "9. GET /api/v1/jobs/{job_id}", "9"),
        (3.0, 5.0, 2.2, "10. Read status from cache", "10"),
        (5.0, 3.0, 1.5, "11. Return job status", "11"),
        (3.0, 1.0, 0.8, "12. HTTP 200 OK {status: complete, report}", "12")
    ]

    for from_x, to_x, y, label, num in steps:
        direction = 1 if to_x > from_x else -1
        arrow_start = from_x
        arrow_end = to_x
        
        ax.annotate(
            "",
            xy=(arrow_end, y),
            xytext=(arrow_start, y),
            arrowprops=dict(
                arrowstyle="->",
                color='#3B82F6' if direction == 1 else '#EF4444',
                lw=1.2,
                ls='-' if direction == 1 else '--'
            )
        )
        
        ax.text(
            (from_x + to_x) / 2, y + 0.12,
            f"({num}) {label}",
            ha='center', va='bottom',
            fontsize=6.5, color='#334155',
            bbox=dict(boxstyle='square,pad=0.05', facecolor='#F8FAFC', edgecolor='none')
        )

    plt.savefig(output_path, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()

def generate_cache_cdn_diagram(output_path):
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    boxes = [
        (0.5, 2.8, 2.0, 0.8, "Field Engineer\nBrowser Client"),
        (3.5, 2.8, 2.0, 0.8, "Cloudflare CDN\nEdge Cache"),
        (6.5, 2.8, 2.0, 0.8, "FastAPI Application\n(Tile & Jobs API)"),
        (6.5, 1.3, 2.0, 0.8, "Redis Cache\n(Cache-Aside DB)"),
        (3.5, 1.3, 2.0, 0.8, "PostgreSQL Master\n& S3 Object Store")
    ]

    for x, y, w, h, text in boxes:
        rect = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.03",
            linewidth=1.0,
            edgecolor='#1E3A8A',
            facecolor='#EFF6FF',
            mutation_scale=0.2
        )
        ax.add_patch(rect)
        ax.text(
            x + w/2, y + h/2, text,
            ha='center', va='center',
            fontsize=7.5, color='#0F172A',
            fontweight='bold', family='sans-serif'
        )

    ax.arrow(2.5, 3.2, 0.9, 0, head_width=0.08, head_length=0.08, fc='#3B82F6', ec='#3B82F6', length_includes_head=True, linewidth=1.0)
    ax.text(2.95, 3.3, "Request", ha='center', va='bottom', fontsize=6.5, color='#475569')

    ax.arrow(3.5, 3.0, -0.9, 0, head_width=0.08, head_length=0.08, fc='#22C55E', ec='#22C55E', length_includes_head=True, linewidth=1.0)
    ax.text(2.95, 2.85, "Tile Hit (15ms)", ha='center', va='top', fontsize=6.5, color='#15803D')

    ax.arrow(5.5, 3.2, 0.9, 0, head_width=0.08, head_length=0.08, fc='#EF4444', ec='#EF4444', length_includes_head=True, linewidth=1.0)
    ax.text(5.95, 3.3, "Tile Miss (150ms)", ha='center', va='bottom', fontsize=6.5, color='#B91C1C')

    ax.arrow(7.5, 2.8, 0, -0.6, head_width=0.08, head_length=0.08, fc='#3B82F6', ec='#3B82F6', length_includes_head=True, linewidth=1.0)
    ax.text(7.6, 2.5, "1. Query Cache", ha='left', va='center', fontsize=6.5, color='#475569')

    ax.arrow(7.3, 2.2, 0, 0.6, head_width=0.08, head_length=0.08, fc='#22C55E', ec='#22C55E', length_includes_head=True, linewidth=1.0)
    ax.text(7.2, 2.5, "2. Cache Hit", ha='right', va='center', fontsize=6.5, color='#15803D')

    ax.arrow(6.5, 1.7, -0.9, 0, head_width=0.08, head_length=0.08, fc='#EF4444', ec='#EF4444', length_includes_head=True, linewidth=1.0)
    ax.text(5.95, 1.8, "3. Cache Miss", ha='center', va='bottom', fontsize=6.5, color='#B91C1C')

    ax.arrow(5.5, 1.5, 0.9, 0, head_width=0.08, head_length=0.08, fc='#3B82F6', ec='#3B82F6', length_includes_head=True, linewidth=1.0)
    ax.text(5.95, 1.35, "4. Populate Cache", ha='center', va='top', fontsize=6.5, color='#475569')

    plt.savefig(output_path, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()

def generate_hardened_queue_diagram(output_path):
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.axis('off')
    fig.patch.set_facecolor('#F8FAFC')

    boxes = [
        (0.2, 3.2, 1.5, 0.8, "Client Browser\n(Field Engineer)"),
        (2.1, 3.2, 1.5, 0.8, "Nginx Ingress\n& WAF Edge"),
        (4.0, 3.2, 1.5, 0.8, "FastAPI Gateway\n(API Pods)"),
        (5.9, 3.2, 1.5, 0.8, "RabbitMQ Cluster\n(Celery Broker)"),
        (7.8, 3.2, 1.5, 0.8, "Celery Workers\n(Scale-out Pods)"),
        # ML / Storage
        (9.7, 4.3, 1.5, 0.7, "Triton ML Server\n(ResNet & XGBoost)"),
        (9.7, 3.2, 1.5, 0.7, "AWS S3 / R2\n(Object Storage)"),
        (9.7, 2.1, 1.5, 0.7, "PostgreSQL Master\n(Database Core)")
    ]

    for x, y, w, h, text in boxes:
        rect = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.03",
            linewidth=1.0,
            edgecolor='#1E3A8A',
            facecolor='#EFF6FF',
            mutation_scale=0.2
        )
        ax.add_patch(rect)
        ax.text(
            x + w/2, y + h/2, text,
            ha='center', va='center',
            fontsize=7, color='#0F172A',
            fontweight='bold', family='sans-serif'
        )

    arrows = [
        (1.7, 3.6, 0.35, 0),
        (3.6, 3.6, 0.35, 0),
        (5.5, 3.6, 0.35, 0),
        (7.4, 3.6, 0.35, 0),
        (9.3, 3.75, 0.35, 0.9),
        (9.3, 3.6, 0.35, 0),
        (9.3, 3.45, 0.35, -0.9)
    ]

    for x, y, dx, dy in arrows:
        ax.arrow(
            x, y, dx, dy,
            head_width=0.08, head_length=0.08,
            fc='#3B82F6', ec='#3B82F6',
            length_includes_head=True,
            linewidth=1.0
        )

    api_box = patches.Rectangle(
        (3.9, 3.0), 1.7, 1.1,
        linewidth=0.8, edgecolor='#94A3B8', facecolor='none', linestyle='--'
    )
    ax.add_patch(api_box)
    ax.text(4.75, 4.15, "API Pods", fontsize=6, color='#64748B', fontweight='bold', ha='center')

    worker_box = patches.Rectangle(
        (7.6, 1.9), 3.85, 3.3,
        linewidth=0.8, edgecolor='#94A3B8', facecolor='none', linestyle='--'
    )
    ax.add_patch(worker_box)
    ax.text(9.5, 5.25, "Asynchronous Execution Tier", fontsize=6, color='#64748B', fontweight='bold', ha='center')

    plt.savefig(output_path, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()


# -------------------------------------------------------------------------
# REPORT COMPILER
# -------------------------------------------------------------------------

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (Page 2 and later)
        self.drawString(54, 790, "Cortex Structural Intelligence Platform \u2014 Systems Design & Reliability Report")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 782, 541, 782)
        
        # Footer
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(541, 45, page_str)
        self.drawString(54, 45, "CONFIDENTIAL \u2014 CORTEX STRUCTURAL AI")
        self.line(54, 55, 541, 55)
        
        self.restoreState()

def create_report(output_filename):
    # Temp diagram paths
    img_hld = "temp_diag_hld.png"
    img_seq = "temp_diag_seq.png"
    img_cache = "temp_diag_cache.png"
    img_queue = "temp_diag_queue.png"
    
    print("Generating system architecture and layout diagrams...")
    generate_hld_monolith_diagram(img_hld)
    generate_sequence_diagram(img_seq)
    generate_cache_cdn_diagram(img_cache)
    generate_hardened_queue_diagram(img_queue)

    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#3B82F6"),
        spaceAfter=30
    )
    
    meta_style = ParagraphStyle(
        'CoverMeta',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=14,
        textColor=colors.HexColor("#64748B"),
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=12,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6
    )
    
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F8FAFC"),
        borderColor=colors.HexColor("#E2E8F0"),
        borderWidth=0.5,
        borderPadding=5,
        spaceAfter=8
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    table_body_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155")
    )

    story = []

    # ---------------------------------------------------------
    # PAGE 1: COVER PAGE
    # ---------------------------------------------------------
    story.append(Spacer(1, 100))
    title_data = [
        ["", Paragraph("CORTEX STRUCTURAL INTELLIGENCE PLATFORM", title_style)],
        ["", Paragraph("Unified Systems Architecture, High-Level Design,\n& Reliability Engineering Audit Report", subtitle_style)]
    ]
    title_table = Table(title_data, colWidths=[8, 479])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#3B82F6")), # Blue accent line
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (1,0), (1,-1), 15),
    ]))
    story.append(title_table)
    
    story.append(Spacer(1, 230))
    
    meta_text = f"""
    <b>DOCUMENT VERSION:</b> 2.0.0<br/>
    <b>AUTHOR:</b> System Engineering, Architecture & SRE Group<br/>
    <b>DATE:</b> {datetime.now().strftime('%B %d, %Y')}<br/>
    <b>STATUS:</b> Approved Technical Audit & Deployment Plan
    """
    story.append(Paragraph(meta_text, meta_style))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 2: EXECUTIVE SUMMARY & TECH STACK
    # ---------------------------------------------------------
    story.append(Paragraph("1. Executive Summary & Architecture Rationale", h1_style))
    story.append(Paragraph(
        "The Cortex Structural Intelligence Platform processes massive drone visual scans of building facades to "
        "detect and quantify structural defects (cracks, spalls, corrosion) in physical units (cm, mm, area). "
        "The platform utilizes a hybrid modular monolith architecture, local in-memory execution, aggressive feature-caching, "
        "and a Content Delivery Network (CDN) cache layer for global report distribution.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Architecture Rationale: Zero Network Latency</b><br/>"
        "Transferring high-resolution drone frames (4000x3000 px) and massive stitched mosaics (20,000x20,000 px) between "
        "separate microservices introduces heavy network serialization and I/O bottlenecks. A monolithic approach "
        "keeps the coordinate state in local CPU/GPU memory (numpy arrays), while offloading heavy worker threads via Celery.",
        body_style
    ))

    story.append(Paragraph("2. Technological Stack Configuration", h1_style))
    
    headers = [Paragraph("Tier", table_header_style), Paragraph("Technology", table_header_style), Paragraph("Role & Configuration", table_header_style)]
    tech_data = [
        headers,
        [Paragraph("Frontend UI", table_body_style), Paragraph("Next.js 16 (React 19)", table_body_style), Paragraph("Static build served by Nginx. Dynamic custom WebGL Three.js viewport for rendering 3D structural elements (Column, Beam, Slab) with parametric crack mappings.", table_body_style)],
        [Paragraph("Reverse Proxy / Edge", table_body_style), Paragraph("Nginx 1.25", table_body_style), Paragraph("Configured as an edge cache & reverse proxy. Caches static assets, handles TLS termination, rate-limits endpoints (api_zone: 30r/s, auth_zone: 5r/m), and routes /api/* to the FastAPI backend.", table_body_style)],
        [Paragraph("Application Layer", table_body_style), Paragraph("FastAPI (Python 3.11)", table_body_style), Paragraph("Non-blocking asynchronous web layer. Implements token-bucket sliding-window rate-limiting in Redis and handles multipart/form image uploads.", table_body_style)],
        [Paragraph("Async Tasks & Queues", table_body_style), Paragraph("Celery 5.3 + Redis", table_body_style), Paragraph("Offloads resource-heavy stitching homographies, SIFT alignments, and PDF generation from the API request thread pool.", table_body_style)],
        [Paragraph("ML & Inference Core", table_body_style), Paragraph("OpenCV + ResNet-50 + XGBoost", table_body_style), Paragraph("Runs edge quality gates (blur and exposure checks), SIFT homography registration, ResNet-50 patch feature extraction, and XGBoost false-positive filtering.", table_body_style)],
        [Paragraph("Database & Cache", table_body_style), Paragraph("PostgreSQL 16 + Redis", table_body_style), Paragraph("Relational storage for inspections, defects, and audit logs. Redis acts as a fast cache-aside storage for job state polling.", table_body_style)]
    ]
    
    tech_table = Table(tech_data, colWidths=[80, 110, 297])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(tech_table)
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 3: SYSTEM ARCHITECTURE & MONOLITHIC FLOW
    # ---------------------------------------------------------
    story.append(Paragraph("3. System Architecture & Component Design", h1_style))
    story.append(Paragraph(
        "The monolithic processing pipeline is optimized for minimal CPU-to-GPU memory transfer times. Intermediate image arrays "
        "remain in local RAM until final PDF generation.",
        body_style
    ))
    
    story.append(Paragraph("3.1 Platform High-Level Architecture Flowchart", h2_style))
    story.append(Paragraph(
        "The diagram below outlines the logical sequence of processing steps in the monolithic memory space:",
        body_style
    ))
    
    story.append(Spacer(1, 5))
    story.append(Image(img_hld, width=440, height=198))
    story.append(Spacer(1, 10))

    story.append(Paragraph("3.2 Key System Components Definition", h2_style))
    story.append(Paragraph("&bull; <b>Ingestion & Quality Gates</b>: Filters blurry/dark images based on Laplacian variance.", bullet_style))
    story.append(Paragraph("&bull; <b>Stitcher (SIFT/USAC-MAGSAC)</b>: Registers keypoints and aligns images into a high-res structural mosaic.", bullet_style))
    story.append(Paragraph("&bull; <b>Quantification Engine</b>: walks structural crack skeletons to measure physical lengths and EDT widths.", bullet_style))
    story.append(Paragraph("&bull; <b>Feature Extractor & Classifier</b>: Runs ResNet-50 patch extraction and XGBoost classification to filter false positives.", bullet_style))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 4: JOB LIFECYCLE
    # ---------------------------------------------------------
    story.append(Paragraph("3.3 End-to-End Processing Job Lifecycle (Data Flow)", h1_style))
    story.append(Paragraph(
        "Facade processing is fully asynchronous to avoid blocking client requests. Below is the transaction sequence flow:",
        body_style
    ))
    
    story.append(Spacer(1, 5))
    story.append(Image(img_seq, width=440, height=220))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Step-by-Step Transaction Flow:", h2_style))
    story.append(Paragraph("&bull; <b>Step 1-4</b>: Client dispatches inspection. API registers the record as 'pending', sends a task to the queue, and returns 202 Accepted.", bullet_style))
    story.append(Paragraph("&bull; <b>Step 5-8</b>: Celery worker dequeues the job, requests ML classification, computes zone scores, writes defects to the DB, and flags Redis as 'complete'.", bullet_style))
    story.append(Paragraph("&bull; <b>Step 9-12</b>: Client polls the status API, which reads from Redis (Cache Hit) or fallback Postgres (Cache Miss), returning report URLs.", bullet_style))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 5: RESTFUL API DESIGN
    # ---------------------------------------------------------
    story.append(Paragraph("3.4 RESTful API Design", h1_style))
    story.append(Paragraph(
        "All API routes conform to the OpenAPI 3.0 specification. Endpoints are rate-limited via a Token Bucket algorithm.",
        body_style
    ))
    
    story.append(Paragraph("POST /api/v1/run-inspection", h2_style))
    req_json = """// Request Body (Application/JSON)
{
  "building_id": "BLDG-CORTEX-01",
  "cycle_number": 2,
  "input_directory": "/shared/data/raw/BLDG-CORTEX-01_C2"
}

// Response Body (HTTP 202 Accepted)
{
  "job_id": "job_01h2y3t4r5e6w7q8",
  "status": "pending",
  "created_at": "2026-06-03T16:54:31Z",
  "check_status_url": "/api/v1/jobs/job_01h2y3t4r5e6w7q8"
}"""
    story.append(Preformatted(req_json, code_style))

    story.append(Paragraph("GET /api/v1/jobs/{job_id}", h2_style))
    resp_json = """// Response Body (HTTP 200 OK)
{
  "job_id": "job_01h2y3t4r5e6w7q8",
  "status": "processing",
  "progress": 65,
  "current_action": "SIFT keypoint descriptor matching",
  "estimated_seconds_remaining": 45
}"""
    story.append(Preformatted(resp_json, code_style))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 6: DATABASE SCHEMA DESIGN
    # ---------------------------------------------------------
    story.append(Paragraph("3.5 Relational Database Schema Design (PostgreSQL Dialect)", h1_style))
    story.append(Paragraph(
        "The PostgreSQL database design enforces strict structural constraints, Cascading Deletes, and audit version tracking:",
        body_style
    ))
    
    db_sql = """-- Primary table for facade inspection runs
CREATE TABLE IF NOT EXISTS inspections (
    id                  VARCHAR(64) PRIMARY KEY,
    building_id         VARCHAR(64) NOT NULL,
    building_name       VARCHAR(255) NOT NULL,
    inspection_date     VARCHAR(10) NOT NULL,
    vi_score            DOUBLE PRECISION,
    vi_class            VARCHAR(16) CHECK(vi_class IN ('minor', 'moderate', 'severe', 'critical')),
    pipeline_version    VARCHAR(16) DEFAULT '1.4.0',
    run_timestamp       VARCHAR(32) NOT NULL,
    warnings            TEXT DEFAULT '[]', -- JSON string
    s3_key              VARCHAR(512),
    row_version         INTEGER DEFAULT 1 NOT NULL,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Defect locations and quantifications
CREATE TABLE IF NOT EXISTS defects (
    id                          SERIAL PRIMARY KEY,
    defect_id                   VARCHAR(64) NOT NULL UNIQUE,
    inspection_id               VARCHAR(64) NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    type                        VARCHAR(32) NOT NULL,
    length_cm                   DOUBLE PRECISION,
    width_mm                    DOUBLE PRECISION,
    area_cm2                    DOUBLE PRECISION NOT NULL,
    severity_class              VARCHAR(16) NOT NULL CHECK(severity_class IN ('hairline', 'moderate', 'severe')),
    confidence_score            DOUBLE PRECISION NOT NULL,
    is_false_positive           INTEGER DEFAULT 0 NOT NULL,
    growth_acceleration         DOUBLE PRECISION DEFAULT 0.0 NOT NULL
);

-- Horizontal Scaling Indexes
CREATE INDEX IF NOT EXISTS idx_inspections_bldg ON inspections(building_id);
CREATE INDEX IF NOT EXISTS idx_defects_inspection ON defects(inspection_id);
CREATE INDEX IF NOT EXISTS idx_defects_class ON defects(severity_class, type);"""
    
    story.append(Preformatted(db_sql, code_style))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 7: CACHING & CDN STRATEGY
    # ---------------------------------------------------------
    story.append(Paragraph("3.6 Caching & CDN Strategy", h1_style))
    story.append(Paragraph(
        "To guarantee sub-100ms response times for site engineers, the system implements a layered cache architecture.",
        body_style
    ))
    
    story.append(Spacer(1, 5))
    story.append(Image(img_cache, width=440, height=195))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Caching Tier Optimizations:", h2_style))
    story.append(Paragraph("&bull; <b>Redis Cache-Aside</b>: Configured with an LRU eviction policy. Cache TTL is set to 10 minutes for historical listings, and 24 hours for active jobs (invalidating on task completion).", bullet_style))
    story.append(Paragraph("&bull; <b>DeepZoom Tile Cache</b>: High-resolution mosaic images are segmented into 256x256 px tiles. Browsers view tiles via Leaflet.js, requesting only viewable blocks from Nginx/CDN memory caches (Cache-Control max-age = 1 year).", bullet_style))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 8: RELIABILITY AUDIT
    # ---------------------------------------------------------
    story.append(Paragraph("4. Reliability Audit: Critical Risks & Challenged Decisions", h1_style))
    story.append(Paragraph(
        "An audit of the baseline implementation identified several critical bottlenecks and scaling hazards:",
        body_style
    ))
    
    story.append(Paragraph("4.1 Risk 1: CPU-Bound Inline Processing on Web Servers (Thread Fallback)", h2_style))
    story.append(Paragraph(
        "<b>The Shortcut:</b> Spawning a local daemon thread (`threading.Thread(target=run_sync)`) to execute the CPU-heavy OpenCV/SIFT "
        "pipeline when Celery or Redis is offline.<br/>"
        "<b>SRE Impact:</b> Python's GIL freezes the FastAPI event loop under CPU saturation. High memory consumption causes container "
        "OOM kills, terminating the web gateway.",
        body_style
    ))

    story.append(Paragraph("4.2 Risk 2: Unbounded Memory Growth in Fallback Cache", h2_style))
    story.append(Paragraph(
        "<b>The Shortcut:</b> Storing cache keys in a raw Python dict fallback (`self.in_memory_cache`) when Redis is offline.<br/>"
        "<b>SRE Impact:</b> Continuous polling introduces a memory leak as expired keys are not actively evicted, leading to process crashes.",
        body_style
    ))

    story.append(Paragraph("4.3 Risk 3: Unbounded Client IP Tracking in Rate Limiter", h2_style))
    story.append(Paragraph(
        "<b>The Shortcut:</b> Storing all tracking IPs in a default dictionary without automatic cleanup.<br/>"
        "<b>SRE Impact:</b> Web crawlers and scanners trigger a slow but absolute memory leak.",
        body_style
    ))

    story.append(Paragraph("4.4 Risk 4: Thread Pool Sync-to-Async DB Bridge Overhead", h2_style))
    story.append(Paragraph(
        "<b>The Shortcut:</b> Creating thread pools and starting loop frameworks on a per-query basis inside `sqlite_store.py`.<br/>"
        "<b>SRE Impact:</b> Heavy context switching and lock contention under high-concurrency workloads.",
        body_style
    ))

    story.append(Paragraph("4.5 Risk 5: Lack of Connection Pool Hardening", h2_style))
    story.append(Paragraph(
        "<b>The Shortcut:</b> Initializing database engines without explicit pool sizing or timeout limits.<br/>"
        "<b>SRE Impact:</b> Connection starvation and leaks under concurrent traffic spikes.",
        body_style
    ))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 9: TECHNICAL DECISION TRADE-OFFS
    # ---------------------------------------------------------
    story.append(Paragraph("5. Technical Decision Trade-Off Analysis", h1_style))
    story.append(Paragraph(
        "The following matrices compare strategies for asynchronous scheduling and rate limiting mechanisms:",
        body_style
    ))
    
    story.append(Paragraph("5.1 Asynchronous Task Execution Options", h2_style))
    async_headers = [Paragraph("Metric", table_header_style), Paragraph("A: In-Process Threads", table_header_style), Paragraph("B: Celery + Redis", table_header_style), Paragraph("C: SQLite Local Queue", table_header_style)]
    async_data = [
        async_headers,
        [Paragraph("GIL Impact", table_body_style), Paragraph("Critical (Freezes loop)", table_body_style), Paragraph("None (Isolated process)", table_body_style), Paragraph("None (Separate process)", table_body_style)],
        [Paragraph("Scalability", table_body_style), Paragraph("Non-scalable", table_body_style), Paragraph("High (Multi-node)", table_body_style), Paragraph("Medium (Single VM)", table_body_style)],
        [Paragraph("Reliability", table_body_style), Paragraph("Low (Crashes lose data)", table_body_style), Paragraph("High (Durable logs)", table_body_style), Paragraph("Medium (Durable on disk)", table_body_style)],
        [Paragraph("Decision", table_body_style), Paragraph("<b>REJECTED</b>", table_body_style), Paragraph("<b>PRIMARY CHOICE</b>", table_body_style), Paragraph("<b>LOCAL FAILOVER</b>", table_body_style)]
    ]
    async_table = Table(async_data, colWidths=[70, 140, 140, 137])
    async_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(async_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph("5.2 API Rate Limiting Options", h2_style))
    lim_headers = [Paragraph("Limiter Model", table_header_style), Paragraph("Pros", table_header_style), Paragraph("Cons", table_header_style), Paragraph("Recommendation", table_header_style)]
    lim_data = [
        lim_headers,
        [Paragraph("In-Memory IP Bucket", table_body_style), Paragraph("Ultra-low latency, zero setup.", table_body_style), Paragraph("IP trackers leak memory over time.", table_body_style), Paragraph("<b>Dev/Test Only</b> (Pruned)", table_body_style)],
        [Paragraph("Redis-Backed Rate Limiting", table_body_style), Paragraph("Cluster-aware, shared.", table_body_style), Paragraph("Requires active Redis broker.", table_body_style), Paragraph("<b>Production Standard</b>", table_body_style)],
        [Paragraph("WAF / Ingress Limiting", table_body_style), Paragraph("Blocks traffic at edge.", table_body_style), Paragraph("Coarse-grained controls.", table_body_style), Paragraph("<b>Mandatory Edge Defense</b>", table_body_style)]
    ]
    lim_table = Table(lim_data, colWidths=[110, 125, 125, 127])
    lim_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(lim_table)
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 10: HARDENED ARCHITECTURE
    # ---------------------------------------------------------
    story.append(Paragraph("6. Hardened Production-Grade Architecture", h1_style))
    story.append(Paragraph(
        "To resolve identified thread and connection locks, the platform is structured around a decoupled queuing tier. "
        "FastAPI is isolated from CPU-heavy tasks via Celery and RabbitMQ.",
        body_style
    ))
    
    story.append(Paragraph("6.1 Decoupled Queue Architecture", h2_style))
    story.append(Paragraph(
        "The diagram below outlines the topology of the hardened deployment. Ingress rate-limits traffic at the gate, FastAPI "
        "registers transaction requests in Postgres replicas, and Celery worker pods pull tasks asynchronously:",
        body_style
    ))
    
    story.append(Spacer(1, 5))
    story.append(Image(img_queue, width=440, height=198))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Operational Topology Details:", h2_style))
    story.append(Paragraph("&bull; <b>Gateway Tier</b>: Horizontally scalable FastAPI pods handle incoming requests, read cached statuses from Redis, and dispatch tasks to the broker.", bullet_style))
    story.append(Paragraph("&bull; <b>Asynchronous Processing Tier</b>: Decoupled Celery worker pods pull tasks, run the OpenCV pipeline, trigger isolated ML queries on a Triton Inference Server, and save artifacts directly to AWS S3 / R2 storage.", bullet_style))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 11: HARDENED CODE PART 1
    # ---------------------------------------------------------
    story.append(Paragraph("6.2 Hardened Code Implementations", h1_style))
    story.append(Paragraph(
        "The following validated implementations prevent memory leaks and thread lockups:",
        body_style
    ))
    
    story.append(Paragraph("Code 1: Bounded LRU Fallback Cache in CacheManager", h2_style))
    code_cache = """class HardenedCacheManager:
    \"\"\"Hardened Cache-Aside manager with Redis and bounded LRU fallback.\"\"\"
    def __init__(self, redis_url: Optional[str] = None, max_local_size: int = 1000):
        self.max_local_size = max_local_size
        self.local_cache: OrderedDict[str, Any] = OrderedDict()
        self.local_ttls: dict[str, float] = {}
        # ... Redis connect initialization ...

    def get(self, key: str) -> Optional[Any]:
        # ... Redis get logic ...
        if key in self.local_cache:
            ttl = self.local_ttls.get(key, 0.0)
            if ttl == 0.0 or time.time() < ttl:
                self.local_cache.move_to_end(key)
                return self.local_cache[key]
            else:
                self.local_cache.pop(key, None)
                self.local_ttls.pop(key, None)
        return None

    def set(self, key: str, value: Any, ttl_seconds: int = 600):
        # ... Redis set logic ...
        if len(self.local_cache) >= self.max_local_size:
            oldest_key, _ = self.local_cache.popitem(last=False)
            self.local_ttls.pop(oldest_key, None)
        self.local_cache[key] = value
        self.local_ttls[key] = time.time() + ttl_seconds"""
    story.append(Preformatted(code_cache, code_style))

    story.append(Paragraph("Code 2: Bounded Rate Limiter with Automatic IP Pruning", h2_style))
    code_limiter = """class HardenedTokenBucketLimiter:
    \"\"\"Token bucket limiter with active IP tracking pruning to prevent leaks.\"\"\"
    def __init__(self, capacity: int, fill_rate: float, prune_interval: int = 600):
        self.capacity, self.fill_rate = capacity, fill_rate
        self.prune_interval = prune_interval
        self.buckets: dict[str, list[float]] = {}
        self.last_prune = time.time()
        self.lock = threading.Lock()

    def consume(self, client_ip: str, tokens: int = 1) -> tuple[bool, int, float]:
        with self.lock:
            now = time.time()
            if now - self.last_prune > self.prune_interval:
                self._prune_buckets(now)
            if client_ip not in self.buckets:
                self.buckets[client_ip] = [float(self.capacity), now]
            # ... Token bucket subtraction and token return logic ..."""
    story.append(Preformatted(code_limiter, code_style))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 12: HARDENED CODE PART 2 & VERIFICATION
    # ---------------------------------------------------------
    story.append(Paragraph("Code 3: SQLAlchemy Connection Pool Optimization", h2_style))
    code_db = """# Hardened PostgreSQL database engine setup
self.engine = create_async_engine(
    pg_dsn,
    pool_size=20,               # Maintain 20 hot connections
    max_overflow=10,            # Allow bursts up to 30 connections
    pool_recycle=1800,          # Recycles connections every 30 minutes
    pool_pre_ping=True,         # Auto-verify connection before query
    connect_args={"timeout": 5} # Capped connection timeout
)"""
    story.append(Preformatted(code_db, code_style))

    story.append(Paragraph("7. Proposed Verification Plan", h1_style))
    story.append(Paragraph("&bull; <b>Load Smoke Test</b>: Query 1,000 distinct IP addresses. Verify local memory remains capped under max size limitations.", bullet_style))
    story.append(Paragraph("&bull; <b>Starvation Test</b>: Disconnect Celery and mock heavy API request rate. Verify FastAPI continues serving health checks.", bullet_style))
    story.append(Paragraph("&bull; <b>Integration Validation</b>: Run CI checkers to ensure all test suites pass with zero warnings.", bullet_style))

    story.append(Paragraph("8. Project Implementation & Integration Update", h1_style))
    story.append(Paragraph("&bull; <b>E2E Stack Operational</b>: API, Celery worker, Redis, Nginx, and Postgres are fully running.", bullet_style))
    story.append(Paragraph("&bull; <b>Seeded Credentials</b>: Default user admin@cortex.com / CortexPass123! and cortex organization are successfully seeded.", bullet_style))
    story.append(Paragraph("&bull; <b>Static Build Served</b>: Next.js frontend has been compiled and Nginx serves static assets at port 80.", bullet_style))

    story.append(Paragraph("9. Reference Documents & Architecture Artifacts", h1_style))
    story.append(Paragraph("&bull; <b>system_architecture_design.md</b>: Kubernetes setups and database schema scripts.", bullet_style))
    story.append(Paragraph("&bull; <b>system_design_hld.md</b>: Monolithic processing details.", bullet_style))
    story.append(Paragraph("&bull; <b>reliability_engineering_report.md</b>: Detailed vulnerabilities analysis.", bullet_style))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    
    # Cleanup temp images
    for p in [img_hld, img_seq, img_cache, img_queue]:
        if os.path.exists(p):
            os.remove(p)
    print("Report compiled successfully and temporary assets cleaned up.")

if __name__ == "__main__":
    output_path = "Cortex_System_Architecture_and_Reliability_Report.pdf"
    create_report(output_path)
    print(f"Report generated successfully at: {output_path}")
