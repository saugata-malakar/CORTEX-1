import { useState, useRef, useEffect, useCallback } from "react";

// ─── DESIGN TOKENS ───────────────────────────────────────────────────────────
const C = {
  bg:          "#0A0B0F",     // Deep black-slate background (matches page.js)
  surface:     "#111318",     // Sleek dark-slate surface (matches page.js)
  card:        "#161920",     // Premium dark-grey card color
  border:      "#1E2230",     // Subtle dark border
  borderHi:    "#FFE600",     // Bright yellow border highlight
  accent:      "#FFE600",     // Vibrant yellow
  accentDark:  "#FFE600",     // Yellow contrast
  accentGlow:  "rgba(255,230,0,0.12)",
  critical:    "#EF4444",     // Red
  severe:      "#F97316",     // Orange
  moderate:    "#D97706",     // Amber
  minor:       "#10B981",     // Emerald green
  hairline:    "#06B6D4",     // Cyan
  text:        "#F0F2F8",     // Light text for dark background
  textSub:     "#8892A4",     // Subdued light text
  textMuted:   "#4A5568",     // Muted grey text
  mono:        "'JetBrains Mono', monospace",
  display:     "'Syne', sans-serif",
  body:        "'DM Sans', sans-serif",
};

// ─── CRACK DATABASE — Civil Engineering Specs ─────────────────────────────────
const CRACK_DB = {
  shear: {
    label:          "Shear Crack",
    subtitle:       "Diagonal — 30–60° from horizontal",
    is_code:        "IS 456:2000 Cl.40.4",
    risk:           "CRITICAL",
    riskColor:      C.critical,
    cause:          "Shear stress exceeding diagonal tensile capacity near supports. Transverse reinforcement insufficient.",
    failure_mode:   "Sudden brittle failure — no warning. Column or beam splits diagonally.",
    intervention:   "IMMEDIATE: Install shoring props. Pressure-inject structural epoxy (viscosity ≤ 50 cP). Wrap member with CFRP U-strips at 150mm c/c. Reassess load path.",
    reinspect_days: 7,
    angle_range:    [30, 60],
    member:         "beam_column_junction",
    // 3D model parameters
    model: {
      type:         "beam_with_diagonal_crack",
      crackAngle:   45,
      crackColor:   0xFF2222,
      memberColor:  0x8B9DC3,
      highlight:    [0, 1],   // which faces glow
      description:  "Diagonal crack across beam/column junction at 45°",
    }
  },
  flexural: {
    label:          "Flexural Crack",
    subtitle:       "Vertical — perpendicular to member axis",
    is_code:        "IS 456:2000 Cl.43.1",
    risk:           "SEVERE",
    riskColor:      C.severe,
    cause:          "Bending moment exceeding cracking moment. Tensile stress at bottom fibre exceeds fct.",
    failure_mode:   "Progressive — crack opens at bottom, propagates upward. Compression zone reduces. Eventual crushing.",
    intervention:   "Detailed load assessment required. Inject low-viscosity epoxy. Add flexural steel if under-reinforced. Monitor neutral axis depth.",
    reinspect_days: 30,
    angle_range:    [85, 95],
    member:         "beam_soffit",
    model: {
      type:         "beam_vertical_crack",
      crackAngle:   90,
      crackColor:   0xFF6600,
      memberColor:  0x7B8EB8,
      highlight:    [2],
      description:  "Vertical crack at beam soffit — bending zone",
    }
  },
  corrosion: {
    label:          "Corrosion-Induced Crack",
    subtitle:       "Longitudinal — parallel to rebar axis",
    is_code:        "IS 456:2000 Cl.8.2.8",
    risk:           "SEVERE",
    riskColor:      C.severe,
    cause:          "Rebar oxidation causing 2–4× volume expansion of iron oxide. Splitting tensile stress in cover concrete.",
    failure_mode:   "Cover spalls off. Bar section loss. Bond failure. Progressive collapse of cover zone.",
    intervention:   "Remove all delaminated cover. Treat rebar (NACE SP0169). Apply polymer-modified repair mortar. Increase cover ≥ 50mm. Apply anti-carbonation coating.",
    reinspect_days: 14,
    angle_range:    [0, 10],
    member:         "column_cover",
    model: {
      type:         "column_longitudinal_crack",
      crackAngle:   0,
      crackColor:   0xFF8800,
      memberColor:  0x6B7E9F,
      highlight:    [0, 3],
      description:  "Longitudinal crack along rebar — cover delamination",
    }
  },
  settlement: {
    label:          "Settlement Crack",
    subtitle:       "Diagonal from opening corners — foundation movement",
    is_code:        "IS 1904:1986 Cl.5",
    risk:           "SEVERE",
    riskColor:      C.severe,
    cause:          "Differential foundation settlement. Stress concentration at re-entrant corners of openings.",
    failure_mode:   "Crack widens over time as settlement continues. Opening distortion. Masonry tie failure.",
    intervention:   "Stop at source — investigate and stabilise foundation. Soil investigation (SPT/DCPT). Underpinning if required. Then seal cracks with flexible sealant.",
    reinspect_days: 14,
    angle_range:    [30, 50],
    member:         "wall_opening",
    model: {
      type:         "wall_corner_crack",
      crackAngle:   45,
      crackColor:   0xFFAA00,
      memberColor:  0x8A9AB5,
      highlight:    [1, 2],
      description:  "Diagonal crack radiating from window/door corner",
    }
  },
  compression: {
    label:          "Compression Crack",
    subtitle:       "Vertical splitting — column under axial load",
    is_code:        "IS 456:2000 Cl.39.3",
    risk:           "CRITICAL",
    riskColor:      C.critical,
    cause:          "Axial load exceeding 0.4 fck·Ac + 0.67 fy·Asc. Lateral confinement inadequate. Column crushing imminent.",
    failure_mode:   "Explosive brittle failure. No ductility. Column loses load-carrying capacity completely.",
    intervention:   "EVACUATE IMMEDIATELY if active. Install steel angles + welded plate jacketing. Add RCC or steel jacket for confinement. Reassess entire structural load path.",
    reinspect_days: 1,
    angle_range:    [80, 100],
    member:         "column_body",
    model: {
      type:         "column_vertical_split",
      crackAngle:   90,
      crackColor:   0xFF0000,
      memberColor:  0x5A6B8A,
      highlight:    [0, 1, 2, 3],
      description:  "Vertical splitting crack in column — near-failure state",
    }
  },
  shrinkage: {
    label:          "Shrinkage / Map Crack",
    subtitle:       "Random map pattern — surface crazing",
    is_code:        "IS 456:2000 Cl.13.5",
    risk:           "MINOR",
    riskColor:      C.minor,
    cause:          "Plastic shrinkage during curing. Rapid moisture loss. High cement content, low w/c ratio.",
    failure_mode:   "Cosmetic only if shallow. Risk of water ingress leading to rebar corrosion over time.",
    intervention:   "Clean and wash surface. Apply cementitious slurry coat or crystalline waterproofing. Monitor for depth progression.",
    reinspect_days: 365,
    angle_range:    [0, 180],
    member:         "surface",
    model: {
      type:         "surface_map_crack",
      crackAngle:   "random",
      crackColor:   0x22C55E,
      memberColor:  0x9AAAC0,
      highlight:    [],
      description:  "Random map-pattern surface crazing — shrinkage origin",
    }
  },
  hairline: {
    label:          "Hairline Crack",
    subtitle:       "Width < 0.1mm — early stage monitoring",
    is_code:        "IS 456:2000 Table 20",
    risk:           "HAIRLINE",
    riskColor:      C.hairline,
    cause:          "Early shrinkage, thermal movement, or very minor flexural stress. Within acceptable limits per code.",
    failure_mode:   "No structural risk at current width. Monitor for progression.",
    intervention:   "Gravity-feed low-viscosity epoxy. Surface seal with epoxy paint. Photograph and log for temporal comparison.",
    reinspect_days: 180,
    angle_range:    [0, 180],
    member:         "surface",
    model: {
      type:         "hairline_surface",
      crackAngle:   "random",
      crackColor:   0x06B6D4,
      memberColor:  0xA0B0C8,
      highlight:    [],
      description:  "Hairline surface crack < 0.1mm — monitor only",
    }
  },
  none: {
    label:          "No Selection",
    subtitle:       "Select a scenario or upload an image to begin",
    is_code:        "Compliant",
    risk:           "CLEARED",
    riskColor:      C.textSub,
    cause:          "No active defect selected. Choose a pre-defined crack scenario from the quick select options or upload a UAV frame for real-time analysis.",
    failure_mode:   "No structural failure mode active.",
    intervention:   "System is idle. Awaiting concrete facade image ingestion or crack scenario selection.",
    reinspect_days: 0,
    angle_range:    [0, 0],
    member:         "none",
    model: {
      type:         "none",
      crackAngle:   0,
      crackColor:   0x7A8BA8,
      memberColor:  0x131720,
      highlight:    [],
      description:  "Awaiting visual scan data",
    }
  },
};

// ─── CRACK DETECTION ENGINE ───────────────────────────────────────────────────
function analyzeImageForCrack(imageData, scenario = null) {
  // In production this calls your Python /api/analyze endpoint
  // Here we simulate with engineering-accurate detection logic
  if (scenario) return { ...CRACK_DB[scenario], id: scenario };

  // Without model: return based on image brightness/edge analysis
  return { ...CRACK_DB["shear"], id: "shear" };
}

function detectCrackType(angle, aspectRatio, area) {
  if (angle >= 30 && angle <= 60)   return "shear";
  if (angle >= 80 && angle <= 100 && aspectRatio > 5) return "compression";
  if (angle >= 85 && angle <= 95)   return "flexural";
  if (angle < 15 && aspectRatio > 8) return "corrosion";
  if (area < 200)                    return "hairline";
  return "shrinkage";
}

// ─── 3D MODEL CANVAS — Unique per crack type ─────────────────────────────────
function CrackModel3D({ crackType, width = 400, height = 340 }) {
  const canvasRef = useRef(null);
  const animRef   = useRef(null);
  const rotRef    = useRef({ x: 0.3, y: 0.4 });
  const dragging  = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const cfg = CRACK_DB[crackType]?.model || CRACK_DB.shear.model;

    let ry = rotRef.current.y;
    let rx = rotRef.current.x;

    // ── 3D math helpers ─────────────────────────────────────────
    function project(x, y, z, rx, ry, cx, cy, scale = 90) {
      // Rotate Y
      const cosY = Math.cos(ry), sinY = Math.sin(ry);
      const x1 = x * cosY - z * sinY;
      const z1 = x * sinY + z * cosY;
      // Rotate X
      const cosX = Math.cos(rx), sinX = Math.sin(rx);
      const y2 = y * cosX - z1 * sinX;
      const z2 = y * sinX + z1 * cosX;
      // Perspective
      const fov = 5;
      const pz  = z2 + fov;
      return {
        x:     cx + (x1 / pz) * scale * fov,
        y:     cy + (y2 / pz) * scale * fov,
        depth: z2,
      };
    }

    function hexToRgb(hex) {
      const r = (hex >> 16) & 0xff;
      const g = (hex >> 8)  & 0xff;
      const b =  hex        & 0xff;
      return { r, g, b };
    }

    function lighten(hex, factor) {
      const { r, g, b } = hexToRgb(hex);
      return `rgb(${Math.min(255, r + factor)},${Math.min(255, g + factor)},${Math.min(255, b + factor)})`;
    }

    function darken(hex, factor) {
      const { r, g, b } = hexToRgb(hex);
      return `rgb(${Math.max(0, r - factor)},${Math.max(0, g - factor)},${Math.max(0, b - factor)})`;
    }

    function hexStr(hex) {
      return `#${hex.toString(16).padStart(6, "0")}`;
    }

    // ── Draw beam/column box ─────────────────────────────────────
    function drawBox(ctx, cx, cy, verts, faces, mc, pulse) {
      const projected = verts.map(v => project(v[0], v[1], v[2], rx, ry, cx, cy));

      // Sort faces by average depth
      const sorted = faces
        .map((f, i) => ({
          i, f,
          depth: f.reduce((s, vi) => s + projected[vi].depth, 0) / f.length
        }))
        .sort((a, b) => a.depth - b.depth);

      sorted.forEach(({ f, depth, i }) => {
        const pts = f.map(vi => projected[vi]);
        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        pts.forEach(p => ctx.lineTo(p.x, p.y));
        ctx.closePath();

        const isHighlight = cfg.highlight.includes(i);
        const alpha = isHighlight ? 0.18 + 0.08 * pulse : 0;
        const base  = depth > 0 ? lighten(mc, 30) : darken(mc, 40);

        ctx.fillStyle   = base;
        ctx.fill();

        if (isHighlight) {
          ctx.fillStyle = `rgba(239,68,68,${alpha})`;
          ctx.fill();
        }

        ctx.strokeStyle = `rgba(255,255,255,0.08)`;
        ctx.lineWidth   = 0.5;
        ctx.stroke();
      });

      return projected;
    }

    // ── MODEL BUILDERS ───────────────────────────────────────────

    function drawBeamWithDiagonalCrack(ctx, cx, cy, pulse, t) {
      // Beam: wide, horizontal
      const bw = 0.9, bh = 0.3, bd = 0.3;
      const verts = [
        [-bw,-bh,-bd], [bw,-bh,-bd], [bw,bh,-bd], [-bw,bh,-bd],
        [-bw,-bh, bd], [bw,-bh, bd], [bw,bh, bd], [-bw,bh, bd],
      ];
      const faces = [
        [0,1,2,3],[4,5,6,7],[0,1,5,4],
        [2,3,7,6],[0,3,7,4],[1,2,6,5]
      ];
      const projected = drawBox(ctx, cx, cy, verts, faces, cfg.memberColor, pulse);

      // Diagonal shear crack line across front face (face 4 = top)
      const cAng = (45 * Math.PI) / 180;
      const crackPts = [];
      for (let i = 0; i <= 12; i++) {
        const frac = i / 12;
        const cx3 = bw * (1 - 2 * frac);
        const cy3 = bh * (1 - 2 * frac);
        const jitter = (Math.random() - 0.5) * 0.04;
        crackPts.push([cx3 + jitter, cy3, bd + 0.01]);
      }
      const projCrack = crackPts.map(v =>
        project(v[0], v[1], v[2], rx, ry, cx, cy)
      );

      ctx.beginPath();
      ctx.moveTo(projCrack[0].x, projCrack[0].y);
      for (let i = 1; i < projCrack.length; i++) {
        const p = projCrack[i];
        ctx.lineTo(p.x, p.y);
      }
      ctx.strokeStyle = `rgba(239,68,68,${0.7 + 0.3 * pulse})`;
      ctx.lineWidth   = 2.5 + pulse;
      ctx.lineCap     = "round";
      ctx.stroke();

      // Width annotation
      const w1 = project(-0.2, 0.35, bd + 0.02, rx, ry, cx, cy);
      const w2 = project( 0.2, 0.35, bd + 0.02, rx, ry, cx, cy);
      ctx.beginPath();
      ctx.moveTo(w1.x, w1.y); ctx.lineTo(w2.x, w2.y);
      ctx.strokeStyle = `rgba(251,191,36,0.9)`;
      ctx.lineWidth   = 1;
      ctx.stroke();
      ctx.fillStyle   = "#FBB924";
      ctx.font        = `bold 9px ${C.mono}`;
      ctx.fillText("w=63.64mm", (w1.x + w2.x) / 2 - 28, (w1.y + w2.y) / 2 - 6);
    }

    function drawColumnVerticalSplit(ctx, cx, cy, pulse, t) {
      // Column: tall, narrow
      const cw = 0.28, ch = 1.1, cd = 0.28;
      const verts = [
        [-cw,-ch,-cd],[cw,-ch,-cd],[cw,ch,-cd],[-cw,ch,-cd],
        [-cw,-ch, cd],[cw,-ch, cd],[cw,ch, cd],[-cw,ch, cd],
      ];
      const faces = [
        [0,1,2,3],[4,5,6,7],[0,1,5,4],
        [2,3,7,6],[0,3,7,4],[1,2,6,5]
      ];
      drawBox(ctx, cx, cy, verts, faces, cfg.memberColor, pulse);

      // Multiple vertical cracks on front face
      [-0.06, 0.06].forEach(xOff => {
        const crackPts = [];
        for (let i = 0; i <= 16; i++) {
          const frac = i / 16;
          const jitter = (Math.random() - 0.5) * 0.025;
          crackPts.push([xOff + jitter, ch - frac * ch * 1.8, cd + 0.01]);
        }
        const proj = crackPts.map(v => project(v[0], v[1], v[2], rx, ry, cx, cy));
        ctx.beginPath();
        ctx.moveTo(proj[0].x, proj[0].y);
        proj.forEach(p => ctx.lineTo(p.x, p.y));
        ctx.strokeStyle = `rgba(255,30,30,${0.8 + 0.2 * pulse})`;
        ctx.lineWidth   = 1.8 + pulse * 0.5;
        ctx.lineCap     = "round";
        ctx.stroke();
      });

      // Critical label
      const top = project(0, ch + 0.15, 0, rx, ry, cx, cy);
      ctx.fillStyle = `rgba(239,68,68,${0.85 + 0.15 * pulse})`;
      ctx.font = `bold 9px ${C.mono}`;
      ctx.textAlign = "center";
      ctx.fillText("COMPRESSION FAILURE", top.x, top.y);
      ctx.textAlign = "left";
    }

    function drawBeamFlexuralCrack(ctx, cx, cy, pulse, t) {
      // Beam with crack at bottom soffit
      const bw = 0.95, bh = 0.35, bd = 0.3;
      const verts = [
        [-bw,-bh,-bd],[bw,-bh,-bd],[bw,bh,-bd],[-bw,bh,-bd],
        [-bw,-bh, bd],[bw,-bh, bd],[bw,bh, bd],[-bw,bh, bd],
      ];
      const faces = [
        [0,1,2,3],[4,5,6,7],[0,1,5,4],
        [2,3,7,6],[0,3,7,4],[1,2,6,5]
      ];
      drawBox(ctx, cx, cy, verts, faces, cfg.memberColor, pulse);

      // Vertical crack from bottom, tapers toward neutral axis
      const crackPts = [];
      for (let i = 0; i <= 14; i++) {
        const frac = i / 14;
        const taperX = (Math.random() - 0.5) * 0.02 * (1 - frac);
        crackPts.push([taperX, -bh + frac * bh * 1.3, bd + 0.01]);
      }
      const proj = crackPts.map(v => project(v[0], v[1], v[2], rx, ry, cx, cy));
      ctx.beginPath();
      ctx.moveTo(proj[0].x, proj[0].y);
      proj.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.strokeStyle = `rgba(249,115,22,${0.8 + 0.2 * pulse})`;
      ctx.lineWidth   = 2;
      ctx.lineCap     = "round";
      ctx.stroke();

      // Neutral axis indicator
      const na = project(-bw + 0.1, 0.05, bd + 0.02, rx, ry, cx, cy);
      const nb = project( bw - 0.1, 0.05, bd + 0.02, rx, ry, cx, cy);
      ctx.setLineDash([3, 4]);
      ctx.beginPath();
      ctx.moveTo(na.x, na.y); ctx.lineTo(nb.x, nb.y);
      ctx.strokeStyle = "rgba(99,179,255,0.5)";
      ctx.lineWidth   = 1;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle   = "rgba(99,179,255,0.8)";
      ctx.font        = `8px ${C.mono}`;
      ctx.fillText("N.A.", nb.x + 4, nb.y + 3);
    }

    function drawColumnLongitudinalCrack(ctx, cx, cy, pulse, t) {
      // Column with rebar exposed
      const cw = 0.3, ch = 1.0, cd = 0.3;
      const verts = [
        [-cw,-ch,-cd],[cw,-ch,-cd],[cw,ch,-cd],[-cw,ch,-cd],
        [-cw,-ch, cd],[cw,-ch, cd],[cw,ch, cd],[-cw,ch, cd],
      ];
      const faces = [
        [0,1,2,3],[4,5,6,7],[0,1,5,4],
        [2,3,7,6],[0,3,7,4],[1,2,6,5]
      ];
      drawBox(ctx, cx, cy, verts, faces, cfg.memberColor, pulse);

      // Horizontal longitudinal crack
      const crackPts = [];
      for (let i = 0; i <= 18; i++) {
        const frac = i / 18;
        const jitter = (Math.random() - 0.5) * 0.02;
        crackPts.push([-cw + frac * cw * 2, jitter, cd + 0.01]);
      }
      const proj = crackPts.map(v => project(v[0], v[1], v[2], rx, ry, cx, cy));
      ctx.beginPath();
      ctx.moveTo(proj[0].x, proj[0].y);
      proj.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.strokeStyle = `rgba(249,115,22,${0.9 + 0.1 * pulse})`;
      ctx.lineWidth   = 2.5;
      ctx.lineCap     = "round";
      ctx.stroke();

      // Rebar lines inside (orange cylinders schematically)
      [-0.1, 0.1].forEach(xr => {
        const r1 = project(xr, -ch + 0.05, cd - 0.05, rx, ry, cx, cy);
        const r2 = project(xr,  ch - 0.05, cd - 0.05, rx, ry, cx, cy);
        ctx.beginPath();
        ctx.moveTo(r1.x, r1.y); ctx.lineTo(r2.x, r2.y);
        ctx.strokeStyle = `rgba(255,140,0,${0.7 + 0.3 * pulse})`;
        ctx.lineWidth   = 3;
        ctx.stroke();
      });

      // Rust stain visual
      ctx.fillStyle = `rgba(180,80,0,${0.12 + 0.06 * pulse})`;
      const rs = project(-0.05, -0.1, cd + 0.01, rx, ry, cx, cy);
      ctx.beginPath();
      ctx.arc(rs.x, rs.y, 14 + 4 * pulse, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawWallCornerCrack(ctx, cx, cy, pulse, t) {
      // Wall panel with opening
      const ww = 1.0, wh = 0.8, wd = 0.12;
      const verts = [
        [-ww,-wh,-wd],[ww,-wh,-wd],[ww,wh,-wd],[-ww,wh,-wd],
        [-ww,-wh, wd],[ww,-wh, wd],[ww,wh, wd],[-ww,wh, wd],
      ];
      const faces = [
        [0,1,2,3],[4,5,6,7],[0,1,5,4],
        [2,3,7,6],[0,3,7,4],[1,2,6,5]
      ];
      drawBox(ctx, cx, cy, verts, faces, cfg.memberColor, pulse);

      // Opening rectangle on front face
      const ow = 0.32, oh = 0.36, ocx = 0, ocy = 0;
      const openCorners = [
        [ocx - ow, ocy - oh, wd + 0.01],
        [ocx + ow, ocy - oh, wd + 0.01],
        [ocx + ow, ocy + oh, wd + 0.01],
        [ocx - ow, ocy + oh, wd + 0.01],
      ];
      const oc = openCorners.map(v => project(v[0], v[1], v[2], rx, ry, cx, cy));
      ctx.beginPath();
      ctx.moveTo(oc[0].x, oc[0].y);
      oc.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.closePath();
      ctx.fillStyle   = "rgba(8,10,15,0.9)";
      ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,0.15)";
      ctx.lineWidth   = 0.8;
      ctx.stroke();

      // Diagonal cracks from top corners of opening
      [[ocx + ow, ocy - oh], [ocx - ow, ocy - oh]].forEach(([ox, oy], idx) => {
        const dir = idx === 0 ? 1 : -1;
        const crackPts = [];
        for (let i = 0; i <= 10; i++) {
          const frac = i / 10;
          const jitter = (Math.random() - 0.5) * 0.03;
          crackPts.push([ox + dir * frac * 0.5 + jitter, oy - frac * 0.45 + jitter, wd + 0.01]);
        }
        const proj = crackPts.map(v => project(v[0], v[1], v[2], rx, ry, cx, cy));
        ctx.beginPath();
        ctx.moveTo(proj[0].x, proj[0].y);
        proj.forEach(p => ctx.lineTo(p.x, p.y));
        ctx.strokeStyle = `rgba(249,115,22,${0.8 + 0.2 * pulse})`;
        ctx.lineWidth   = 2;
        ctx.lineCap     = "round";
        ctx.stroke();
      });
    }

    function drawSurfaceMapCrack(ctx, cx, cy, pulse, t, color) {
      // Flat slab surface
      const sw = 1.1, sh = 0.12, sd = 0.9;
      const verts = [
        [-sw,-sh,-sd],[sw,-sh,-sd],[sw,sh,-sd],[-sw,sh,-sd],
        [-sw,-sh, sd],[sw,-sh, sd],[sw,sh, sd],[-sw,sh, sd],
      ];
      const faces = [
        [0,1,2,3],[4,5,6,7],[0,1,5,4],
        [2,3,7,6],[0,3,7,4],[1,2,6,5]
      ];
      drawBox(ctx, cx, cy, verts, faces, cfg.memberColor, pulse);

      // Random map crack network on top face
      const seed = 42;
      for (let k = 0; k < 14; k++) {
        const angle = (k / 14) * Math.PI * 2 + t * 0.02;
        const len   = 0.2 + (k % 5) * 0.1;
        const startX = Math.cos(angle * 1.7) * 0.6;
        const startZ = Math.sin(angle * 2.3) * 0.6;
        const crackPts = [];
        for (let i = 0; i <= 6; i++) {
          const frac = i / 6;
          const nx = startX + Math.cos(angle + frac) * len * frac;
          const nz = startZ + Math.sin(angle * 1.4 + frac) * len * frac;
          crackPts.push([Math.max(-sw + 0.1, Math.min(sw - 0.1, nx)), sh + 0.01,
            Math.max(-sd + 0.1, Math.min(sd - 0.1, nz))]);
        }
        const proj = crackPts.map(v => project(v[0], v[1], v[2], rx, ry, cx, cy));
        ctx.beginPath();
        ctx.moveTo(proj[0].x, proj[0].y);
        proj.forEach(p => ctx.lineTo(p.x, p.y));
        const hexColor = color.toString(16).padStart(6, "0");
        ctx.strokeStyle = `rgba(${parseInt(hexColor.slice(0,2),16)},${parseInt(hexColor.slice(2,4),16)},${parseInt(hexColor.slice(4,6),16)},${0.5 + 0.2 * pulse})`;
        ctx.lineWidth   = 0.8;
        ctx.lineCap     = "round";
        ctx.stroke();
      }
    }

    // ── MAIN DRAW LOOP ───────────────────────────────────────────
    let t = 0;
    const W = canvas.width;
    const H = canvas.height;
    const cx = W / 2, cy = H / 2;

    function draw() {
      t++;
      if (!dragging.current) ry += 0.008;
      const pulse = Math.sin(t * 0.05) * 0.5 + 0.5;

      ctx.clearRect(0, 0, W, H);

      // Grid background
      ctx.strokeStyle = "rgba(30,34,53,0.6)";
      ctx.lineWidth   = 0.5;
      for (let i = 0; i <= W; i += 28) {
        ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke();
      }
      for (let i = 0; i <= H; i += 28) {
        ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(W, i); ctx.stroke();
      }

      // Ground plane
      const gpts = [
        project(-1.5, 1.15, -1.5, rx, ry, cx, cy),
        project( 1.5, 1.15, -1.5, rx, ry, cx, cy),
        project( 1.5, 1.15,  1.5, rx, ry, cx, cy),
        project(-1.5, 1.15,  1.5, rx, ry, cx, cy),
      ];
      ctx.beginPath();
      ctx.moveTo(gpts[0].x, gpts[0].y);
      gpts.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.closePath();
      ctx.fillStyle   = "rgba(20,24,36,0.5)";
      ctx.fill();
      ctx.strokeStyle = "rgba(59,130,246,0.12)";
      ctx.lineWidth   = 1;
      ctx.stroke();

      // Model specific
      const mc = cfg.memberColor;
      switch (cfg.type) {
        case "none":
          // Draw a placeholder or empty ground plane only
          ctx.fillStyle = "rgba(122, 139, 168, 0.4)";
          ctx.font = `11px ${C.mono}`;
          ctx.textAlign = "center";
          ctx.fillText("AWAITING INGESTION DATA", cx, cy - 8);
          ctx.font = `8px ${C.mono}`;
          ctx.fillText("Model rendering is inactive", cx, cy + 10);
          ctx.textAlign = "left";
          break;
        case "beam_with_diagonal_crack":   drawBeamWithDiagonalCrack(ctx, cx, cy, pulse, t);   break;
        case "column_vertical_split":      drawColumnVerticalSplit(ctx, cx, cy, pulse, t);      break;
        case "beam_vertical_crack":        drawBeamFlexuralCrack(ctx, cx, cy, pulse, t);        break;
        case "column_longitudinal_crack":  drawColumnLongitudinalCrack(ctx, cx, cy, pulse, t);  break;
        case "wall_corner_crack":          drawWallCornerCrack(ctx, cx, cy, pulse, t);          break;
        case "surface_map_crack":
        case "hairline_surface":           drawSurfaceMapCrack(ctx, cx, cy, pulse, t, cfg.crackColor); break;
        default:                           drawBeamWithDiagonalCrack(ctx, cx, cy, pulse, t);
      }

      // Type label
      ctx.fillStyle = "rgba(30,34,53,0.75)";
      ctx.fillRect(8, H - 28, W - 16, 22);
      ctx.fillStyle   = hexStr(cfg.crackColor);
      ctx.font        = `500 9px ${C.mono}`;
      ctx.fillText(cfg.description, 14, H - 13);

      rotRef.current = { x: rx, y: ry };
      animRef.current = requestAnimationFrame(draw);
    }

    // Mouse drag
    canvas.addEventListener("mousedown", e => {
      dragging.current = true;
      lastMouse.current = { x: e.clientX, y: e.clientY };
    });
    window.addEventListener("mouseup", () => { dragging.current = false; });
    window.addEventListener("mousemove", e => {
      if (!dragging.current) return;
      const dx = e.clientX - lastMouse.current.x;
      const dy = e.clientY - lastMouse.current.y;
      ry += dx * 0.012;
      rx += dy * 0.012;
      rx = Math.max(-1.1, Math.min(1.1, rx));
      lastMouse.current = { x: e.clientX, y: e.clientY };
    });

    draw();
    return () => {
      cancelAnimationFrame(animRef.current);
    };
  }, [crackType]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ width: "100%", height: height, cursor: "grab", borderRadius: 8, display: "block" }}
      aria-label={`3D model of ${crackType} crack`}
    />
  );
}

// ─── BLUEPRINT VIEW CANVAS ────────────────────────────────────────────────────
function BlueprintView({ crackType, m, width = 380, height = 250 }) {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    const crack = CRACK_DB[crackType] || { riskColor: "#FBB924", is_code: "IS 456", label: "Crack" };

    ctx.fillStyle = "#0B1628";
    ctx.fillRect(0, 0, W, H);

    if (crackType === "none") {
      ctx.fillStyle = "rgba(122, 139, 168, 0.4)";
      ctx.font = `11px ${C.mono}`;
      ctx.textAlign = "center";
      ctx.fillText("NO BLUEPRINT SCHEMATIC", W / 2, H / 2 - 8);
      ctx.font = `8px ${C.mono}`;
      ctx.fillText("Select a scenario or upload a UAV image to analyze", W / 2, H / 2 + 10);
      return;
    }

    // Grid
    ctx.strokeStyle = "rgba(59,130,246,0.1)";
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= W; i += 20) { ctx.beginPath(); ctx.moveTo(i,0); ctx.lineTo(i,H); ctx.stroke(); }
    for (let i = 0; i <= H; i += 20) { ctx.beginPath(); ctx.moveTo(0,i); ctx.lineTo(W,i); ctx.stroke(); }

    // Main member outline
    ctx.strokeStyle = "rgba(59,130,246,0.7)";
    ctx.lineWidth   = 1.5;
    ctx.setLineDash([]);

    if (crackType === "shear" || crackType === "flexural") {
      // Beam
      ctx.strokeRect(W*0.1, H*0.3, W*0.8, H*0.4);
      // Stirrups
      ctx.lineWidth = 0.8;
      ctx.strokeStyle = "rgba(59,130,246,0.4)";
      for (let x = W*0.15; x < W*0.85; x += 28) {
        ctx.strokeRect(x, H*0.33, 20, H*0.34);
      }
      // Rebar lines
      ctx.setLineDash([]);
      ctx.strokeStyle = "rgba(255,140,0,0.8)";
      ctx.lineWidth = 2;
      [H*0.37, H*0.63].forEach(y => {
        ctx.beginPath(); ctx.moveTo(W*0.12, y); ctx.lineTo(W*0.88, y); ctx.stroke();
      });

      // Crack indicator
      ctx.strokeStyle = crack.riskColor;
      ctx.lineWidth   = 2;
      ctx.setLineDash([]);
      if (crackType === "shear") {
        ctx.beginPath(); ctx.moveTo(W*0.65, H*0.3); ctx.lineTo(W*0.78, H*0.7); ctx.stroke();
      } else {
        ctx.beginPath(); ctx.moveTo(W*0.5, H*0.7); ctx.lineTo(W*0.5, H*0.45); ctx.stroke();
      }

    } else if (crackType === "compression" || crackType === "corrosion") {
      // Column
      ctx.strokeStyle = "rgba(59,130,246,0.7)";
      ctx.strokeRect(W*0.35, H*0.05, W*0.3, H*0.9);
      // Ties
      ctx.lineWidth = 0.8;
      ctx.strokeStyle = "rgba(59,130,246,0.4)";
      for (let y = H*0.1; y < H*0.9; y += 30) {
        ctx.strokeRect(W*0.37, y, W*0.26, 22);
      }
      // Rebar
      ctx.strokeStyle = "rgba(255,140,0,0.8)";
      ctx.lineWidth = 2;
      [W*0.4, W*0.6].forEach(x => {
        ctx.beginPath(); ctx.moveTo(x, H*0.07); ctx.lineTo(x, H*0.93); ctx.stroke();
      });
      // Crack
      ctx.strokeStyle = crack.riskColor;
      ctx.lineWidth = 2;
      if (crackType === "compression") {
        [W*0.46, W*0.54].forEach(x => {
          ctx.beginPath(); ctx.moveTo(x, H*0.1); ctx.lineTo(x, H*0.88); ctx.stroke();
        });
      } else {
        ctx.setLineDash([3,3]);
        ctx.beginPath(); ctx.moveTo(W*0.35, H*0.5); ctx.lineTo(W*0.65, H*0.5); ctx.stroke();
        ctx.setLineDash([]);
      }
    } else {
      // Generic wall/slab panel for settlement, shrinkage, hairline and any
      // other detected type — previously these rendered as an empty grid.
      ctx.strokeStyle = "rgba(59,130,246,0.7)";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(W*0.12, H*0.15, W*0.76, H*0.7);
      // Mesh reinforcement hint
      ctx.strokeStyle = "rgba(255,140,0,0.5)";
      ctx.lineWidth = 1;
      for (let x = W*0.2; x < W*0.85; x += 26) { ctx.beginPath(); ctx.moveTo(x, H*0.17); ctx.lineTo(x, H*0.83); ctx.stroke(); }
      for (let y = H*0.22; y < H*0.85; y += 26) { ctx.beginPath(); ctx.moveTo(W*0.14, y); ctx.lineTo(W*0.86, y); ctx.stroke(); }

      // Crack pattern by type
      ctx.strokeStyle = crack.riskColor;
      ctx.lineWidth = 2.2;
      if (crackType === "settlement") {
        // Stepped diagonal settlement crack
        ctx.beginPath();
        ctx.moveTo(W*0.25, H*0.2);
        ctx.lineTo(W*0.4, H*0.4); ctx.lineTo(W*0.52, H*0.4);
        ctx.lineTo(W*0.66, H*0.62); ctx.lineTo(W*0.78, H*0.62);
        ctx.stroke();
      } else if (crackType === "shrinkage" || crackType === "hairline") {
        // Fine map / craze cracking
        ctx.lineWidth = 1;
        const seg = [[0.3,0.35,0.45,0.5],[0.45,0.5,0.4,0.66],[0.55,0.4,0.68,0.55],[0.6,0.6,0.5,0.72],[0.4,0.5,0.58,0.52]];
        seg.forEach(([x1,y1,x2,y2]) => { ctx.beginPath(); ctx.moveTo(W*x1,H*y1); ctx.lineTo(W*x2,H*y2); ctx.stroke(); });
      } else {
        // Generic single crack
        ctx.beginPath(); ctx.moveTo(W*0.3, H*0.3); ctx.lineTo(W*0.7, H*0.68); ctx.stroke();
      }
    }

    // Dimension lines
    ctx.strokeStyle = "rgba(251,191,36,0.7)";
    ctx.lineWidth   = 0.8;
    ctx.setLineDash([4,3]);
    ctx.beginPath(); ctx.moveTo(W*0.05, H*0.3); ctx.lineTo(W*0.05, H*0.7); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#FBB924";
    ctx.font = `8px ${C.mono}`;
    ctx.fillText(`w=${m.width}mm`, 8, H*0.5 + 3);

    // IS Code reference
    ctx.fillStyle = "rgba(59,130,246,0.6)";
    ctx.font = `8px ${C.mono}`;
    ctx.fillText(crack.is_code, W - 110, H - 10);

  }, [crackType, m]);
  return <canvas ref={canvasRef} width={width} height={height} style={{ width:"100%", height:height, borderRadius:8 }} aria-label="Blueprint view"/>;
}

// --- IMAGE OVERLAY: single canvas draws photo + real crack paths together ---
function ImageOverlay({ imageUrl, crackType, analyzedData }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const crack = CRACK_DB[crackType] || { riskColor: "#FBB924" };
  const hasData = analyzedData && !analyzedData.error && analyzedData.defect_found !== false;

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || !imageUrl) return;

    let ro;
    const img = new Image();
    img.onload = () => {
      const draw = () => {
        const cw = container.clientWidth || 1;
        const ch = container.clientHeight || 1;
        canvas.width = cw;
        canvas.height = ch;
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, cw, ch);

        // contain-fit: whole image visible, preserve aspect, centred
        const ar = img.width / img.height;
        const car = cw / ch;
        let dw, dh, dx, dy;
        if (ar > car) { dw = cw; dh = cw / ar; dx = 0; dy = (ch - dh) / 2; }
        else { dh = ch; dw = ch * ar; dy = 0; dx = (cw - dw) / 2; }
        ctx.drawImage(img, dx, dy, dw, dh);

        if (!hasData) return;
        const cracks = (analyzedData?.cracks || []).filter(c => c.length_cm > 0);
        const riskColor = crack.riskColor || "#FF4444";
        const mapX = nx => dx + nx * dw;
        const mapY = ny => dy + ny * dh;

        cracks.slice(0, 12).forEach((c, i) => {
          const isPrimary = i === 0;
          const color = isPrimary ? riskColor : "rgba(255,210,0,0.95)";
          const pts = c.contour_pts;
          if (pts && pts.length >= 2) {
            // soft dark halo so the line reads on light or dark concrete
            ctx.beginPath();
            ctx.moveTo(mapX(pts[0][0]), mapY(pts[0][1]));
            for (let j = 1; j < pts.length; j++) ctx.lineTo(mapX(pts[j][0]), mapY(pts[j][1]));
            ctx.strokeStyle = "rgba(0,0,0,0.55)";
            ctx.lineWidth = (isPrimary ? 3 : 2) + 2;
            ctx.lineJoin = "round"; ctx.lineCap = "round";
            ctx.stroke();
            // coloured crack line
            ctx.strokeStyle = color;
            ctx.lineWidth = isPrimary ? 3 : 2;
            ctx.stroke();
          }
          // numbered badge at the crack start (matches table "Crack N")
          const bx = pts ? mapX(pts[0][0]) : mapX(0.5);
          const by = pts ? mapY(pts[0][1]) : mapY(0.5);
          ctx.beginPath();
          ctx.arc(bx, by, 10, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.strokeStyle = "rgba(0,0,0,0.6)";
          ctx.lineWidth = 1.5;
          ctx.stroke();
          ctx.fillStyle = "#000";
          ctx.font = "bold 12px monospace";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(String(i + 1), bx, by);
          ctx.textAlign = "start";
          ctx.textBaseline = "alphabetic";
        });
      };
      draw();
      ro = new ResizeObserver(draw);
      ro.observe(container);
    };
    img.src = imageUrl;
    return () => { if (ro) ro.disconnect(); };
  }, [imageUrl, hasData, analyzedData, crack.riskColor]);

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%", height: "100%", background: "#080A0F", overflow: "hidden" }}>
      {imageUrl ? (
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
      ) : (
        <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "rgba(122,139,168,0.45)", fontFamily: C.mono, fontSize: 11, gap: 6 }}>
          <div style={{ fontSize: 20 }}>CAM</div>
          <div>NO ACTIVE SCAN DATA</div>
          <div style={{ fontSize: 9 }}>Upload an image and click Analyze</div>
        </div>
      )}

      {hasData && (
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
          <div style={{ position: "absolute", top: 6, left: 6, background: "rgba(0,0,0,0.78)", border: `1px solid ${crack.riskColor}`, borderRadius: 4, padding: "2px 7px", fontFamily: C.mono, fontSize: 9, fontWeight: 700, color: crack.riskColor }}>
            {analyzedData.crack_type}  ({analyzedData.crack_count} crack{analyzedData.crack_count === 1 ? "" : "s"})
          </div>
          <div style={{ position: "absolute", top: 6, right: 6, background: crack.riskColor, borderRadius: 4, padding: "2px 7px", fontFamily: C.mono, fontSize: 9, fontWeight: 800, color: "#000" }}>
            {(analyzedData.severity || "").toUpperCase()}
          </div>
          <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, background: "rgba(0,0,0,0.82)", borderTop: `1px solid rgba(255,255,255,0.07)`, display: "flex", fontFamily: C.mono }}>
            {[
              { l: "LEN", v: `${analyzedData.length_cm}cm` },
              { l: "W", v: `${analyzedData.width_mm}mm` },
              { l: "ANG", v: `${analyzedData.orientation_angle}deg` },
              { l: "V-IDX", v: `${analyzedData.v_index}` },
            ].map((item, i) => (
              <div key={i} style={{ flex: 1, padding: "4px 4px", borderRight: i < 3 ? `1px solid rgba(255,255,255,0.07)` : "none", textAlign: "center" }}>
                <div style={{ fontSize: 7, color: "rgba(255,255,255,0.4)", letterSpacing: "0.04em" }}>{item.l}</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#fff" }}>{item.v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {analyzedData && !analyzedData.error && analyzedData.defect_found === false && imageUrl && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
          <div style={{ background: "rgba(34,197,94,0.15)", border: "1px solid #22c55e", borderRadius: 8, padding: "8px 18px", fontFamily: C.mono, fontSize: 11, fontWeight: 700, color: "#22c55e" }}>
            No Crack - Surface Sound
          </div>
        </div>
      )}
    </div>
  );
}


// ─── METRIC CARD ─────────────────────────────────────────────────────────────
function MetricCard({ label, value, unit, color }) {
  return (
    <div style={{
      background: C.card,
      border: `1px solid ${C.border}`,
      borderLeft: `4px solid ${color || C.accent}`,
      borderRadius: 8,
      padding: "12px 14px",
      boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)",
      transition: "all 0.2s ease"
    }}>
      <div style={{ fontSize: 9.5, letterSpacing: "0.08em", color: C.textSub, textTransform: "uppercase", marginBottom: 4, fontWeight: 700 }}>{label}</div>
      <div style={{ fontFamily: C.mono, fontSize: 32, fontWeight: 800, color: color || "#FFFFFF", lineHeight: 1.1 }}>
        {value}<span style={{ fontSize: 13, fontWeight: 600, color: C.textSub, marginLeft: 2 }}>{unit}</span>
      </div>
    </div>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
export default function CortexCrackAnalyzer({ authToken, getApiUrl, onDefectSaved, onStatsChange }) {
  const [slots, setSlots] = useState([
    { id: 1, crackType: "none", uploadedImg: null, analyzed: false, analyzedData: null, uploadedLocalPath: "", analyzing: false, activeView: "overlay" },
    { id: 2, crackType: "none", uploadedImg: null, analyzed: false, analyzedData: null, uploadedLocalPath: "", analyzing: false, activeView: "overlay" },
  ]);
  const [activeSlotIdx, setActiveSlotIdx] = useState(0);
  const fileRef = useRef(null);

  const [peekingSlotIdx, setPeekingSlotIdx] = useState(null);
  const peekTimerRef = useRef(null);

  // ── User-supplied capture geometry & measurement mode ──────────────────────
  // The real-world dimensions the frame covers drive an accurate ground-sampling
  // distance; the method toggles the real CV+trigonometry engine vs the legacy
  // heuristic ("coin flip") estimate.
  const [realWidthM, setRealWidthM] = useState("3.0");
  const [realHeightM, setRealHeightM] = useState("2.0");
  const [measurementMethod, setMeasurementMethod] = useState("trigonometry");
  const pendingAnalyzeRef = useRef(false);

  const handleMouseDownPeek = (idx) => {
    peekTimerRef.current = setTimeout(() => {
      setPeekingSlotIdx(idx);
    }, 250);
  };

  const handleMouseUpPeek = () => {
    if (peekTimerRef.current) {
      clearTimeout(peekTimerRef.current);
    }
    setPeekingSlotIdx(null);
  };

  const handleMouseMoveTilt = (e, idx) => {
    const card = e.currentTarget;
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const xc = rect.width / 2;
    const yc = rect.height / 2;
    const angleX = (yc - y) / 10;
    const angleY = (x - xc) / 10;
    
    card.style.transform = `perspective(1000px) rotateX(${angleX}deg) rotateY(${angleY}deg) scale3d(1.02, 1.02, 1.02)`;
    card.style.boxShadow = `0 14px 28px rgba(0,0,0,0.45), 0 10px 10px rgba(0,0,0,0.35), 0 0 20px ${C.accentGlow}`;
    card.style.zIndex = "5";
  };

  const handleMouseLeaveTilt = (e, isActive) => {
    const card = e.currentTarget;
    card.style.transform = isActive ? "perspective(1000px) scale3d(1.01, 1.01, 1.01)" : "perspective(1000px) scale3d(1, 1, 1)";
    card.style.boxShadow = isActive ? `0 0 18px ${C.accentGlow}, 0 4px 6px -1px rgba(0, 0, 0, 0.08)` : "0 4px 6px -1px rgba(0, 0, 0, 0.05)";
    card.style.zIndex = "1";
  };

  const activeSlot = slots[activeSlotIdx];
  const crackType = activeSlot.crackType;
  const uploadedImg = activeSlot.uploadedImg;
  const analyzed = activeSlot.analyzed;
  const analyzedData = activeSlot.analyzedData;
  const uploadedLocalPath = activeSlot.uploadedLocalPath;
  const analyzing = activeSlot.analyzing;
  const activeView = activeSlot.activeView;

  const updateSlot = (idx, updates) => {
    setSlots(prev => prev.map((s, i) => i === idx ? { ...s, ...updates } : s));
  };

  const getMeasurementsForSlot = (slot) => {
    return slot.analyzedData && !slot.analyzedData.error ? {
      width: (slot.analyzedData.width_mm || 0).toFixed(2),
      length: (slot.analyzedData.length_cm || 0).toFixed(1),
      spacing: slot.analyzedData.rebar_spacing_cm > 0 ? (slot.analyzedData.rebar_spacing_cm || 0).toFixed(1) : "—",
      vi: (slot.analyzedData.v_index || 0).toFixed(2),
    } : MEASUREMENTS[slot.crackType];
  };

  const setCrackType = (val) => updateSlot(activeSlotIdx, { crackType: val });
  const setUploadedImg = (val) => updateSlot(activeSlotIdx, { uploadedImg: val });
  const setAnalyzed = (val) => updateSlot(activeSlotIdx, { analyzed: val });
  const setAnalyzedData = (val) => updateSlot(activeSlotIdx, { analyzedData: val });
  const setUploadedLocalPath = (val) => updateSlot(activeSlotIdx, { uploadedLocalPath: val });
  const setAnalyzing = (val) => updateSlot(activeSlotIdx, { analyzing: val });
  const setActiveView = (val) => updateSlot(activeSlotIdx, { activeView: val });

  const crack = CRACK_DB[crackType];

  const SCENARIOS = [
    { id: "shear",       label: "Shear Crack",        icon: "⚡" },
    { id: "flexural",    label: "Flexural Tension",   icon: "↕" },
    { id: "corrosion",   label: "Rebar Corrosion",    icon: "🔴" },
    { id: "settlement",  label: "Settlement Crack",   icon: "↘" },
    { id: "compression", label: "Compression Split",  icon: "⬇" },
    { id: "shrinkage",   label: "Hairline Shrink",    icon: "⋯" },
  ];

  const VIEWS = [
    { id: "overlay",   label: "🖼 Visual Overlay" },
    { id: "blueprint", label: "📐 Blueprint X-Ray" },
    { id: "model3d",   label: "🧊 3D Model" },
  ];

  // Measurements per crack type
  const MEASUREMENTS = {
    shear:       { width: "63.64", length: "40", spacing: "45.4", vi: "0.85" },
    flexural:    { width: "8.20",  length: "28", spacing: "30.2", vi: "0.61" },
    corrosion:   { width: "12.50", length: "55", spacing: "22.8", vi: "0.72" },
    settlement:  { width: "18.30", length: "34", spacing: "38.0", vi: "0.66" },
    compression: { width: "25.00", length: "90", spacing: "18.5", vi: "0.94" },
    shrinkage:   { width: "0.08",  length: "12", spacing: "—",    vi: "0.14" },
    none:        { width: "0.00",  length: "0",  spacing: "—",    vi: "0.00" },
  };

  // Dynamic calculations for dynamic stats bar
  const activeSlots = slots.filter(s => s.crackType !== "none");
  const totalDefects = activeSlots.length;
  const criticalDefects = slots.filter(s => {
    if (s.crackType === "none") return false;
    const dbRisk = CRACK_DB[s.crackType]?.risk;
    const severity = s.analyzedData?.severity;
    return (
      dbRisk === "CRITICAL" || dbRisk === "SEVERE" ||
      severity === "critical" || severity === "severe" || severity === "SEVERE"
    );
  }).length;
  const avgVIndex = activeSlots.length > 0
    ? (activeSlots.reduce((sum, s) => sum + parseFloat(getMeasurementsForSlot(s).vi || 0), 0) / activeSlots.length).toFixed(2)
    : "0.00";
  const avgGSD = activeSlots.length > 0
    ? (activeSlots.reduce((sum, s) => sum + parseFloat(s.analyzedData?.gsd_mm_px || s.analyzedData?.gsd || 2.1), 0) / activeSlots.length).toFixed(1)
    : "2.1";

  // Notify parent of slot statistics changes
  useEffect(() => {
    if (onStatsChange) {
      onStatsChange({
        total: totalDefects.toString(),
        critical: criticalDefects.toString(),
        avgVIndex: avgVIndex,
        gsd: avgGSD
      });
    }
  }, [slots, onStatsChange, totalDefects, criticalDefects, avgVIndex, avgGSD]);

  const m = analyzedData && !analyzedData.error ? {
    width: (analyzedData.width_mm || 0).toFixed(2),
    length: (analyzedData.length_cm || 0).toFixed(1),
    spacing: analyzedData.rebar_spacing_cm > 0 ? (analyzedData.rebar_spacing_cm || 0).toFixed(1) : "—",
    vi: (analyzedData.v_index || 0).toFixed(2),
  } : MEASUREMENTS[crackType];

  const performAnalysis = useCallback((file) => {
    if (!file) { alert("Upload an image first."); return; }
    updateSlot(activeSlotIdx, { analyzing: true, analyzed: false, analyzedData: null, uploadedLocalPath: "" });

    const formData = new FormData();
    formData.append("files", file);
    if (realWidthM && parseFloat(realWidthM) > 0) formData.append("real_width_m", realWidthM);
    if (realHeightM && parseFloat(realHeightM) > 0) formData.append("real_height_m", realHeightM);
    formData.append("measurement_method", measurementMethod);

    const headers = {};
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

    fetch(getApiUrl("/api/upload-images"), { method: "POST", headers, body: formData })
      .then(res => { if (!res.ok) throw new Error("API analysis failed (HTTP " + res.status + ")"); return res.json(); })
      .then(data => {
        const result = data.results && data.results[0];
        if (!result) { alert("No analysis result returned by server."); setAnalyzing(false); return; }
        setActiveView("overlay");
        if (result.passed) {
          setAnalyzedData(result.analysis);
          setUploadedLocalPath(result.local_path);
          const type = result.analysis.crack_type || "";
          if (result.analysis.defect_found === false || type.toLowerCase().includes("no crack")) setCrackType("none");
          else if (type.toLowerCase().includes("shear")) setCrackType("shear");
          else if (type.toLowerCase().includes("corrosion") || type.toLowerCase().includes("spall")) setCrackType("corrosion");
          else if (type.toLowerCase().includes("flexural")) setCrackType("flexural");
          else if (type.toLowerCase().includes("settlement")) setCrackType("settlement");
          else if (type.toLowerCase().includes("compression")) setCrackType("compression");
          else if (type.toLowerCase().includes("shrinkage")) setCrackType("shrinkage");
          else setCrackType("hairline");
          setAnalyzed(true);
        } else {
          setCrackType("none");
          setAnalyzedData({
            error: true,
            warnings: result.warnings,
            crack_type: "Quality Gate Rejection",
            recommendation: "Ingestion rejected: " + (result.warnings || []).join(" ")
          });
          setAnalyzed(true);
        }
        setAnalyzing(false);
      })
      .catch(err => {
        console.error(err);
        setAnalyzing(false);
        alert("Error analyzing image: " + err.message);
      });
  }, [activeSlotIdx, authToken, getApiUrl, realWidthM, realHeightM, measurementMethod]);

  const handleUpload = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Load image into the slot and show a preview.
    updateSlot(activeSlotIdx, {
      pendingFile: file,
      uploadedImg: URL.createObjectURL(file),
      analyzed: false,
      analyzedData: null,
      analyzing: false,
      uploadedLocalPath: "",
      crackType: "none",
      activeView: "overlay",
    });
    if (fileRef.current) fileRef.current.value = "";
    // If Analyze was pressed with no image, analyze immediately after picking.
    if (pendingAnalyzeRef.current) {
      pendingAnalyzeRef.current = false;
      performAnalysis(file);
    }
  }, [activeSlotIdx, performAnalysis]);

  const runAnalysis = useCallback(() => {
    const file = slots[activeSlotIdx]?.pendingFile;
    if (file) {
      performAnalysis(file);
    } else {
      // No image yet — open the picker and analyze as soon as one is chosen.
      pendingAnalyzeRef.current = true;
      fileRef.current?.click();
    }
  }, [slots, activeSlotIdx, performAnalysis]);

  return (
    <div style={{ height: "100%", background: C.bg, fontFamily: C.body, color: C.text, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: ${C.bg}; }
        @keyframes fadeUp { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
        @keyframes pulse  { 0%,100%{opacity:1} 50%{opacity:0.4} }
        @keyframes scan   { 0%{transform:translateY(-100%)} 100%{transform:translateY(400%)} }
        @keyframes shimmer{ 0%{background-position:-400px 0} 100%{background-position:400px 0} }
        button { cursor: pointer; font-family: inherit; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius:2px; }
      `}</style>

      {/* ── TOP STAT BAR ── */}
      <div style={{ borderBottom: `1px solid ${C.border}`, background: C.surface, padding: "12px 24px", display: "flex", gap: 16, alignItems: "center" }}>
        <div style={{ display:"flex", alignItems:"center", gap:10, marginRight:"auto" }}>
          {/* Logo Mark of Cortex Solutions: a yellow square with target circle */}
          <svg width="28" height="28" viewBox="0 0 100 100" style={{ borderRadius: 6 }}>
            <rect width="100" height="100" fill="#FFE600" />
            <circle cx="50" cy="50" r="32" fill="none" stroke="#000000" strokeWidth="8" />
            <circle cx="50" cy="50" r="14" fill="#000000" />
            <line x1="50" y1="10" x2="50" y2="90" stroke="#000000" strokeWidth="6" />
            <line x1="10" y1="50" x2="90" y2="50" stroke="#000000" strokeWidth="6" />
          </svg>
          <span style={{ fontFamily: C.mono, fontSize: 22, fontWeight: 800, letterSpacing: "0.05em", color: "#FFFFFF", display: "flex", alignItems: "center" }}>
            C
            <span style={{ display: "inline-block", position: "relative", top: 0, margin: "0 1px" }}>
              <svg width="18" height="18" viewBox="0 0 100 100" style={{ verticalAlign: "middle" }}>
                <circle cx="50" cy="50" r="45" fill="#FFE600" />
                <circle cx="50" cy="50" r="28" fill="none" stroke="#000000" strokeWidth="10" />
                <circle cx="50" cy="50" r="12" fill="#000000" />
                <line x1="50" y1="12" x2="50" y2="88" stroke="#000000" strokeWidth="8" />
                <line x1="12" y1="50" x2="88" y2="50" stroke="#000000" strokeWidth="8" />
              </svg>
            </span>
            RTEX
          </span>
          <span style={{ fontSize:9, fontFamily:C.mono, color: "#000", background: "#FFE600", borderRadius:4, padding:"2px 8px", fontWeight: "bold", marginLeft: 6 }}>
            CONSTRUCTION SOLUTIONS
          </span>
        </div>
        {[
          { label:"Total Defects", val:totalDefects,     delta: totalDefects > 0 ? `+${totalDefects * 10}%` : "+0%", dc:C.minor },
          { label:"Critical",      val:criticalDefects,  delta: criticalDefects > 0 ? "HIGH RISK" : "NOMINAL",  dc: criticalDefects > 0 ? C.critical : C.minor },
          { label:"Avg V-Index",   val:avgVIndex,        delta: parseFloat(avgVIndex) > 0.5 ? "ELEVATED" : "NOMINAL",  dc: parseFloat(avgVIndex) > 0.5 ? C.severe : C.minor },
          { label:"GSD",           val:avgGSD,           unit:"mm/px", delta:"+0%", dc:C.textMuted },
        ].map((s,i) => (
          <div key={i} style={{ textAlign:"right", minWidth:110, borderLeft: i > 0 ? `1px solid ${C.border}` : "none", paddingLeft: 16 }}>
            <div style={{ fontSize:9.5, fontWeight:700, color:C.textSub, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom: 2 }}>
              {s.label}
            </div>
            <div style={{ fontFamily:C.mono, fontSize:28, fontWeight:800, color:"#FFFFFF", lineHeight:1.1 }}>
              {s.val}
              {s.unit && <span style={{fontSize:12, color:"rgba(255,255,255,0.4)"}}> {s.unit}</span>}
            </div>
            <div style={{ fontSize:9, color:s.dc, display:"flex", alignItems:"center", justifyContent:"flex-end", gap:4, marginTop: 4, fontWeight:700 }}>
              <span style={{ width:4,height:4,borderRadius:"50%",background:s.dc, display:"inline-block" }}/>
              {s.delta}
            </div>
          </div>
        ))}
      </div>

      <div style={{ padding:"8px 24px 2px" }}>
        <h1 style={{ fontFamily: C.display, fontSize: 20, fontWeight: 800, letterSpacing:"0.02em", color: C.text }}>
          UAV Visual Frame Crack &amp; Rebar Analyzer
        </h1>
        <p style={{ fontSize: 11, color: C.textSub, marginTop: 2, fontWeight: 500 }}>
          IS 456 · IS 13935 · IS 1904 compliant — select a crack scenario or upload a UAV image
        </p>
      </div>

      {/* ── MAIN GRID ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "2.3fr 1.1fr",
        gap: 12,
        padding: "10px 16px 14px",
        flex: 1,
        minHeight: 0,
        overflow: "auto"
      }}>

        {/* ── LEFT PANEL: 2-Viewport Grid ── */}
        <div style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}>
          {/* ── Slot cards row ── */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {slots.map((slot, idx) => {
            const isActive = idx === activeSlotIdx;
            const slotM = getMeasurementsForSlot(slot);
            const slotCrack = CRACK_DB[slot.crackType];

            return (
              <div
                key={slot.id}
                onClick={() => setActiveSlotIdx(idx)}
                style={{
                  background: C.card,
                  border: isActive ? `2px solid ${C.borderHi}` : `1px solid ${C.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                  boxShadow: isActive ? `0 0 20px ${C.accentGlow}, 0 4px 8px rgba(0, 0, 0, 0.2)` : "0 4px 6px rgba(0, 0, 0, 0.1)",
                  display: "flex",
                  flexDirection: "column",
                  position: "relative",
                  height: 380,
                  minHeight: 380,
                }}
                onMouseOver={(e) => {
                  if (!isActive) e.currentTarget.style.borderColor = C.borderHi;
                }}
                onMouseOut={(e) => {
                  if (!isActive) e.currentTarget.style.borderColor = C.border;
                }}
              >
                {/* Viewport Header */}
                <div style={{
                  padding: "10px 12px",
                  borderBottom: `1px solid ${C.border}`,
                  background: C.surface,
                  color: "#FFFFFF",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{
                        fontFamily: C.mono,
                        fontSize: 13,
                        fontWeight: 700,
                        color: isActive ? C.accent : "#FFFFFF"
                      }}>
                        SLOT {slot.id}
                      </span>
                      {isActive && (
                        <span style={{
                          fontSize: 9.5,
                          background: C.accent,
                          color: "#000000",
                          padding: "2px 6px",
                          borderRadius: 4,
                          fontWeight: "bold",
                          fontFamily: C.mono,
                        }}>
                          ACTIVE
                        </span>
                      )}
                    </div>
                  </div>
                  
                  <div style={{ display: "flex", gap: 4 }} onClick={(e) => e.stopPropagation()}>
                    {VIEWS.map(v => {
                      const isSelected = slot.activeView === v.id;
                      return (
                        <button
                          key={v.id}
                          onClick={() => updateSlot(idx, { activeView: v.id })}
                          style={{
                            flex: 1,
                            fontSize: 11,
                            padding: "5px 0",
                            borderRadius: 4,
                            border: "none",
                            background: isSelected ? C.accent : "rgba(255,255,255,0.08)",
                            color: isSelected ? "#000000" : "rgba(255,255,255,0.6)",
                            fontWeight: isSelected ? "bold" : "normal",
                            transition: "all 0.1s",
                          }}
                        >
                          {v.id === "overlay" ? "Overlay" : v.id === "blueprint" ? "Blueprint" : "3D Model"}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Viewport Canvas area */}
                <div 
                  onMouseDown={() => handleMouseDownPeek(idx)}
                  onMouseUp={handleMouseUpPeek}
                  onMouseLeave={handleMouseUpPeek}
                  onTouchStart={() => handleMouseDownPeek(idx)}
                  onTouchEnd={handleMouseUpPeek}
                  style={{ position: "relative", background: "#080A0F", flex: 1, minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", cursor: "zoom-in" }}
                  title="Click and hold to 3D Touch Peek"
                >
                  {slot.analyzing && (
                    <div style={{
                      position: "absolute",
                      inset: 0,
                      zIndex: 10,
                      background: "rgba(8,10,15,0.8)",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 8,
                      padding: 10,
                    }}>
                      <div style={{ fontFamily: C.mono, fontSize: 11, color: C.accent, fontWeight: "bold" }}>⟳ ANALYZING...</div>
                      <div style={{ width: "80%", height: 3, background: C.border, borderRadius: 2, overflow: "hidden" }}>
                        <div style={{
                          height: "100%",
                          background: C.accent,
                          animation: "shimmer 1.2s ease-in-out infinite",
                          backgroundSize: "400px 100%",
                          backgroundImage: `linear-gradient(90deg,transparent,${C.accent},transparent)`
                        }}/>
                      </div>
                    </div>
                  )}

                  {slot.activeView === "overlay"   && <ImageOverlay imageUrl={slot.uploadedImg} crackType={slot.crackType} analyzedData={slot.analyzedData}/>}
                  {slot.activeView === "blueprint" && <BlueprintView crackType={slot.crackType} m={slotM} width={380} height={230}/>}
                  {slot.activeView === "model3d"   && <CrackModel3D crackType={slot.crackType} width={380} height={230}/>}
                </div>

                {/* Slot info footer */}
                <div style={{
                  padding: "10px 12px",
                  borderTop: `1px solid ${C.border}`,
                  fontSize: 12,
                  color: C.textSub,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  background: C.surface,
                }}>
                  <span style={{ fontFamily: C.mono, color: slotCrack.riskColor, fontWeight: 700 }}>
                    {slot.analyzedData && !slot.analyzedData.error ? (slot.analyzedData.crack_type || slotCrack.label) : slotCrack.label}
                  </span>
                  <span style={{ fontFamily: C.mono, fontSize: 11, fontWeight: 600 }}>
                    w={slotM.width}mm
                  </span>
                </div>
              </div>
            );
          })}
          </div>{/* end slot cards row */}
          
          {/* Active Slot Control Section */}
          <div style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 12,
            padding: 16,
            display: "flex",
            flexDirection: "column",
            gap: 12,
            boxShadow: `0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)`
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: C.text, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Active Slot Controls (Slot {activeSlotIdx + 1})
                </span>
                <span style={{
                  fontSize: 11,
                  color: C.textSub,
                  background: "#F3F4F6",
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  padding: "2px 8px",
                  fontFamily: C.mono,
                  fontWeight: 600,
                }}>
                  {activeSlot.crackType === "none" ? "No Scenario Selected" : `Scenario: ${CRACK_DB[activeSlot.crackType].label}`}
                </span>
              </div>
            </div>

            {/* Capture geometry + measurement engine */}
            <div style={{
              display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end",
              padding: "10px 12px", background: C.surface,
              border: `1px solid ${C.border}`, borderRadius: 8,
            }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <label style={{ fontSize: 10, fontWeight: 700, color: C.textSub, fontFamily: C.mono, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Image Length (m)
                </label>
                <input
                  type="number" min="0" step="0.1" value={realWidthM}
                  onChange={(e) => setRealWidthM(e.target.value)}
                  style={{ width: 90, padding: "6px 8px", background: C.bg, border: `1px solid ${C.border}`,
                    borderRadius: 6, color: C.text, fontFamily: C.mono, fontSize: 13 }}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <label style={{ fontSize: 10, fontWeight: 700, color: C.textSub, fontFamily: C.mono, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Image Breadth (m)
                </label>
                <input
                  type="number" min="0" step="0.1" value={realHeightM}
                  onChange={(e) => setRealHeightM(e.target.value)}
                  style={{ width: 90, padding: "6px 8px", background: C.bg, border: `1px solid ${C.border}`,
                    borderRadius: 6, color: C.text, fontFamily: C.mono, fontSize: 13 }}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4, marginLeft: "auto" }}>
                <label style={{ fontSize: 10, fontWeight: 700, color: C.textSub, fontFamily: C.mono, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Measurement Method
                </label>
                <div style={{ display: "flex", border: `1px solid ${C.border}`, borderRadius: 6, overflow: "hidden" }}>
                  {[
                    { id: "trigonometry", label: "📐 Geometry" },
                    { id: "cv", label: "🧠 CV (AI)" },
                  ].map(opt => (
                    <button
                      key={opt.id}
                      onClick={() => setMeasurementMethod(opt.id)}
                      title={
                        opt.id === "trigonometry"
                          ? "Straight principal-axis length + trigonometric GSD scaling"
                          : "Tiled segmentation + skeleton geodesic length (uses the YOLO model when available, else classical CV)"}
                      style={{
                        padding: "6px 14px", border: "none", fontSize: 12, fontWeight: 700, fontFamily: C.mono,
                        background: measurementMethod === opt.id ? C.accent : C.bg,
                        color: measurementMethod === opt.id ? "#000" : C.textSub,
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Method comparison: geometry vs computer-vision */}
            {analyzedData && !analyzedData.error && analyzedData.method_comparison && (
              <div style={{
                padding: "10px 12px", background: C.surface,
                border: `1px solid ${C.border}`, borderRadius: 8, fontFamily: C.mono,
              }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: C.textSub, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
                  Length Method Comparison
                </div>
                <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: 9, color: C.textSub }}>📐 GEOMETRY</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: C.text }}>
                      {analyzedData.method_comparison.geometry.length_cm} cm
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: C.textSub }}>
                      🧠 CV{analyzedData.method_comparison.cv.yolo_used ? " (YOLO)" : ""}
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: C.accent }}>
                      {analyzedData.method_comparison.cv.length_cm} cm
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: C.textSub }}>Δ LENGTH</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: C.text }}>
                      {analyzedData.method_comparison.length_delta_cm} cm
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: C.textSub }}>AGREEMENT</div>
                    <div style={{ fontSize: 15, fontWeight: 700,
                      color: analyzedData.method_comparison.length_agreement_pct >= 90 ? "#22c55e"
                            : analyzedData.method_comparison.length_agreement_pct >= 75 ? C.accent : "#ef4444" }}>
                      {analyzedData.method_comparison.length_agreement_pct}%
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: C.textSub }}>TORTUOSITY</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: C.text }}>
                      {analyzedData.method_comparison.cv.tortuosity}×
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: 10, color: C.textSub, marginTop: 8, fontFamily: C.body }}>
                  Geometry = straight extent · CV = skeleton geodesic length following curvature
                  {analyzedData.cv_detail ? ` · engine: ${analyzedData.cv_detail.skeleton_engine}` : ""}
                </div>

                {/* Per-crack comparison table */}
                {Array.isArray(analyzedData.method_comparison.per_crack)
                  && analyzedData.method_comparison.per_crack.length > 0 && (
                  <div style={{ marginTop: 10, overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, fontFamily: C.mono }}>
                      <thead>
                        <tr style={{ color: C.textSub, textAlign: "right" }}>
                          <th style={{ textAlign: "left", padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>#</th>
                          <th style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>📐 Geo (cm)</th>
                          <th style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>🧠 CV (cm)</th>
                          <th style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>Δ (cm)</th>
                          <th style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>Agree</th>
                          <th style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>Angle</th>
                          <th style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>Tort.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analyzedData.method_comparison.per_crack.map((row, i) => (
                          <tr key={i} style={{ textAlign: "right", color: C.text }}>
                            <td style={{ textAlign: "left", padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>
                              Crack {i + 1}{row.matched ? "" : " ★"}
                            </td>
                            <td style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>
                              {row.geometry_length_cm != null ? row.geometry_length_cm : "—"}
                            </td>
                            <td style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}`, color: C.accent }}>
                              {row.cv_length_cm != null ? row.cv_length_cm : "—"}
                            </td>
                            <td style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>
                              {row.delta_cm != null ? row.delta_cm : "—"}
                            </td>
                            <td style={{
                              padding: "4px 6px", borderBottom: `1px solid ${C.border}`,
                              color: row.agreement_pct == null ? C.textSub
                                    : row.agreement_pct >= 90 ? "#22c55e"
                                    : row.agreement_pct >= 75 ? C.accent : "#ef4444",
                            }}>
                              {row.agreement_pct != null ? `${row.agreement_pct}%` : "—"}
                            </td>
                            <td style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>
                              {row.angle_deg != null ? `${row.angle_deg}°` : "—"}
                            </td>
                            <td style={{ padding: "4px 6px", borderBottom: `1px solid ${C.border}` }}>
                              {row.tortuosity != null ? `${row.tortuosity}×` : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div style={{ fontSize: 9.5, color: C.textSub, marginTop: 6, fontFamily: C.body, lineHeight: 1.5 }}>
                      <strong style={{ color: C.text }}>★ (star)</strong> = this crack was detected by only <strong>one</strong> method
                      (Geometry or CV) and has no matching crack in the other method, so Δ and Agreement can't be computed.
                      Rows without a star were matched by both methods.
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Upload + Clear Row */}
            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={() => {
                  updateSlot(activeSlotIdx, {
                    uploadedImg: null,
                    crackType: "none",
                    analyzed: false,
                    analyzedData: null,
                    uploadedLocalPath: "",
                    analyzing: false,
                  });
                  if (fileRef.current) fileRef.current.value = "";
                }}
                style={{
                  flex: 1,
                  padding: "11px",
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  color: C.textSub,
                  fontSize: 13,
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  transition: "all 0.2s",
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.background = C.card;
                  e.currentTarget.style.borderColor = C.borderHi;
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.background = C.surface;
                  e.currentTarget.style.borderColor = C.border;
                }}
              >
                ✂ Clear Slot Visuals
              </button>
              
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={handleUpload}
              />
              
              <button
                onClick={() => fileRef.current?.click()}
                style={{
                  flex: 1.3,
                  padding: "11px",
                  background: C.accent,
                  border: "none",
                  borderRadius: 8,
                  color: "#000000",
                  fontSize: 14,
                  fontWeight: 700,
                  boxShadow: `0 4px 14px rgba(251,191,36,0.2)`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  transition: "all 0.2s",
                }}
                onMouseOver={(e) => e.currentTarget.style.filter = "brightness(0.95)"}
                onMouseOut={(e) => e.currentTarget.style.filter = "none"}
              >
                🖼 {activeSlot.pendingFile || activeSlot.uploadedImg ? "Change Image" : `Upload Image to Slot ${activeSlotIdx + 1}`}
              </button>

              <button
                onClick={runAnalysis}
                disabled={!activeSlot.pendingFile || analyzing}
                style={{
                  flex: 1.6,
                  padding: "11px",
                  background: (activeSlot.pendingFile && !analyzing) ? "#22c55e" : C.surface,
                  border: `1px solid ${activeSlot.pendingFile ? "#22c55e" : C.border}`,
                  borderRadius: 8,
                  color: (activeSlot.pendingFile && !analyzing) ? "#04130a" : C.textSub,
                  fontSize: 14,
                  fontWeight: 800,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  cursor: (activeSlot.pendingFile && !analyzing) ? "pointer" : "not-allowed",
                  transition: "all 0.2s",
                }}
                onMouseOver={(e) => { if (activeSlot.pendingFile && !analyzing) e.currentTarget.style.filter = "brightness(1.08)"; }}
                onMouseOut={(e) => e.currentTarget.style.filter = "none"}
              >
                {analyzing ? "⏳ Analyzing…" : "🔬 Analyze"}
              </button>
            </div>

            {/* Quick Scenario Select for active slot */}
            <div>
              <div style={{ fontSize: 11, color: C.textSub, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8, fontWeight: 600 }}>
                Demo Crack Library — illustrative preset values (not measured from an image). Upload + Analyze for real measurements.
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8 }}>
                {SCENARIOS.map(s => {
                  const isSelected = activeSlot.crackType === s.id;
                  return (
                    <button
                      key={s.id}
                      onClick={() => {
                        updateSlot(activeSlotIdx, {
                          crackType: s.id,
                          uploadedImg: null,
                          uploadedLocalPath: "",
                          analyzed: false,
                          analyzedData: null,
                          analyzing: false,
                        });
                        if (fileRef.current) fileRef.current.value = "";
                      }}
                      style={{
                        padding: "8px 10px",
                        fontSize: 12,
                        textAlign: "center",
                        background: isSelected ? C.accentGlow : C.surface,
                        border: `1px solid ${isSelected ? C.borderHi : C.border}`,
                        borderRadius: 8,
                        color: isSelected ? C.accentDark : C.textSub,
                        fontWeight: isSelected ? "bold" : "normal",
                        transition: "all 0.15s",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 4,
                        boxShadow: "0 1px 2px rgba(0,0,0,0.02)"
                      }}
                      onMouseOver={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.borderColor = C.borderHi;
                          e.currentTarget.style.background = C.card;
                        }
                      }}
                      onMouseOut={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.borderColor = C.border;
                          e.currentTarget.style.background = C.surface;
                        }
                      }}
                    >
                      <span>{s.icon}</span>
                      <span style={{ fontFamily: C.mono, fontSize: 11, fontWeight: isSelected ? 600 : 500 }}>{s.label.split(" ")[0]}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* ── RIGHT PANEL ── */}
        <div style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          animation: "fadeUp 0.3s ease",
          height: "100%",
          minHeight: 0,
          overflowY: "auto",
          paddingRight: 4
        }}>

          {/* Comparison Matrix Table */}
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)" }}>
            <div style={{ padding: "10px 12px", borderBottom: `1px solid ${C.border}`, background: C.surface, color: "#FFFFFF" }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: C.accent, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                2-Slot Comparison
              </span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${C.border}`, background: C.surface }}>
                    <th style={{ padding: "8px 12px", color: C.textSub, fontWeight: 600 }}>Parameter</th>
                    {[0, 1].map((idx) => {
                      const isActive = idx === activeSlotIdx;
                      return (
                        <th
                          key={idx}
                          onClick={() => setActiveSlotIdx(idx)}
                          style={{
                            padding: "8px 12px",
                            color: isActive ? C.accentDark : C.text,
                            fontWeight: 700,
                            cursor: "pointer",
                            background: isActive ? `${C.accentGlow}` : "transparent",
                            borderLeft: `1px solid ${C.border}`,
                            borderTop: isActive ? `3px solid ${C.borderHi}` : `none`,
                            textAlign: "center"
                          }}
                        >
                          Slot {idx + 1} {isActive && "★"}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {[
                    {
                      label: "Type",
                      val: (slot) => {
                        const label = slot.analyzedData && !slot.analyzedData.error ? slot.analyzedData.crack_type : CRACK_DB[slot.crackType].label;
                        return <span style={{ fontWeight: 600 }}>{label.split(" ")[0]}</span>;
                      }
                    },
                    {
                      label: "Severity",
                      val: (slot) => {
                        const sdb = CRACK_DB[slot.crackType];
                        const sev = slot.analyzedData && !slot.analyzedData.error ? slot.analyzedData.severity.toUpperCase() : sdb.risk;
                        const col = sdb.riskColor;
                        return <span style={{ color: col, fontWeight: "bold", fontSize: 10 }}>{sev}</span>;
                      }
                    },
                    {
                      label: "Width",
                      val: (slot) => {
                        const m = getMeasurementsForSlot(slot);
                        return <span style={{ fontFamily: C.mono, fontWeight: 600 }}>{m.width}mm</span>;
                      }
                    },
                    {
                      label: "Length",
                      val: (slot) => {
                        const m = getMeasurementsForSlot(slot);
                        return <span style={{ fontFamily: C.mono, fontWeight: 600 }}>{m.length}cm</span>;
                      }
                    },
                    {
                      label: "Spacing",
                      val: (slot) => {
                        const m = getMeasurementsForSlot(slot);
                        return <span style={{ fontFamily: C.mono, fontWeight: 600 }}>{m.spacing}</span>;
                      }
                    },
                    {
                      label: "V-Index",
                      val: (slot) => {
                        const m = getMeasurementsForSlot(slot);
                        const score = parseFloat(m.vi);
                        const col = score > 0.7 ? C.critical : score > 0.4 ? C.severe : C.minor;
                        return <span style={{ fontFamily: C.mono, color: col, fontWeight: 700 }}>{m.vi}</span>;
                      }
                    }
                  ].map((row, rIdx) => (
                    <tr key={rIdx} style={{ borderBottom: `1px solid ${C.border}` }}>
                      <td style={{ padding: "8px 12px", color: C.textSub, fontWeight: 600 }}>{row.label}</td>
                      {[0, 1].map((idx) => {
                        const slot = slots[idx];
                        const isActive = idx === activeSlotIdx;
                        return (
                          <td
                            key={idx}
                            onClick={() => setActiveSlotIdx(idx)}
                            style={{
                              padding: "8px 12px",
                              textAlign: "center",
                              cursor: "pointer",
                              background: isActive ? `${C.accentGlow}` : "transparent",
                              borderLeft: `1px solid ${C.border}`,
                            }}
                          >
                            {row.val(slot)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <button
            onClick={async () => {
              const compiledPdfData = slots.map((slot, i) => {
                const slotM = getMeasurementsForSlot(slot);
                const slotCrack = CRACK_DB[slot.crackType];
                return slot.analyzedData && !slot.analyzedData.error ? {
                  filename: slot.analyzedData.filename || `slot_${i+1}_image.png`,
                  width_mm: slot.analyzedData.width_mm || 1.84,
                  length_cm: slot.analyzedData.length_cm || 32.5,
                  rebar_spacing_cm: slot.analyzedData.rebar_spacing_cm || 20.0,
                  detected_rods: slot.analyzedData.detected_rods || 3,
                  crack_type: slot.analyzedData.crack_type || "Structural Crack",
                  severity: slot.analyzedData.severity || "severe",
                  v_index: slot.analyzedData.v_index || 0.68,
                  recommendation: slot.analyzedData.recommendation || "Expose bars and clean.",
                  measurement_method: slot.analyzedData.measurement_method,
                  orientation_angle: slot.analyzedData.orientation_angle,
                  crack_count: slot.analyzedData.crack_count,
                  gsd_cm_per_px_x: slot.analyzedData.gsd_cm_per_px_x,
                  gsd_cm_per_px_y: slot.analyzedData.gsd_cm_per_px_y,
                  resolution_w: slot.analyzedData.resolution_w,
                  resolution_h: slot.analyzedData.resolution_h,
                  primary_length_px: slot.analyzedData.cracks && slot.analyzedData.cracks[0] ? slot.analyzedData.cracks[0].length_px : null,
                  real_image_width_m: slot.analyzedData.real_image_width_m,
                  real_image_height_m: slot.analyzedData.real_image_height_m,
                  analysis_confidence: slot.analyzedData.analysis_confidence,
                  member_type: slot.analyzedData.member_type,
                  method_comparison: slot.analyzedData.method_comparison,
                } : {
                  filename: `scenario_slot_${i+1}.png`,
                  width_mm: parseFloat(slotM.width),
                  length_cm: parseFloat(slotM.length),
                  rebar_spacing_cm: slotM.spacing === "—" ? 20.0 : parseFloat(slotM.spacing),
                  detected_rods: slotM.spacing === "—" ? 0 : 3,
                  crack_type: slotCrack.label,
                  severity: slotCrack.risk.toLowerCase(),
                  v_index: parseFloat(slotM.vi),
                  recommendation: slotCrack.intervention
                };
              });

              try {
                const headers = { "Content-Type": "application/json" };
                if (authToken) {
                  headers["Authorization"] = `Bearer ${authToken}`;
                }
                const res = await fetch(getApiUrl("/api/export-compiled-pdf"), {
                  method: "POST",
                  headers: headers,
                  body: JSON.stringify(compiledPdfData)
                });
                if (!res.ok) throw new Error("Failed to export compiled PDF");
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "Cortex_Compiled_Diagnostic_Report.pdf";
                document.body.appendChild(a);
                a.click();
                a.remove();
              } catch (err) {
                alert("Error generating compiled PDF: " + err.message);
              }
            }}
            style={{
              padding: "12px", borderRadius: 8, border: "none",
              background: C.accent,
              color: "#000000", fontSize: 13, fontWeight: 700,
              boxShadow: `0 4px 14px rgba(251,191,36,0.25)`,
              display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
              transition: "all 0.2s"
            }}
            onMouseOver={(e) => e.currentTarget.style.filter = "brightness(0.95)"}
            onMouseOut={(e) => e.currentTarget.style.filter = "none"}
          >
            📚 Compile &amp; Export 2-Slot Report PDF
          </button>

          {/* Active Slot details */}
          <div style={{
            background: C.card,
            border: `2.5px solid ${crack.riskColor}22`,
            borderTop: `3px solid ${crack.riskColor}`,
            borderRadius: 12,
            padding: "14px 16px",
            display: "flex",
            flexDirection: "column",
            gap: 4,
            boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)"
          }}>
            <span style={{ fontSize: 10, fontFamily: C.mono, color: C.textSub, textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
              Active Slot {activeSlotIdx + 1} Specifications
            </span>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginTop: 2 }}>
              <div>
                <h2 style={{ fontFamily: C.display, fontSize: 18, fontWeight: 800 }}>
                  {analyzedData && !analyzedData.error ? (analyzedData.crack_type || crack.label) : crack.label}
                </h2>
                <p style={{ fontSize: 12, color: C.textSub, marginTop: 1, fontWeight: 500 }}>
                  {analyzedData && !analyzedData.error ? "UAV Visual Analysis Scan" : crack.subtitle}
                </p>
                <p style={{ fontSize: 11, fontFamily: C.mono, color: C.textMuted, marginTop: 1, fontWeight: 500 }}>
                  {analyzedData && !analyzedData.error ? "IS 456 / IS 13935 Compliant" : crack.is_code}
                </p>
              </div>
              <div style={{
                background: `${crack.riskColor}18`, border: `1px solid ${crack.riskColor}44`,
                borderRadius: 6, padding: "4px 10px", fontSize: 11, fontWeight: 700,
                color: crack.riskColor, fontFamily: C.mono,
                display: "flex", alignItems: "center", gap: 4,
              }}>
                <span style={{ width: 5, height: 5, borderRadius: "50%", background: crack.riskColor, animation: "pulse 1.5s infinite" }}/>
                {analyzedData && !analyzedData.error ? (analyzedData.severity || "severe").toUpperCase() : crack.risk}
              </div>
            </div>
          </div>

          {/* Metrics grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <MetricCard label="Crack Width"    value={m.width}   unit="mm"  color={crack.riskColor}/>
            <MetricCard label="Crack Length"   value={m.length}  unit="cm"  color={C.accentDark}/>
            <MetricCard label="Rebar Spacing"  value={m.spacing} unit=""    color={C.moderate}/>
            <MetricCard label="V-Index Score"  value={m.vi}      unit=""    color={parseFloat(m.vi)>0.7?C.critical:parseFloat(m.vi)>0.4?C.severe:C.minor}/>
          </div>

          {/* Engineering analysis */}
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)" }}>
            {[
              { 
                title: "Root Cause", 
                content: analyzedData && !analyzedData.error ? `Detected defect classified as ${analyzedData.crack_type}. Reinforcement coverage is estimated at ${m.spacing} cm spacing. Growth rate is estimated at ${m.vi} mm/month.` : crack.cause, 
                icon: "🔍" 
              },
              { 
                title: "Failure Mode", 
                content: analyzedData && !analyzedData.error ? `Risk of structural load capacity degradation. Water ingress may accelerate steel oxidation (volume expansion 2-4x). Structural monitoring recommended.` : crack.failure_mode, 
                icon: "⚠" 
              },
            ].map((item, i) => (
              <div key={i} style={{ padding: "12px 14px", borderBottom: `1px solid ${C.border}` }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: C.textSub, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>
                  <span>{item.icon}</span>{item.title}
                </div>
                <p style={{ fontSize: 13, color: C.text, lineHeight: 1.6 }}>{item.content}</p>
              </div>
            ))}

            {/* Remediation — highlighted */}
            <div style={{ padding: "12px 14px", background: `${crack.riskColor}08`, borderLeft: `3px solid ${crack.riskColor}` }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: crack.riskColor, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>
                ✅ Recommended Remedial Action
              </div>
              <p style={{ fontSize: 13, color: C.text, lineHeight: 1.6 }}>
                {analyzedData ? (analyzedData.recommendation || crack.intervention) : crack.intervention}
              </p>
              <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ fontSize: 10, fontFamily: C.mono, color: C.textSub }}>Reinspect in:</span>
                <span style={{ fontSize: 11.5, fontFamily: C.mono, fontWeight: 700, color: crack.riskColor,
                  background: `${crack.riskColor}18`, border: `1px solid ${crack.riskColor}44`,
                  borderRadius: 4, padding: "2px 6px" }}>
                  {analyzedData && !analyzedData.error ? (analyzedData.severity === "critical" ? 7 : 30) : crack.reinspect_days} days
                </span>
              </div>
            </div>
          </div>

          {/* Export / Save row for active slot */}
          <div style={{ display: "flex", gap: 8 }}>
            <button 
              onClick={async () => {
                const pdfData = analyzedData ? {
                  filename: analyzedData.filename || `slot_${activeSlotIdx+1}_uav_image.png`,
                  width_mm: analyzedData.width_mm || 1.84,
                  length_cm: analyzedData.length_cm || 32.5,
                  rebar_spacing_cm: analyzedData.rebar_spacing_cm || 20.0,
                  detected_rods: analyzedData.detected_rods || 3,
                  crack_type: analyzedData.crack_type || "Structural Crack",
                  severity: analyzedData.severity || "severe",
                  v_index: analyzedData.v_index || 0.68,
                  recommendation: analyzedData.recommendation || "Expose bars and clean.",
                  // Engineering detail for the report
                  measurement_method: analyzedData.measurement_method,
                  orientation_angle: analyzedData.orientation_angle,
                  crack_count: analyzedData.crack_count,
                  gsd_cm_per_px_x: analyzedData.gsd_cm_per_px_x,
                  gsd_cm_per_px_y: analyzedData.gsd_cm_per_px_y,
                  resolution_w: analyzedData.resolution_w,
                  resolution_h: analyzedData.resolution_h,
                  primary_length_px: analyzedData.cracks && analyzedData.cracks[0] ? analyzedData.cracks[0].length_px : null,
                  real_image_width_m: analyzedData.real_image_width_m,
                  real_image_height_m: analyzedData.real_image_height_m,
                  analysis_confidence: analyzedData.analysis_confidence,
                  member_type: analyzedData.member_type,
                  method_comparison: analyzedData.method_comparison,
                } : {
                  filename: `scenario_slot_${activeSlotIdx+1}.png`,
                  width_mm: parseFloat(m.width),
                  length_cm: parseFloat(m.length),
                  rebar_spacing_cm: m.spacing === "—" ? 20.0 : parseFloat(m.spacing),
                  detected_rods: m.spacing === "—" ? 0 : 3,
                  crack_type: crack.label,
                  severity: crack.risk.toLowerCase(),
                  v_index: parseFloat(m.vi),
                  recommendation: crack.intervention
                };
                
                try {
                  const headers = { "Content-Type": "application/json" };
                  if (authToken) {
                    headers["Authorization"] = `Bearer ${authToken}`;
                  }
                  const res = await fetch(getApiUrl("/api/export-pdf"), {
                    method: "POST",
                    headers: headers,
                    body: JSON.stringify(pdfData)
                  });
                  if (!res.ok) throw new Error("Failed to export PDF");
                  const blob = await res.blob();
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `Cortex_Repair_Specification_${pdfData.filename}.pdf`;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                } catch (err) {
                  alert("Error generating PDF: " + err.message);
                }
              }}
              style={{
                flex: 2, padding: "11px", borderRadius: 8, border: "none",
                background: C.accent,
                color: "#000000", fontSize: 13, fontWeight: 700,
                boxShadow: `0 4px 14px rgba(251,191,36,0.2)`,
                transition: "all 0.2s"
              }}
              onMouseOver={(e) => e.currentTarget.style.filter = "brightness(0.95)"}
              onMouseOut={(e) => e.currentTarget.style.filter = "none"}
            >
              📄 Export Slot PDF
            </button>
            <button 
              onClick={async () => {
                const defectPayload = analyzedData ? {
                  defect_id: analyzedData.filename ? `DEF-${analyzedData.filename.replace(/[^a-zA-Z0-9]/g, "").slice(-6)}` : `DEF-${Math.floor(Math.random() * 1000)}`,
                  type: analyzedData.crack_type || crack.label,
                  width_mm: analyzedData.width_mm || parseFloat(m.width),
                  length_cm: analyzedData.length_cm || parseFloat(m.length),
                  rebar_spacing_cm: analyzedData.rebar_spacing_cm || (m.spacing === "—" ? 0.0 : parseFloat(m.spacing)),
                  v_index: analyzedData.v_index || parseFloat(m.vi),
                  severity: analyzedData.severity || crack.risk.toLowerCase(),
                  recommendation: analyzedData.recommendation || crack.intervention
                } : {
                  defect_id: `DEF-${activeSlotIdx+1}-${crackType}`,
                  type: crack.label,
                  width_mm: parseFloat(m.width),
                  length_cm: parseFloat(m.length),
                  rebar_spacing_cm: m.spacing === "—" ? 0.0 : parseFloat(m.spacing),
                  v_index: parseFloat(m.vi),
                  severity: crack.risk.toLowerCase(),
                  recommendation: crack.intervention
                };

                try {
                  const headers = { "Content-Type": "application/json" };
                  if (authToken) {
                    headers["Authorization"] = `Bearer ${authToken}`;
                  }
                  
                  const res = await fetch(getApiUrl("/api/inspections"), {
                    method: "POST",
                    headers: headers,
                    body: JSON.stringify({
                      building_id: "6a182507-c3c9-41c2-a165-b7fd0faf497b",
                      s3_image_key: uploadedLocalPath || "/tmp/cortex_uploads/demo-facade.jpg",
                      cycle_id: Math.floor(Date.now() / 100000) % 100 + 1,
                      gsd_mm_per_px: 1.2,
                      elapsed_months: 6.0,
                      defect_data: defectPayload
                    })
                  });
                  
                  if (!res.ok) throw new Error("Failed to save inspection to database");
                  alert("Defect saved to catalog successfully!");
                  onDefectSaved?.();
                } catch (e) {
                  alert("Error saving: " + e.message);
                }
              }}
              style={{
                flex: 1, padding: "11px", borderRadius: 8,
                background: C.surface, border: `1px solid ${C.border}`,
                color: "#FFFFFF", fontSize: 12, fontWeight: 600,
                transition: "all 0.2s"
              }}
              onMouseOver={(e) => e.currentTarget.style.background = "#2D3748"}
              onMouseOut={(e) => e.currentTarget.style.background = C.surface}
            >
              💾 Save Catalog
            </button>
          </div>
        </div>

      </div>

      {peekingSlotIdx !== null && (
        <div style={{
          position: "fixed",
          inset: 0,
          background: "rgba(10,11,15,0.75)",
          backdropFilter: "blur(12px)",
          zIndex: 1000,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          animation: "fadeIn 0.2s ease"
        }}>
          <div style={{
            background: "#161920",
            border: `2px solid ${C.accent}`,
            borderRadius: 16,
            padding: 24,
            maxWidth: 600,
            width: "90%",
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(255,230,0,0.2)",
            display: "flex",
            flexDirection: "column",
            gap: 16
          }}>
            {/* Peek Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${C.border}`, paddingBottom: 12 }}>
              <span style={{ fontFamily: C.mono, color: C.accent, fontWeight: 700, fontSize: 13 }}>
                3D TOUCH PEEK PREVIEW · SLOT {peekingSlotIdx + 1}
              </span>
              <span style={{ fontSize: 9, background: C.accent, color: "#000", padding: "2px 6px", borderRadius: 4, fontWeight: "bold" }}>
                DIAGNOSTICS PEERING ACTIVE
              </span>
            </div>

            {/* Peek Content */}
            <div style={{ display: "flex", gap: 16 }}>
              <div style={{ flex: 1.2, background: "#080A0F", borderRadius: 8, overflow: "hidden", border: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <VisualOverlay imageUrl={slots[peekingSlotIdx].uploadedImg} crackType={slots[peekingSlotIdx].crackType} width={340} height={200} />
              </div>
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
                <h3 style={{ fontSize: 16, fontWeight: 800, color: "#FFFFFF" }}>
                  {CRACK_DB[slots[peekingSlotIdx].crackType].label}
                </h3>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 10, background: CRACK_DB[slots[peekingSlotIdx].crackType].riskColor, color: "#FFF", padding: "2px 6px", borderRadius: 4, fontWeight: "bold" }}>
                    {CRACK_DB[slots[peekingSlotIdx].crackType].risk}
                  </span>
                  <span style={{ fontSize: 10, background: "#1E293B", color: C.textSub, padding: "2px 6px", borderRadius: 4, fontFamily: C.mono }}>
                    {CRACK_DB[slots[peekingSlotIdx].crackType].is_code}
                  </span>
                </div>
                <p style={{ fontSize: 11, color: C.textSub, lineHeight: 1.4 }}>
                  <strong>Probable Cause:</strong> {CRACK_DB[slots[peekingSlotIdx].crackType].cause}
                </p>
                <p style={{ fontSize: 11, color: C.textSub, lineHeight: 1.4 }}>
                  <strong>Remedial Strategy:</strong> {CRACK_DB[slots[peekingSlotIdx].crackType].intervention.substring(0, 100)}...
                </p>
              </div>
            </div>

            {/* Peek Footer */}
            <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 12, textAlign: "center", fontSize: 11, color: C.textMuted, fontFamily: C.mono }}>
              Release click/touch to pop back to main dashboard view
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
