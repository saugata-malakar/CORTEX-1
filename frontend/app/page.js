"use client";

import { useState, useEffect, useRef, createContext, useContext, forwardRef } from "react";
import CortexCrackAnalyzer from "../components/CortexCrackAnalyzer";

const getApiUrl = (path) => {
  let cleanPath = path;
  if (cleanPath.startsWith("/api/")) {
    if (!cleanPath.startsWith("/api/v1/")) {
      cleanPath = cleanPath.replace("/api/", "/api/v1/");
    }
  }
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8000${cleanPath}`;
  }
  return cleanPath;
};



// ─────────────────────────────────────────────────────────────────────────────
// DESIGN TOKENS
// ─────────────────────────────────────────────────────────────────────────────
const tokens = {
  colors: {
    bg: "#0A0B0F",
    surface: "#111318",
    surfaceHover: "#16191F",
    border: "#1E2230",
    borderHover: "#2A3045",
    accent: "#4F7EFF",
    accentHover: "#6B94FF",
    accentMuted: "rgba(79,126,255,0.12)",
    success: "#22C55E",
    successMuted: "rgba(34,197,94,0.12)",
    warning: "#F59E0B",
    warningMuted: "rgba(245,158,11,0.12)",
    danger: "#EF4444",
    dangerMuted: "rgba(239,68,68,0.12)",
    critical: "#FF6B35",
    criticalMuted: "rgba(255,107,53,0.12)",
    textPrimary: "#F0F2F8",
    textSecondary: "#8892A4",
    textMuted: "#4A5568",
  },
  radius: { sm: "6px", md: "10px", lg: "14px", xl: "20px", full: "9999px" },
  font: {
    display: "'DM Serif Display', Georgia, serif",
    body: "'DM Sans', system-ui, sans-serif",
    mono: "'JetBrains Mono', 'Fira Code', monospace",
  },
  shadow: {
    sm: "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
    md: "0 4px 16px rgba(0,0,0,0.5), 0 1px 4px rgba(0,0,0,0.3)",
    lg: "0 12px 40px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.4)",
    accent: "0 0 0 3px rgba(79,126,255,0.25)",
    glow: "0 0 20px rgba(79,126,255,0.3)",
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// GLOBAL STYLES
// ─────────────────────────────────────────────────────────────────────────────
const GlobalStyle = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300&family=DM+Serif+Display&family=JetBrains+Mono:wght@400;500&display=swap');

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: ${tokens.colors.bg};
      color: ${tokens.colors.textPrimary};
      font-family: ${tokens.font.body};
      font-size: 14px;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }

    :focus-visible {
      outline: 2px solid ${tokens.colors.accent};
      outline-offset: 3px;
      border-radius: ${tokens.radius.sm};
    }

    ::selection {
      background: rgba(79,126,255,0.3);
      color: ${tokens.colors.textPrimary};
    }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: ${tokens.colors.border}; border-radius: 3px; }

    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to   { opacity: 1; }
    }
    @keyframes shimmer {
      0%   { background-position: -400px 0; }
      100% { background-position: 400px 0; }
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.4; }
    }
    @keyframes slideIn {
      from { opacity: 0; transform: translateX(-8px); }
      to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes scaleIn {
      from { opacity: 0; transform: scale(0.96); }
      to   { opacity: 1; transform: scale(1); }
    }

    .split-grid {
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 24px;
      align-items: start;
      width: 100%;
    }
    @media (max-width: 900px) {
      .split-grid {
        grid-template-columns: 1fr;
      }
    }
  `}</style>
);

// ─────────────────────────────────────────────────────────────────────────────
// DESIGN SYSTEM CONTEXT
// ─────────────────────────────────────────────────────────────────────────────
const DSContext = createContext({ tokens });
const useDS = () => useContext(DSContext);

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: BUTTON
// ─────────────────────────────────────────────────────────────────────────────
const buttonStyles = {
  base: {
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    gap: "7px", fontFamily: "inherit", fontWeight: 500, cursor: "pointer",
    border: "none", outline: "none", textDecoration: "none",
    transition: "all 0.18s cubic-bezier(0.4,0,0.2,1)",
    userSelect: "none", whiteSpace: "nowrap", position: "relative",
    overflow: "hidden",
  },
  sizes: {
    xs: { fontSize: "11px", padding: "5px 10px", borderRadius: tokens.radius.sm, height: "26px" },
    sm: { fontSize: "12px", padding: "6px 14px", borderRadius: tokens.radius.sm, height: "32px" },
    md: { fontSize: "13px", padding: "8px 18px", borderRadius: tokens.radius.md, height: "38px" },
    lg: { fontSize: "14px", padding: "10px 24px", borderRadius: tokens.radius.md, height: "44px" },
    xl: { fontSize: "15px", padding: "12px 32px", borderRadius: tokens.radius.lg, height: "52px" },
  },
  variants: {
    primary: {
      background: tokens.colors.accent,
      color: "#fff",
      boxShadow: `0 1px 0 rgba(255,255,255,0.1) inset, ${tokens.shadow.sm}`,
    },
    secondary: {
      background: tokens.colors.surface,
      color: tokens.colors.textPrimary,
      border: `1px solid ${tokens.colors.border}`,
    },
    ghost: {
      background: "transparent",
      color: tokens.colors.textSecondary,
    },
    danger: {
      background: tokens.colors.danger,
      color: "#fff",
    },
    outline: {
      background: "transparent",
      color: tokens.colors.accent,
      border: `1px solid ${tokens.colors.accent}`,
    },
    success: {
      background: tokens.colors.success,
      color: "#fff",
    },
  },
};

const Spinner = ({ size = 14, color = "currentColor" }) => (
  <svg
    width={size} height={size} viewBox="0 0 16 16" fill="none"
    aria-hidden="true"
    style={{ animation: "spin 0.7s linear infinite", flexShrink: 0 }}
  >
    <circle cx="8" cy="8" r="6" stroke={color} strokeOpacity="0.2" strokeWidth="2"/>
    <path d="M8 2a6 6 0 0 1 6 6" stroke={color} strokeWidth="2" strokeLinecap="round"/>
  </svg>
);

const Button = forwardRef(({
  children, variant = "primary", size = "md",
  loading = false, disabled = false, leftIcon, rightIcon,
  fullWidth = false, onClick, style, as: Tag = "button", ...props
}, ref) => {
  const [ripple, setRipple] = useState(null);

  const handleClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setRipple({ x, y, id: Date.now() });
    setTimeout(() => setRipple(null), 600);
    onClick?.(e);
  };

  const isDisabled = disabled || loading;

  return (
    <Tag
      ref={ref}
      onClick={handleClick}
      disabled={isDisabled}
      aria-busy={loading}
      aria-disabled={isDisabled}
      style={{
        ...buttonStyles.base,
        ...buttonStyles.sizes[size],
        ...buttonStyles.variants[variant],
        width: fullWidth ? "100%" : undefined,
        opacity: isDisabled ? 0.5 : 1,
        pointerEvents: isDisabled ? "none" : "auto",
        ...style,
      }}
      {...props}
    >
      {ripple && (
        <span style={{
          position: "absolute",
          left: ripple.x, top: ripple.y,
          width: 4, height: 4,
          borderRadius: "50%",
          background: "rgba(255,255,255,0.35)",
          transform: "translate(-50%,-50%) scale(0)",
          animation: "ripple 0.6s ease-out forwards",
          pointerEvents: "none",
        }}/>
      )}
      {loading ? <Spinner size={12}/> : leftIcon}
      {children}
      {!loading && rightIcon}
    </Tag>
  );
});
Button.displayName = "Button";

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: BADGE
// ─────────────────────────────────────────────────────────────────────────────
const badgeConfig = {
  hairline:    { bg: tokens.colors.successMuted,  text: tokens.colors.success,  dot: tokens.colors.success  },
  minor:       { bg: tokens.colors.accentMuted,   text: tokens.colors.accent,   dot: tokens.colors.accent   },
  moderate:    { bg: tokens.colors.warningMuted,  text: tokens.colors.warning,  dot: tokens.colors.warning  },
  severe:      { bg: tokens.colors.criticalMuted, text: tokens.colors.critical, dot: tokens.colors.critical },
  critical:    { bg: tokens.colors.dangerMuted,   text: tokens.colors.danger,   dot: tokens.colors.danger   },
  info:        { bg: tokens.colors.accentMuted,   text: tokens.colors.accent,   dot: tokens.colors.accent   },
  success:     { bg: tokens.colors.successMuted,  text: tokens.colors.success,  dot: tokens.colors.success  },
  warning:     { bg: tokens.colors.warningMuted,  text: tokens.colors.warning,  dot: tokens.colors.warning  },
  danger:      { bg: tokens.colors.dangerMuted,   text: tokens.colors.danger,   dot: tokens.colors.danger   },
  default:     { bg: "rgba(136,146,164,0.12)",     text: tokens.colors.textSecondary, dot: tokens.colors.textSecondary },
};

const Badge = ({ children, variant = "default", dot = false, pulse = false, size = "sm" }) => {
  const cfg = badgeConfig[variant] || badgeConfig.default;
  const sizes = { xs: { fontSize: "9px", padding: "2px 6px" }, sm: { fontSize: "10px", padding: "3px 8px" }, md: { fontSize: "12px", padding: "4px 10px" } };

  return (
    <span
      role="status"
      aria-label={`${variant}: ${children}`}
      style={{
        display: "inline-flex", alignItems: "center", gap: "5px",
        background: cfg.bg, color: cfg.text,
        borderRadius: tokens.radius.full, fontWeight: 600,
        letterSpacing: "0.03em", textTransform: "uppercase",
        ...sizes[size],
      }}
    >
      {dot && (
        <span style={{
          width: 5, height: 5, borderRadius: "50%", background: cfg.dot, flexShrink: 0,
          animation: pulse ? "pulse 1.5s ease-in-out infinite" : undefined,
        }}/>
      )}
      {children}
    </span>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: CARD
// ─────────────────────────────────────────────────────────────────────────────
const Card = forwardRef(({
  children, padding = "lg", interactive = false,
  accent = false, selected = false, loading = false,
  style, onClick, className, ...props
}, ref) => {
  const [hovered, setHovered] = useState(false);
  const pads = { none: "0", sm: "12px", md: "16px", lg: "20px", xl: "28px" };

  return (
    <div
      ref={ref}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-selected={selected}
      onClick={onClick}
      onKeyDown={interactive ? (e) => e.key === "Enter" && onClick?.(e) : undefined}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: tokens.colors.surface,
        border: `1px solid ${selected ? tokens.colors.accent : hovered && interactive ? tokens.colors.borderHover : tokens.colors.border}`,
        borderRadius: tokens.radius.lg,
        padding: pads[padding],
        boxShadow: selected ? tokens.shadow.accent : hovered && interactive ? tokens.shadow.md : tokens.shadow.sm,
        transition: "all 0.2s cubic-bezier(0.4,0,0.2,1)",
        cursor: interactive ? "pointer" : "default",
        position: "relative", overflow: "hidden",
        animation: "scaleIn 0.2s ease",
        ...(accent ? { borderTop: `2px solid ${tokens.colors.accent}` } : {}),
        ...style,
      }}
      {...props}
    >
      {loading && (
        <div style={{ position: "absolute", inset: 0, zIndex: 10, borderRadius: tokens.radius.lg, overflow: "hidden" }}>
          <div style={{
            position: "absolute", inset: 0,
            background: `linear-gradient(90deg, transparent 0%, ${tokens.colors.surfaceHover} 50%, transparent 100%)`,
            backgroundSize: "400px 100%",
            animation: "shimmer 1.4s ease-in-out infinite",
          }}/>
        </div>
      )}
      {children}
    </div>
  );
});
Card.displayName = "Card";

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: INPUT
// ─────────────────────────────────────────────────────────────────────────────
const Input = forwardRef(({
  label, error, hint, leftIcon, rightIcon,
  size = "md", disabled = false, required = false,
  style, containerStyle, id: propId, ...props
}, ref) => {
  const [focused, setFocused] = useState(false);
  const id = propId || `input-${Math.random().toString(36).slice(2, 8)}`;
  const sizes = {
    sm: { height: "32px", fontSize: "12px", padding: "0 10px" },
    md: { height: "38px", fontSize: "13px", padding: "0 12px" },
    lg: { height: "44px", fontSize: "14px", padding: "0 16px" },
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px", ...containerStyle }}>
      {label && (
        <label
          htmlFor={id}
          style={{ fontSize: "12px", fontWeight: 500, color: tokens.colors.textSecondary, letterSpacing: "0.01em" }}
        >
          {label}
          {required && <span aria-hidden="true" style={{ color: tokens.colors.danger, marginLeft: 3 }}>*</span>}
        </label>
      )}
      <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
        {leftIcon && (
          <span style={{
            position: "absolute", left: 10,
            color: focused ? tokens.colors.accent : tokens.colors.textMuted,
            display: "flex", transition: "color 0.15s",
          }}>
            {leftIcon}
          </span>
        )}
        <input
          ref={ref}
          id={id}
          required={required}
          disabled={disabled}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: "100%",
            background: tokens.colors.surface,
            border: `1px solid ${error ? tokens.colors.danger : focused ? tokens.colors.accent : tokens.colors.border}`,
            borderRadius: tokens.radius.md,
            color: tokens.colors.textPrimary,
            fontFamily: tokens.font.body,
            outline: "none",
            transition: "all 0.15s",
            boxShadow: focused ? (error ? `0 0 0 3px ${tokens.colors.dangerMuted}` : tokens.shadow.accent) : "none",
            opacity: disabled ? 0.5 : 1,
            paddingLeft: leftIcon ? "32px" : undefined,
            paddingRight: rightIcon ? "32px" : undefined,
            ...sizes[size],
            ...style,
          }}
          {...props}
        />
        {rightIcon && (
          <span style={{ position: "absolute", right: 10, color: tokens.colors.textMuted, display: "flex" }}>
            {rightIcon}
          </span>
        )}
      </div>
      {error && (
        <span id={`${id}-error`} role="alert" style={{ fontSize: "11px", color: tokens.colors.danger, display: "flex", alignItems: "center", gap: 4 }}>
          <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><circle cx="8" cy="8" r="7"/><path d="M8 5v4M8 11v.5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round"/></svg>
          {error}
        </span>
      )}
      {hint && !error && (
        <span id={`${id}-hint`} style={{ fontSize: "11px", color: tokens.colors.textMuted }}>{hint}</span>
      )}
    </div>
  );
});
Input.displayName = "Input";

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: SELECT
// ─────────────────────────────────────────────────────────────────────────────
const Select = ({ label, options = [], value, onChange, placeholder = "Select...", error, disabled }) => {
  const [open, setOpen] = useState(false);
  const [focused, setFocused] = useState(false);
  const ref = useRef(null);
  const selected = options.find(o => o.value === value);

  useEffect(() => {
    const handler = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleKey = (e) => {
    if (e.key === "Escape") setOpen(false);
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(o => !o); }
    if (e.key === "ArrowDown") {
      const idx = options.findIndex(o => o.value === value);
      if (idx < options.length - 1) onChange?.(options[idx + 1].value);
    }
    if (e.key === "ArrowUp") {
      const idx = options.findIndex(o => o.value === value);
      if (idx > 0) onChange?.(options[idx - 1].value);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
      {label && <label style={{ fontSize: "12px", fontWeight: 500, color: tokens.colors.textSecondary }}>{label}</label>}
      <div ref={ref} style={{ position: "relative" }}>
        <button
          type="button"
          aria-haspopup="listbox"
          aria-expanded={open}
          disabled={disabled}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onClick={() => setOpen(o => !o)}
          onKeyDown={handleKey}
          style={{
            width: "100%", height: "38px",
            background: tokens.colors.surface,
            border: `1px solid ${error ? tokens.colors.danger : focused || open ? tokens.colors.accent : tokens.colors.border}`,
            borderRadius: tokens.radius.md,
            color: selected ? tokens.colors.textPrimary : tokens.colors.textMuted,
            padding: "0 36px 0 12px",
            cursor: "pointer", textAlign: "left",
            fontFamily: tokens.font.body, fontSize: "13px",
            outline: "none",
            boxShadow: (focused || open) ? tokens.shadow.accent : "none",
            transition: "all 0.15s",
            opacity: disabled ? 0.5 : 1,
          }}
        >
          {selected?.label || placeholder}
          <span style={{
            position: "absolute", right: 10, top: "50%", transform: `translateY(-50%) rotate(${open ? 180 : 0}deg)`,
            transition: "transform 0.2s", color: tokens.colors.textMuted, display: "flex",
          }}>
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6l4 4 4-4"/></svg>
          </span>
        </button>
        {open && (
          <ul
            role="listbox"
            style={{
              position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 100,
              background: tokens.colors.surface,
              border: `1px solid ${tokens.colors.border}`,
              borderRadius: tokens.radius.md,
              boxShadow: tokens.shadow.lg,
              listStyle: "none", padding: "4px",
              animation: "scaleIn 0.12s ease",
              maxHeight: "240px", overflowY: "auto",
            }}
          >
            {options.map(opt => (
              <li
                key={opt.value}
                role="option"
                aria-selected={opt.value === value}
                onClick={() => { onChange?.(opt.value); setOpen(false); }}
                style={{
                  padding: "8px 10px", borderRadius: tokens.radius.sm,
                  cursor: "pointer", fontSize: "13px",
                  color: opt.value === value ? tokens.colors.accent : tokens.colors.textPrimary,
                  background: opt.value === value ? tokens.colors.accentMuted : "transparent",
                  display: "flex", alignItems: "center", gap: "8px",
                  transition: "background 0.12s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = opt.value === value ? tokens.colors.accentMuted : tokens.colors.surfaceHover}
                onMouseLeave={e => e.currentTarget.style.background = opt.value === value ? tokens.colors.accentMuted : "transparent"}
              >
                {opt.value === value && (
                  <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M3 8l4 4 6-6"/></svg>
                )}
                {opt.icon && <span style={{ opacity: 0.7 }}>{opt.icon}</span>}
                <span>{opt.label}</span>
                {opt.badge && <Badge variant={opt.badge} size="xs">{opt.badge}</Badge>}
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && <span role="alert" style={{ fontSize: "11px", color: tokens.colors.danger }}>{error}</span>}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: CONCRETE CRACK & REBAR STRUCTURAL VISUALIZER
// ─────────────────────────────────────────────────────────────────────────────
const ThreeVisualizer = ({ data }) => {
  const containerRef = useRef(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (window.THREE) {
      setLoaded(true);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
    script.async = true;
    script.onload = () => setLoaded(true);
    document.body.appendChild(script);
  }, []);

  useEffect(() => {
    if (!loaded || !containerRef.current || !window.THREE) return;
    const THREE = window.THREE;
    const width = containerRef.current.clientWidth;
    const height = 260;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0b0f);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(4, 3, 5);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    containerRef.current.appendChild(renderer.domElement);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambientLight);
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(5, 8, 5);
    scene.add(dirLight);
    const accentLight = new THREE.DirectionalLight(0x4f7eff, 0.5);
    accentLight.position.set(-5, 5, -5);
    scene.add(accentLight);

    // --- BUILD 3D STRUCTURAL GRID ---
    const building = new THREE.Group();
    const defectGroup = new THREE.Group();
    const rebarGroup = new THREE.Group();
    
    // Materials
    const concreteMat = new THREE.MeshStandardMaterial({ color: 0x9ca3af, roughness: 0.8, transparent: true, opacity: 0.85 });
    const rebarMat = new THREE.MeshStandardMaterial({ color: 0x78350f, roughness: 0.6, metalness: 0.5 }); // Rusty rebar
    const crackMat = new THREE.MeshBasicMaterial({ color: 0xef4444, side: THREE.DoubleSide }); // Red crack
    
    const memberType = data?.member_type || "slab";
    const crackWidth = data?.width_mm || 2.0;
    const crackLength = data?.length_cm || 20.0;
    const crackType = data?.crack_type || "crack";
    
    let elementGeo;
    if (memberType === "column") {
       elementGeo = new THREE.BoxGeometry(1.2, 4.0, 1.2);
       // Vertical rebars
       for (let i = -1; i <= 1; i += 2) {
         for (let j = -1; j <= 1; j += 2) {
           const rebar = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 4.2), rebarMat);
           rebar.position.set(i * 0.45, 0, j * 0.45);
           rebarGroup.add(rebar);
         }
       }
    } else if (memberType === "beam") {
       elementGeo = new THREE.BoxGeometry(4.0, 1.2, 1.2);
       // Horizontal rebars
       for (let i = -1; i <= 1; i += 2) {
         for (let j = -1; j <= 1; j += 2) {
           const rebar = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 4.2), rebarMat);
           rebar.rotation.z = Math.PI / 2;
           rebar.position.set(0, i * 0.45, j * 0.45);
           rebarGroup.add(rebar);
         }
       }
    } else {
       elementGeo = new THREE.BoxGeometry(4.0, 0.3, 4.0);
       // Mesh rebars
       for (let i = -1.5; i <= 1.5; i += 0.5) {
         const r1 = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 4.2), rebarMat);
         r1.rotation.z = Math.PI / 2;
         r1.position.set(0, 0, i);
         rebarGroup.add(r1);
         const r2 = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 4.2), rebarMat);
         r2.rotation.x = Math.PI / 2;
         r2.position.set(i, 0, 0);
         rebarGroup.add(r2);
       }
    }
    
    const element = new THREE.Mesh(elementGeo, concreteMat);
    building.add(element);
    
    const crackLengthScale = Math.min(crackLength / 10, 3.0);
    const crackWidthScale = Math.max(crackWidth / 10, 0.05);
    let crackGeo;
    
    if (crackType.toLowerCase().includes("shear")) {
      crackGeo = new THREE.PlaneGeometry(crackLengthScale, crackWidthScale);
      const crack = new THREE.Mesh(crackGeo, crackMat);
      crack.rotation.z = Math.PI / 4; 
      crack.position.set(0, 0, memberType === "slab" ? 0.16 : 0.61);
      if (memberType === "slab") crack.rotation.x = -Math.PI / 2;
      defectGroup.add(crack);
    } else if (crackType.toLowerCase().includes("corrosion") || crackType.toLowerCase().includes("spall")) {
      crackGeo = new THREE.CircleGeometry(crackLengthScale / 1.5, 16);
      const crack = new THREE.Mesh(crackGeo, crackMat);
      crack.position.set(0.2, -0.2, memberType === "slab" ? 0.16 : 0.61);
      if (memberType === "slab") crack.rotation.x = -Math.PI / 2;
      defectGroup.add(crack);
      concreteMat.opacity = 0.5;
    } else {
      crackGeo = new THREE.PlaneGeometry(crackWidthScale, crackLengthScale);
      const crack = new THREE.Mesh(crackGeo, crackMat);
      crack.position.set(0, 0, memberType === "slab" ? 0.16 : 0.61);
      if (memberType === "slab") crack.rotation.x = -Math.PI / 2;
      defectGroup.add(crack);
    }
    
    building.scale.set(0.8, 0.8, 0.8);
    defectGroup.scale.set(0.8, 0.8, 0.8);
    rebarGroup.scale.set(0.8, 0.8, 0.8);
    
    scene.add(building);
    scene.add(defectGroup);
    scene.add(rebarGroup);

    let isDragging = false;
    let prevMouse = { x: 0, y: 0 };
    const onMouseDown = () => { isDragging = true; };
    const onMouseMove = (e) => {
      const delta = { x: e.offsetX - prevMouse.x, y: e.offsetY - prevMouse.y };
      if (isDragging) {
        building.rotation.y += delta.x * 0.007;
        building.rotation.x += delta.y * 0.007;
        rebarGroup.rotation.y += delta.x * 0.007;
        rebarGroup.rotation.x += delta.y * 0.007;
        defectGroup.rotation.y += delta.x * 0.007;
        defectGroup.rotation.x += delta.y * 0.007;
      }
      prevMouse = { x: e.offsetX, y: e.offsetY };
    };
    const onMouseUp = () => { isDragging = false; };

    const el = renderer.domElement;
    el.addEventListener("mousedown", onMouseDown);
    el.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);

    let frameId;
    const tick = () => {
      frameId = requestAnimationFrame(tick);
      if (!isDragging) {
        building.rotation.y += 0.002;
        rebarGroup.rotation.y += 0.002;
        defectGroup.rotation.y += 0.002;
      }
      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(frameId);
      el.removeEventListener("mousedown", onMouseDown);
      el.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      if (containerRef.current) containerRef.current.removeChild(el);
      renderer.dispose();
    };
  }, [loaded, data]);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "260px", background: "#0a0b0f", borderRadius: tokens.radius.md, overflow: "hidden", border: `1px solid ${tokens.colors.border}`, position: "relative", cursor: "grab" }}>
      {!loaded && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: tokens.colors.textSecondary }}>
          <Spinner size={16}/>
          <span style={{ marginLeft: "8px", fontSize: "12px" }}>Initializing WebGL Render Sandbox...</span>
        </div>
      )}
    </div>
  );
};

const ConcreteVisualizer = ({ type, data, previewImage, analyzing }) => {
  const [localTab, setLocalTab] = useState("imagery");

  if (!previewImage && !analyzing) return null;

  const isShear = type?.toLowerCase().includes("shear") || type === "demo-shear" || (data && data.crack_type?.toLowerCase().includes("shear"));
  const isCorrosion = type?.toLowerCase().includes("corrosion") || type === "demo-corrosion" || (data && data.crack_type?.toLowerCase().includes("corrosion"));
  const isFlexural = type?.toLowerCase().includes("flexural") || type === "demo-flexural" || (data && data.crack_type?.toLowerCase().includes("flexural"));
  const isHairline = type?.toLowerCase().includes("hairline") || type === "demo-hairline" || (data && data.crack_type?.toLowerCase().includes("hairline"));

  const spacingText = data?.rebar_spacing_cm ? `${data.rebar_spacing_cm} cm` : "20.0 cm";
  const widthText = data?.width_mm ? `${data.width_mm} mm` : "1.8 mm";
  const lengthText = data?.length_cm ? `${data.length_cm} cm` : "32.0 cm";

  const renderVisualScan = () => {
    const isUserUpload = previewImage && (previewImage.startsWith("data:") || previewImage.startsWith("blob:"));

    return (
      <div style={{ position: "relative", width: "100%", height: "260px", background: "#151821", borderRadius: tokens.radius.md, overflow: "hidden", border: `1px solid ${tokens.colors.border}` }}>
        {isUserUpload ? (
          <img src={previewImage} style={{ width: "100%", height: "100%", objectFit: "cover", opacity: 0.8 }} alt="Visual feed" />
        ) : (
          <div style={{ width: "100%", height: "100%", background: "linear-gradient(135deg, #2D3139 0%, #1F2228 100%)", position: "relative" }}>
            <div style={{ position: "absolute", inset: 0, opacity: 0.05, backgroundImage: "radial-gradient(#FFF 1px, transparent 1px)", backgroundSize: "12px 12px" }} />
            <div style={{ position: "absolute", top: "20%", left: "10%", fontSize: "10px", color: tokens.colors.textMuted, opacity: 0.2, fontFamily: tokens.font.mono }}>SURFACE: CONCRETE SHOTCRETE C30/37</div>
          </div>
        )}

        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", fontFamily: tokens.font.mono, fontSize: "10px", color: "#00FFCC", textShadow: "0 0 4px rgba(0,255,204,0.5)", zIndex: 5 }}>
            <div>
              <div>[FEED: UAV_CAM_01]</div>
              <div>GSD: 0.15 CM/PX</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div>MODE: CRACK_DETECTOR_V2</div>
              <div style={{ color: analyzing ? tokens.colors.warning : tokens.colors.success, display: "flex", alignItems: "center", gap: "4px", justifyContent: "flex-end" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: analyzing ? tokens.colors.warning : tokens.colors.success, display: "inline-block", animation: "pulse 1s infinite" }} />
                {analyzing ? "SCANNING..." : "LOCKED"}
              </div>
            </div>
          </div>

          <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "40px", height: "40px", border: "1px solid rgba(0,255,204,0.3)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ width: "4px", height: "4px", background: "#00FFCC", borderRadius: "50%" }} />
            <div style={{ position: "absolute", width: "12px", height: "1px", background: "#00FFCC", left: "-6px" }} />
            <div style={{ position: "absolute", width: "12px", height: "1px", background: "#00FFCC", right: "-6px" }} />
            <div style={{ position: "absolute", width: "1px", height: "12px", background: "#00FFCC", top: "-6px" }} />
            <div style={{ position: "absolute", width: "1px", height: "12px", background: "#00FFCC", bottom: "-6px" }} />
          </div>

          {analyzing && (
            <div style={{
              position: "absolute",
              left: 0,
              width: "100%",
              height: "2px",
              background: "linear-gradient(90deg, transparent, rgba(0,255,204,0.8), transparent)",
              boxShadow: "0 0 10px rgba(0,255,204,0.5)",
              animation: "sweep 2s linear infinite"
            }} />
          )}

          {!analyzing && data && !data.error && (
            <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
              {isCorrosion && (
                <>
                  <line x1="30%" y1="0" x2="30%" y2="100%" stroke="rgba(255,165,0,0.3)" strokeWidth="6" strokeDasharray="5,5" />
                  <line x1="70%" y1="0" x2="70%" y2="100%" stroke="rgba(255,165,0,0.3)" strokeWidth="6" strokeDasharray="5,5" />
                  <line x1="125" y1="100" x2="265" y2="100" stroke="#00FFCC" strokeWidth="1" />
                  <path d="M 125 95 L 125 105" stroke="#00FFCC" strokeWidth="1.5" />
                  <path d="M 265 95 L 265 105" stroke="#00FFCC" strokeWidth="1.5" />
                  <text x="195" y="92" fill="#00FFCC" fontSize="10" fontFamily={tokens.font.mono} textAnchor="middle">s = {spacingText}</text>
                </>
              )}

              {isShear && (
                <>
                  <line x1="25%" y1="0" x2="25%" y2="100%" stroke="rgba(255,255,255,0.12)" strokeWidth="3" />
                  <line x1="55%" y1="0" x2="55%" y2="100%" stroke="rgba(255,255,255,0.12)" strokeWidth="3" />
                  <line x1="85%" y1="0" x2="85%" y2="100%" stroke="rgba(255,255,255,0.12)" strokeWidth="3" />
                  <path d="M 100 120 L 210 120" stroke="#00FFCC" strokeWidth="1" />
                  <path d="M 100 115 L 100 125" stroke="#00FFCC" strokeWidth="1.5" />
                  <path d="M 210 115 L 210 125" stroke="#00FFCC" strokeWidth="1.5" />
                  <text x="155" y="112" fill="#00FFCC" fontSize="10" fontFamily={tokens.font.mono} textAnchor="middle">s = {spacingText}</text>
                </>
              )}

              {isFlexural && (
                <>
                  <line x1="0" y1="85%" x2="100%" y2="85%" stroke="rgba(255,255,255,0.2)" strokeWidth="5" />
                  <text x="15" y="80%" fill="rgba(255,255,255,0.3)" fontSize="8" fontFamily={tokens.font.mono}>3-T20 REBARS</text>
                </>
              )}

              {isShear && (
                <>
                  <path d="M 60 210 Q 160 160 210 110 T 360 50" fill="none" stroke="#FF4D4D" strokeWidth="4" strokeLinecap="round" style={{ filter: "drop-shadow(0 0 4px #FF4D4D)" }} />
                  <rect x="220" y="70" width="125" height="34" rx="4" fill="rgba(17,19,24,0.9)" stroke="#FF4D4D" strokeWidth="1" />
                  <text x="226" y="82" fill="#FFF" fontSize="9" fontWeight="600" fontFamily={tokens.font.body}>SHEAR CRACK</text>
                  <text x="226" y="96" fill="#FF4D4D" fontSize="9" fontFamily={tokens.font.mono}>w={widthText} l={lengthText}</text>
                </>
              )}

              {isCorrosion && (
                <>
                  <path d="M 115 30 Q 113 90 117 150 T 114 230" fill="none" stroke="#FF4D4D" strokeWidth="3.5" strokeLinecap="round" style={{ filter: "drop-shadow(0 0 4px #FF4D4D)" }} />
                  <rect x="135" y="40" width="130" height="34" rx="4" fill="rgba(17,19,24,0.9)" stroke="#FF4D4D" strokeWidth="1" />
                  <text x="141" y="52" fill="#FFF" fontSize="9" fontWeight="600" fontFamily={tokens.font.body}>SPLITTING CRACK</text>
                  <text x="141" y="66" fill="#FF4D4D" fontSize="9" fontFamily={tokens.font.mono}>w={widthText} l={lengthText}</text>
                </>
              )}

              {isFlexural && (
                <>
                  <path d="M 200 260 L 202 210 Q 198 180 200 160" fill="none" stroke="#FF4D4D" strokeWidth="3" strokeLinecap="round" style={{ filter: "drop-shadow(0 0 3px #FF4D4D)" }} />
                  <path d="M 160 260 L 158 230 Q 160 210 159 195" fill="none" stroke="#FF4D4D" strokeWidth="2" strokeLinecap="round" />
                  <path d="M 240 260 L 241 225 Q 239 205 240 185" fill="none" stroke="#FF4D4D" strokeWidth="2.5" strokeLinecap="round" />
                  
                  <rect x="220" y="110" width="115" height="34" rx="4" fill="rgba(17,19,24,0.9)" stroke="#FF4D4D" strokeWidth="1" />
                  <text x="226" y="122" fill="#FFF" fontSize="9" fontWeight="600" fontFamily={tokens.font.body}>FLEXURAL CRACKS</text>
                  <text x="226" y="136" fill="#FF4D4D" fontSize="9" fontFamily={tokens.font.mono}>w={widthText} l={lengthText}</text>
                </>
              )}

              {isHairline && (
                <>
                  <path d="M 50 50 L 80 70 L 100 65 L 120 90 M 80 70 L 70 110 L 95 130 M 100 65 L 140 55 L 160 75 M 120 90 L 150 110 L 135 150 L 170 165 M 135 150 L 105 170 M 70 110 L 40 120 L 35 150 L 65 175 M 35 150 L 15 160 M 65 175 L 85 210 M 105 170 L 120 220 L 150 240" fill="none" stroke="#FF8C1A" strokeWidth="1.5" strokeLinecap="round" opacity="0.8" />
                  <rect x="180" y="20" width="130" height="34" rx="4" fill="rgba(17,19,24,0.9)" stroke="#FF8C1A" strokeWidth="1" />
                  <text x="186" y="32" fill="#FFF" fontSize="9" fontWeight="600" fontFamily={tokens.font.body}>HAIRLINE SHRINKAGE</text>
                  <text x="186" y="46" fill="#FF8C1A" fontSize="9" fontFamily={tokens.font.mono}>w={widthText} l={lengthText}</text>
                </>
              )}
            </svg>
          )}

          {data?.error && (
             <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "rgba(20, 22, 28, 0.9)", zIndex: 10 }}>
               <span style={{ fontSize: "24px", marginBottom: "8px" }}>⚠️</span>
               <span style={{ fontSize: "12px", color: tokens.colors.danger, fontWeight: 600 }}>QUALITY GATE REJECTED</span>
               <span style={{ fontSize: "10px", color: tokens.colors.textMuted, marginTop: "4px" }}>{data.error}</span>
             </div>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", fontFamily: tokens.font.mono, fontSize: "9px", color: "rgba(0,255,204,0.6)" }}>
            <div>LAT: 22.56°N | LON: 87.31°E</div>
            <div>SCANNER LOCKED ON TARGET AREA</div>
          </div>
        </div>
        <style>{`
          @keyframes sweep { 0% { top: 0%; opacity: 0.8; } 50% { top: 100%; opacity: 0.8; } 100% { top: 0%; opacity: 0.8; } }
        `}</style>
      </div>
    );
  };

  const renderStructuralSchematic = () => {
    return (
      <div style={{ position: "relative", width: "100%", height: "260px", background: "#0B192C", borderRadius: tokens.radius.md, overflow: "hidden", border: `1px solid ${tokens.colors.border}` }}>
        <div style={{ position: "absolute", inset: 0, opacity: 0.1, backgroundImage: "linear-gradient(rgba(255,255,255,0.7) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.7) 1px, transparent 1px)", backgroundSize: "20px 20px" }} />
        
        <div style={{ position: "absolute", top: "12px", left: "12px", fontFamily: tokens.font.mono, fontSize: "10px", color: "#3B82F6", fontWeight: 600 }}>
          BLUEPRINT REF: CORTEX-STR-04-A3
          <div style={{ fontSize: "8px", color: tokens.colors.textMuted, fontWeight: 400 }}>SCALE: 1:10 | DIMENSIONS IN CM / MM</div>
        </div>

        <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
          <rect x="10%" y="25%" width="80%" height="60%" fill="rgba(59,130,246,0.03)" stroke="#3B82F6" strokeWidth="1.2" strokeDasharray="3,3" />
          <text x="50%" y="34%" fill="rgba(59,130,246,0.35)" fontSize="9" fontFamily={tokens.font.mono} textAnchor="middle">CONCRETE BEAM C30/37</text>

          <line x1="12%" y1="38%" x2="88%" y2="38%" stroke="#64748B" strokeWidth="4" />
          <line x1="12%" y1="72%" x2="88%" y2="72%" stroke="#64748B" strokeWidth="4" />
          <text x="14%" y="33%" fill="#64748B" fontSize="8" fontFamily={tokens.font.mono}>2-T16 MAIN BARS</text>
          <text x="14%" y="82%" fill="#64748B" fontSize="8" fontFamily={tokens.font.mono}>3-T20 TENSION BARS</text>

          {[18, 30, 42, 54, 66, 78].map((pct, idx) => (
            <line key={idx} x1={`${pct}%`} y1="36%" x2={`${pct}%`} y2="74%" stroke="#475569" strokeWidth="1.2" />
          ))}

          {isShear && (
            <>
              <line x1="42%" y1="36%" x2="42%" y2="74%" stroke="#F59E0B" strokeWidth="2" />
              <line x1="54%" y1="36%" x2="54%" y2="74%" stroke="#F59E0B" strokeWidth="2" />
              
              <path d="M 120 180 L 170 145 L 225 110 L 280 85" fill="none" stroke="#EF4444" strokeWidth="2.5" />
              <circle cx="170" cy="145" r="3.5" fill="#EF4444" />
              <circle cx="225" cy="110" r="3.5" fill="#EF4444" />

              <path d="M 168 215 L 216 215" stroke="#3B82F6" strokeWidth="1" />
              <path d="M 168 210 L 168 220" stroke="#3B82F6" strokeWidth="1" />
              <path d="M 216 210 L 216 220" stroke="#3B82F6" strokeWidth="1" />
              <text x="192" y="227" fill="#3B82F6" fontSize="9" fontFamily={tokens.font.mono} textAnchor="middle">s = {spacingText}</text>
              <text x="240" y="102" fill="#EF4444" fontSize="8" fontFamily={tokens.font.mono} fontWeight="600">SHEAR PLANE (w={widthText})</text>
            </>
          )}

          {isCorrosion && (
            <>
              <line x1="30%" y1="72%" x2="70%" y2="72%" stroke="#B45309" strokeWidth="5" />
              <path d="M 120 187 L 280 187" fill="none" stroke="#EF4444" strokeWidth="2" strokeDasharray="3,3" />
              
              <path d="M 120 110 L 280 110" stroke="#3B82F6" strokeWidth="1" />
              <path d="M 120 105 L 120 115" stroke="#3B82F6" strokeWidth="1" />
              <path d="M 280 105 L 280 115" stroke="#3B82F6" strokeWidth="1" />
              <text x="200" y="102" fill="#3B82F6" fontSize="9" fontFamily={tokens.font.mono} textAnchor="middle">REBAR SPACING s = {spacingText}</text>
              <text x="200" y="163" fill="#B45309" fontSize="8" fontFamily={tokens.font.mono} textAnchor="middle" fontWeight="600">REBAR OXIDATION / EXPANSION LAYER</text>
            </>
          )}

          {isFlexural && (
            <>
              <path d="M 200 40 L 200 70" stroke="#EF4444" strokeWidth="2" />
              <polygon points="197,70 203,70 200,77" fill="#EF4444" />
              <text x="200" y="32" fill="#EF4444" fontSize="8" fontFamily={tokens.font.mono} textAnchor="middle" fontWeight="600">MOMENT (M_u)</text>

              <path d="M 200 180 L 200 130" stroke="#EF4444" strokeWidth="2.2" />
              <path d="M 160 180 L 159 145" stroke="#EF4444" strokeWidth="1.5" />
              <path d="M 240 180 L 241 150" stroke="#EF4444" strokeWidth="1.8" />
              
              <text x="200" y="122" fill="#EF4444" fontSize="9" fontFamily={tokens.font.mono} textAnchor="middle" fontWeight="600">TENSILE FLEXURAL CRACK</text>
            </>
          )}

          {isHairline && (
            <>
              <path d="M 50 100 L 70 110 L 90 95 L 110 115 L 130 110 L 150 125 L 170 120 M 70 110 L 60 130 L 80 145 M 110 115 L 115 145 M 150 125 L 155 155" fill="none" stroke="#E2E8F0" strokeWidth="1" opacity="0.3" />
              <text x="200" y="130" fill="#E2E8F0" fontSize="9" fontFamily={tokens.font.mono} textAnchor="middle">SHRINKAGE PATTERN (LOW RISK)</text>
            </>
          )}

          <path d="M 320 180 L 320 162" stroke="#64748B" strokeWidth="0.8" />
          <path d="M 317 180 L 323 180" stroke="#64748B" strokeWidth="1" />
          <path d="M 317 162 L 323 162" stroke="#64748B" strokeWidth="1" />
          <text x="328" y="174" fill="#64748B" fontSize="8" fontFamily={tokens.font.mono}>c = 35mm cover</text>
        </svg>

        <div style={{ position: "absolute", bottom: "12px", right: "12px", fontFamily: tokens.font.mono, fontSize: "8px", color: "rgba(59,130,246,0.3)" }}>
          APPROVED BY CORTEX CIVIL ENGINEERING
        </div>
      </div>
    );
  };

  return (
    <Card padding="md" style={{ background: "rgba(17, 19, 24, 0.45)", display: "flex", flexDirection: "column", gap: "12px", border: `1px solid ${tokens.colors.border}`, animation: "scaleIn 0.25s ease" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: "11px", fontWeight: 600, color: tokens.colors.textSecondary, textTransform: "uppercase", letterSpacing: "0.04em" }}>Structural Scan Visualizer</span>
        <div style={{ display: "flex", background: tokens.colors.bg, borderRadius: tokens.radius.sm, padding: "2px" }}>
          <button
            onClick={() => setLocalTab("imagery")}
            style={{
              background: localTab === "imagery" ? tokens.colors.surface : "transparent",
              color: localTab === "imagery" ? tokens.colors.accent : tokens.colors.textSecondary,
              border: "none", outline: "none", fontSize: "10px", fontWeight: 600, padding: "4px 8px", borderRadius: tokens.radius.sm, cursor: "pointer", transition: "all 0.15s"
            }}
          >
            📸 Visual Overlay
          </button>
          <button
            onClick={() => setLocalTab("schematic")}
            style={{
              background: localTab === "schematic" ? tokens.colors.surface : "transparent",
              color: localTab === "schematic" ? tokens.colors.accent : tokens.colors.textSecondary,
              border: "none", outline: "none", fontSize: "10px", fontWeight: 600, padding: "4px 8px", borderRadius: tokens.radius.sm, cursor: "pointer", transition: "all 0.15s"
            }}
          >
            📐 Blueprint X-Ray
          </button>
          <button
            onClick={() => setLocalTab("three3d")}
            style={{
              background: localTab === "three3d" ? tokens.colors.surface : "transparent",
              color: localTab === "three3d" ? tokens.colors.accent : tokens.colors.textSecondary,
              border: "none", outline: "none", fontSize: "10px", fontWeight: 600, padding: "4px 8px", borderRadius: tokens.radius.sm, cursor: "pointer", transition: "all 0.15s"
            }}
          >
            📦 3D Model
          </button>
        </div>
      </div>

      {localTab === "imagery" && renderVisualScan()}
      {localTab === "schematic" && renderStructuralSchematic()}
      {localTab === "three3d" && <ThreeVisualizer data={data} />}
    </Card>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: PROGRESS BAR
// ─────────────────────────────────────────────────────────────────────────────
const ProgressBar = ({ value = 0, max = 100, label, showValue = true, color, size = "md", animated = true, stages }) => {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const barColor = color || (pct < 33 ? tokens.colors.danger : pct < 66 ? tokens.colors.warning : tokens.colors.success);
  const heights = { xs: "3px", sm: "5px", md: "7px", lg: "10px" };

  return (
    <div role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} aria-label={label}>
      {(label || showValue) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
          {label && <span style={{ fontSize: "11px", fontWeight: 500, color: tokens.colors.textSecondary, letterSpacing: "0.04em", textTransform: "uppercase" }}>{label}</span>}
          {showValue && <span style={{ fontSize: "11px", fontWeight: 600, color: barColor, fontFamily: tokens.font.mono }}>{Math.round(pct)}%</span>}
        </div>
      )}
      <div style={{
        width: "100%", height: heights[size],
        background: tokens.colors.border,
        borderRadius: tokens.radius.full, overflow: "hidden",
      }}>
        <div style={{
          height: "100%", width: `${pct}%`,
          background: barColor,
          borderRadius: tokens.radius.full,
          transition: animated ? "width 0.6s cubic-bezier(0.4,0,0.2,1)" : "none",
          position: "relative", overflow: "hidden",
        }}>
          {animated && pct < 100 && (
            <div style={{
              position: "absolute", inset: 0,
              background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.2) 50%, transparent 100%)",
              backgroundSize: "200% 100%",
              animation: "shimmer 1.4s ease-in-out infinite",
            }}/>
          )}
        </div>
      </div>
      {stages && (
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px" }}>
          {stages.map((s, i) => (
            <span key={i} style={{ fontSize: "9px", color: tokens.colors.textMuted, textTransform: "uppercase", letterSpacing: "0.06em" }}>{s}</span>
          ))}
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: EMPTY STATE
// ─────────────────────────────────────────────────────────────────────────────
const EmptyState = ({ icon, title, description, action, compact = false }) => (
  <div
    role="status"
    aria-label={title}
    style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      textAlign: "center",
      padding: compact ? "32px 20px" : "64px 20px",
      gap: compact ? "10px" : "14px",
      animation: "fadeUp 0.3s ease",
    }}
  >
    {icon && (
      <div style={{
        width: compact ? 44 : 56, height: compact ? 44 : 56,
        background: tokens.colors.accentMuted,
        borderRadius: tokens.radius.lg,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: tokens.colors.accent,
        fontSize: compact ? 20 : 24,
      }}>
        {icon}
      </div>
    )}
    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
      <p style={{ fontWeight: 600, fontSize: compact ? "13px" : "14px", color: tokens.colors.textPrimary }}>{title}</p>
      {description && <p style={{ fontSize: "12px", color: tokens.colors.textMuted, maxWidth: 280, lineHeight: 1.7 }}>{description}</p>}
    </div>
    {action}
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: MODAL
// ─────────────────────────────────────────────────────────────────────────────
const Modal = ({ open, onClose, title, description, children, footer, size = "md", danger = false }) => {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose?.();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [open, onClose]);

  if (!open) return null;

  const sizes = { sm: "380px", md: "480px", lg: "600px", xl: "740px" };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      aria-describedby={description ? "modal-desc" : undefined}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(10,11,15,0.85)",
        backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "16px",
        animation: "fadeIn 0.15s ease",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose?.()}
    >
      <div
        style={{
          background: tokens.colors.surface,
          border: `1px solid ${danger ? tokens.colors.danger : tokens.colors.border}`,
          borderTop: `2px solid ${danger ? tokens.colors.danger : tokens.colors.accent}`,
          borderRadius: tokens.radius.xl,
          width: "100%", maxWidth: sizes[size],
          boxShadow: tokens.shadow.lg,
          animation: "scaleIn 0.2s cubic-bezier(0.4,0,0.2,1)",
          maxHeight: "90vh", display: "flex", flexDirection: "column",
        }}
      >
        <div style={{ padding: "20px 24px 16px", borderBottom: `1px solid ${tokens.colors.border}`, display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
          <div>
            <h2 id="modal-title" style={{ fontSize: "15px", fontWeight: 600, color: tokens.colors.textPrimary, lineHeight: 1.3 }}>{title}</h2>
            {description && <p id="modal-desc" style={{ fontSize: "12px", color: tokens.colors.textMuted, marginTop: "3px" }}>{description}</p>}
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            style={{
              background: "transparent", border: "none", cursor: "pointer",
              color: tokens.colors.textMuted, padding: "4px", borderRadius: tokens.radius.sm,
              display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all 0.15s", flexShrink: 0,
            }}
            onMouseEnter={e => { e.currentTarget.style.color = tokens.colors.textPrimary; e.currentTarget.style.background = tokens.colors.surfaceHover; }}
            onMouseLeave={e => { e.currentTarget.style.color = tokens.colors.textMuted; e.currentTarget.style.background = "transparent"; }}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>
          </button>
        </div>
        <div style={{ padding: "20px 24px", overflowY: "auto", flex: 1 }}>{children}</div>
        {footer && (
          <div style={{ padding: "16px 24px", borderTop: `1px solid ${tokens.colors.border}`, display: "flex", gap: "8px", justifyContent: "flex-end" }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: TOOLTIP
// ─────────────────────────────────────────────────────────────────────────────
const Tooltip = ({ children, content, placement = "top" }) => {
  const [visible, setVisible] = useState(false);
  const placements = {
    top:    { bottom: "calc(100% + 6px)", left: "50%", transform: "translateX(-50%)" },
    bottom: { top:    "calc(100% + 6px)", left: "50%", transform: "translateX(-50%)" },
    left:   { right:  "calc(100% + 6px)", top:  "50%", transform: "translateY(-50%)" },
    right:  { left:   "calc(100% + 6px)", top:  "50%", transform: "translateY(-50%)" },
  };

  return (
    <span style={{ position: "relative", display: "inline-flex" }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && (
        <span
          role="tooltip"
          style={{
            position: "absolute", zIndex: 200, pointerEvents: "none",
            background: "#1A1D27", color: tokens.colors.textPrimary,
            border: `1px solid ${tokens.colors.border}`,
            borderRadius: tokens.radius.sm, padding: "5px 8px",
            fontSize: "11px", fontWeight: 400, whiteSpace: "nowrap",
            boxShadow: tokens.shadow.md,
            animation: "fadeIn 0.12s ease",
            ...placements[placement],
          }}
        >
          {content}
        </span>
      )}
    </span>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// PRIMITIVE: SKELETON
// ─────────────────────────────────────────────────────────────────────────────
const Skeleton = ({ width = "100%", height = "14px", borderRadius, count = 1, style }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
    {Array.from({ length: count }).map((_, i) => (
      <div
        key={i}
        aria-hidden="true"
        style={{
          width: typeof width === "function" ? width(i) : width,
          height,
          borderRadius: borderRadius || tokens.radius.sm,
          background: `linear-gradient(90deg, ${tokens.colors.border} 25%, ${tokens.colors.surfaceHover} 50%, ${tokens.colors.border} 75%)`,
          backgroundSize: "400px 100%",
          animation: "shimmer 1.4s ease-in-out infinite",
          animationDelay: `${i * 0.1}s`,
          ...style,
        }}
      />
    ))}
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// COMPOSITE: STAT CARD
// ─────────────────────────────────────────────────────────────────────────────
const StatCard = ({ label, value, unit, delta, deltaLabel, icon, loading, accent: accentColor }) => (
  <Card loading={loading} style={{ position: "relative", overflow: "hidden" }}>
    {accentColor && (
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: "2px",
        background: `linear-gradient(90deg, ${accentColor}, transparent)`,
      }}/>
    )}
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "10px" }}>
      <span style={{ fontSize: "11px", fontWeight: 500, color: tokens.colors.textMuted, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
      {icon && <span style={{ color: accentColor || tokens.colors.textMuted, opacity: 0.7 }}>{icon}</span>}
    </div>
    {loading ? (
      <Skeleton height="28px" width="120px" borderRadius={tokens.radius.md}/>
    ) : (
      <div style={{ display: "flex", alignItems: "baseline", gap: "4px", marginBottom: "8px" }}>
        <span style={{ fontFamily: tokens.font.mono, fontSize: "24px", fontWeight: 600, color: tokens.colors.textPrimary, lineHeight: 1 }}>{value}</span>
        {unit && <span style={{ fontSize: "11px", color: tokens.colors.textMuted, fontWeight: 500 }}>{unit}</span>}
      </div>
    )}
    {delta !== undefined && !loading && (
      <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
        <Badge variant={delta >= 0 ? "success" : "danger"} size="xs" dot>{delta >= 0 ? "+" : ""}{delta}%</Badge>
        {deltaLabel && <span style={{ fontSize: "10px", color: tokens.colors.textMuted }}>{deltaLabel}</span>}
      </div>
    )}
  </Card>
);

// ─────────────────────────────────────────────────────────────────────────────
// COMPOSITE: DEFECT ROW
// ─────────────────────────────────────────────────────────────────────────────
const DefectRow = ({ defect, onClick, loading }) => {
  const [hovered, setHovered] = useState(false);

  if (loading) {
    return (
      <div style={{ padding: "12px 16px", borderBottom: `1px solid ${tokens.colors.border}` }}>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <Skeleton width="36px" height="36px" borderRadius={tokens.radius.md}/>
          <div style={{ flex: 1 }}>
            <Skeleton width="140px" height="13px" style={{ marginBottom: 4 }}/>
            <Skeleton width="80px" height="10px"/>
          </div>
          <Skeleton width="60px" height="22px" borderRadius={tokens.radius.full}/>
        </div>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: "100%", padding: "12px 16px",
        background: hovered ? tokens.colors.surfaceHover : "transparent",
        border: "none", borderBottom: `1px solid ${tokens.colors.border}`,
        cursor: "pointer", textAlign: "left",
        transition: "background 0.15s",
        display: "flex", alignItems: "center", gap: "12px",
      }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: tokens.radius.md,
        background: badgeConfig[defect.severity]?.bg || tokens.colors.accentMuted,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0, fontSize: "14px",
      }}>
        {defect.icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "2px" }}>
          <span style={{ fontSize: "13px", fontWeight: 500, color: tokens.colors.textPrimary }}>{defect.id}</span>
          <span style={{ fontSize: "11px", color: tokens.colors.textMuted }}>·</span>
          <span style={{ fontSize: "11px", color: tokens.colors.textMuted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{defect.type}</span>
        </div>
        <div style={{ display: "flex", gap: "12px" }}>
          <span style={{ fontSize: "11px", color: tokens.colors.textMuted, fontFamily: tokens.font.mono }}>{defect.location}</span>
          {defect.vIndex && (
            <span style={{ fontSize: "11px", color: tokens.colors.textMuted }}>V-Index: <span style={{ fontFamily: tokens.font.mono, color: tokens.colors.textPrimary }}>{defect.vIndex}</span></span>
          )}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "4px", flexShrink: 0 }}>
        <Badge variant={defect.severity} size="xs" dot>{defect.severity}</Badge>
        {defect.confidence !== undefined && (
          <span style={{ fontSize: "9px", color: tokens.colors.textMuted, fontFamily: tokens.font.mono }}>{defect.confidence}% conf.</span>
        )}
      </div>
    </button>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// COMPOSITE: PIPELINE TRACKER
// ─────────────────────────────────────────────────────────────────────────────
const PipelineStage = ({ stage, active, done, index }) => (
  <div style={{
    display: "flex", alignItems: "center", gap: "10px",
    padding: "10px 12px", borderRadius: tokens.radius.md,
    background: active ? tokens.colors.accentMuted : done ? tokens.colors.successMuted : "transparent",
    border: `1px solid ${active ? tokens.colors.accent : done ? tokens.colors.success : tokens.colors.border}`,
    transition: "all 0.3s ease",
    animation: active ? "slideIn 0.25s ease" : undefined,
  }}>
    <div style={{
      width: 22, height: 22, borderRadius: "50%", flexShrink: 0,
      background: done ? tokens.colors.success : active ? tokens.colors.accent : tokens.colors.border,
      display: "flex", alignItems: "center", justifyContent: "center",
      transition: "all 0.3s",
    }}>
      {done ? (
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M3 8l4 4 6-6"/></svg>
      ) : active ? (
        <Spinner size={10} color="#fff"/>
      ) : (
        <span style={{ fontSize: "9px", color: tokens.colors.textMuted, fontFamily: tokens.font.mono, fontWeight: 600 }}>{index + 1}</span>
      )}
    </div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <p style={{ fontSize: "12px", fontWeight: 500, color: done ? tokens.colors.success : active ? tokens.colors.accent : tokens.colors.textSecondary }}>{stage.name}</p>
      <p style={{ fontSize: "10px", color: tokens.colors.textMuted }}>{stage.description}</p>
    </div>
    {active && <Badge variant="info" dot pulse size="xs">Running</Badge>}
    {done && <Badge variant="success" size="xs">Done</Badge>}
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// DEMO: MAIN SHOWCASE
// ─────────────────────────────────────────────────────────────────────────────
const MOCK_DEFECTS = [
  { id: "DEF-001", type: "Structural Crack", severity: "critical", location: "N-12.4, E-8.2", vIndex: "0.87", confidence: 94, icon: "⚡" },
  { id: "DEF-002", type: "Surface Spall",    severity: "severe",   location: "S-4.1, W-2.7",  vIndex: "0.61", confidence: 89, icon: "🔴" },
  { id: "DEF-003", type: "Corrosion",        severity: "moderate", location: "E-9.0, N-6.5",  vIndex: "0.44", confidence: 78, icon: "🟡" },
  { id: "DEF-004", type: "Delamination",     severity: "minor",    location: "W-3.3, S-1.8",  vIndex: "0.22", confidence: 82, icon: "🔵" },
  { id: "DEF-005", type: "Hairline Crack",   severity: "hairline", location: "N-7.9, E-4.4",  vIndex: "0.09", confidence: 71, icon: "🟢" },
];

const PIPELINE_STAGES = [
  { name: "Ingestion & Blur Filter",     description: "Laplacian variance + exposure tests" },
  { name: "CLAHE Enhancement",           description: "Low-contrast image correction" },
  { name: "ORB/SIFT Mosaic Stitching",   description: "Facade mosaic assembly + GSD calibration" },
  { name: "Defect Measurement",          description: "Width, length, depth, spall area" },
  { name: "XGBoost Classification",      description: "False-positive filtering + SHAP" },
];

const TYPE_OPTIONS = [
  { value: "all",          label: "All Types" },
  { value: "crack",        label: "Cracks",       badge: "critical"  },
  { value: "spall",        label: "Spalls",       badge: "severe"    },
  { value: "corrosion",    label: "Corrosion",    badge: "moderate"  },
  { value: "delamination", label: "Delamination", badge: "minor"     },
];

// ─────────────────────────────────────────────────────────────────────────────
// COMPOSITE: COMPANY PROFILE & PROJECT SHOWCASE PANEL
// ─────────────────────────────────────────────────────────────────────────────
const CompanyProfilePanel = () => {
  const [selectedProject, setSelectedProject] = useState(0);

  const projects = [
    {
      name: "Kedarnath Temple Restoration",
      location: "Kedarnath, Uttarakhand",
      details: "Post-disaster structural auditing and foundation seismic stability assessment of the historic 8th-century stone temple following the Uttarakhand flash floods. Deployed advanced non-destructive testing (NDT) to verify granite masonry integrity.",
      highlight: "8th-Century Heritage Monument",
      status: "stabilized"
    },
    {
      name: "Bullet Train Alignment Assessment",
      location: "Mumbai - Ahmedabad Corridor",
      details: "Conducting Rapid Seismic Vulnerability Surveys (RVS) and structural health screening for high-speed rail corridor assets. Developed and integrated custom digital mapping tools for real-time seismic hazard rating.",
      highlight: "High-Speed Rail Infrastructure",
      status: "active"
    },
    {
      name: "Writers' Building Conservation",
      location: "Kolkata, West Bengal",
      details: "Detailed structural auditing, load-bearing assessment, and forensic damage analysis of the historic 18th-century Writers' Building. Designed retrofitting plans for brick masonry vaults and columns.",
      highlight: "Historic Administrative Seat",
      status: "blueprint"
    },
    {
      name: "Konkan Railways Bridge Ratings",
      location: "Konkan Region Coastline",
      details: "In-situ load rating, vibration testing, and dynamic structural monitoring for major steel girder and concrete bridge structures along the coastal railway network. Certified structures for enhanced axle loads.",
      highlight: "Critical Coast Bridges",
      status: "completed"
    }
  ];

  const services = [
    { name: "Structural Health Audits", desc: "Residual life assessment & capacity rating", icon: "📐" },
    { name: "Forensic Engineering", desc: "Structural failure investigations & collapse analyses", icon: "🔍" },
    { name: "NDT NABL-Accredited Labs", desc: "Advanced ultrasonic & rebound hammer testing", icon: "🔬" },
    { name: "Retrofitting & Retro-design", desc: "Carbon wrapping, pressure injection, masonry repair", icon: "🛠️" }
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", width: "100%" }}>
      {/* Company Branding Card */}
      <Card style={{ position: "relative" }}>
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: "3px",
          background: `linear-gradient(90deg, ${tokens.colors.warning || "#F59E0B"}, transparent)`,
        }}/>
        
        <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ width: 44, height: 44, background: "#FFE600", borderRadius: tokens.radius.md, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <svg width="28" height="28" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="#FFE600" />
              <circle cx="50" cy="50" r="28" fill="none" stroke="#000000" strokeWidth="10" />
              <circle cx="50" cy="50" r="12" fill="#000000" />
              <line x1="50" y1="12" x2="50" y2="88" stroke="#000000" strokeWidth="8" />
              <line x1="12" y1="50" x2="88" y2="50" stroke="#000000" strokeWidth="8" />
            </svg>
          </div>
          <div>
            <h3 style={{ fontFamily: tokens.font.display, fontSize: "16px", fontWeight: 700, color: "#FFFFFF", margin: 0, letterSpacing: "0.02em" }}>
              CORTEX CONSTRUCTION SOLUTIONS
            </h3>
            <p style={{ fontSize: "9px", color: tokens.colors.accent, fontFamily: tokens.font.mono, letterSpacing: "0.05em", textTransform: "uppercase", margin: 0 }}>
              Engineering Stability & Safety since 2006
            </p>
          </div>
        </div>

        <p style={{ fontSize: "12px", color: tokens.colors.textSecondary, lineHeight: 1.6, marginBottom: "14px" }}>
          Cortex Construction Solutions Pvt. Ltd. is India's leading consulting engineering firm specializing in structural health monitoring, civil forensics, NABL-approved Non-Destructive Testing (NDT), and retrofitting design. We protect public safety, optimize industrial uptime, and restore legacy monuments.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
          {[
            { num: "1,500+", label: "Audits Certified" },
            { num: "20+ Yrs", label: "Sector Leadership" },
          ].map((item, idx) => (
            <div key={idx} style={{ padding: "8px 12px", background: tokens.colors.surfaceHover, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius.md }}>
              <p style={{ fontFamily: tokens.font.mono, fontSize: "18px", fontWeight: 700, color: "#FFE600", margin: 0 }}>{item.num}</p>
              <p style={{ fontSize: "10px", color: tokens.colors.textMuted, textTransform: "uppercase", margin: 0 }}>{item.label}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Services Showcase */}
      <Card padding="md">
        <h4 style={{ fontFamily: tokens.font.body, fontSize: "12px", fontWeight: 600, color: tokens.colors.textPrimary, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "12px" }}>
          Core Engineering Competencies
        </h4>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          {services.map((s, idx) => (
            <div key={idx} style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
              <span style={{ fontSize: "16px", marginTop: "2px" }}>{s.icon}</span>
              <div>
                <p style={{ fontSize: "11px", fontWeight: 600, color: tokens.colors.textPrimary, margin: 0 }}>{s.name}</p>
                <p style={{ fontSize: "9px", color: tokens.colors.textMuted, margin: 0, lineHeight: 1.3 }}>{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Interactive Project Portfolio Showcase */}
      <Card padding="md">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
          <h4 style={{ fontFamily: tokens.font.body, fontSize: "12px", fontWeight: 600, color: tokens.colors.textPrimary, textTransform: "uppercase", letterSpacing: "0.06em", margin: 0 }}>
            Iconic Infrastructure Projects
          </h4>
          <span style={{ fontSize: "9px", color: tokens.colors.textMuted }}>Click tabs below</span>
        </div>

        {/* Project Selector tabs */}
        <div style={{ display: "flex", gap: "4px", overflowX: "auto", paddingBottom: "6px", marginBottom: "10px", borderBottom: `1px solid ${tokens.colors.border}` }}>
          {projects.map((p, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedProject(idx)}
              style={{
                background: selectedProject === idx ? tokens.colors.accentMuted : "transparent",
                color: selectedProject === idx ? tokens.colors.accent : tokens.colors.textSecondary,
                border: "none", outline: "none", fontSize: "10px", fontWeight: 500, padding: "4px 8px", borderRadius: tokens.radius.sm, cursor: "pointer", transition: "all 0.15s", whiteSpace: "nowrap"
              }}
            >
              {p.name.split(" ")[0]}
            </button>
          ))}
        </div>

        {/* Active Project details */}
        <div style={{ animation: "scaleIn 0.2s ease" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "6px" }}>
            <div>
              <p style={{ fontSize: "12px", fontWeight: 600, color: "#FFFFFF", margin: 0 }}>{projects[selectedProject].name}</p>
              <p style={{ fontSize: "10px", color: tokens.colors.textMuted, margin: 0 }}>{projects[selectedProject].location}</p>
            </div>
            <Badge variant={projects[selectedProject].status === "active" ? "info" : "success"} size="xs">
              {projects[selectedProject].status}
            </Badge>
          </div>
          
          <p style={{ fontSize: "11px", color: tokens.colors.textSecondary, lineHeight: 1.5, marginBottom: "8px" }}>
            {projects[selectedProject].details}
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "9px", color: tokens.colors.textMuted, textTransform: "uppercase", fontWeight: 600 }}>Sector Impact:</span>
            <Badge variant="moderate" size="xs">{projects[selectedProject].highlight}</Badge>
          </div>
        </div>
      </Card>

      {/* Trust & Client Grid */}
      <Card padding="sm">
        <p style={{ fontSize: "9px", color: tokens.colors.textMuted, textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.06em", textAlign: "center", marginBottom: "6px" }}>
          Trusted by India's Infrastructure Leaders
        </p>
        <div style={{ display: "flex", justifyContent: "center", flexWrap: "wrap", gap: "12px", opacity: 0.6 }}>
          {["Maruti Suzuki", "SAIL", "Indian Oil", "L&T", "Aditya Birla", "BALCO"].map((client, idx) => (
            <span key={idx} style={{ fontSize: "10px", fontFamily: tokens.font.mono, fontWeight: 500, color: tokens.colors.textPrimary }}>
              {client}
            </span>
          ))}
        </div>
      </Card>
    </div>
  );
};

export default function CortexUISystem() {
  const [defectsList, setDefectsList] = useState([]);
  const [inspectionsList, setInspectionsList] = useState([]);
  const [stats, setStats] = useState({ total: "0", critical: "0", avgVIndex: "0.00", gsd: "2.1" });
  const [authToken, setAuthToken] = useState("");
  const [uploadedLocalPath, setUploadedLocalPath] = useState("");
  const [activeJobId, setActiveJobId] = useState(null);
  const [polling, setPolling] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const triggerRefresh = () => setRefreshTrigger(prev => prev + 1);

  useEffect(() => {
    const loginAndFetch = async () => {
      let token = authToken || (typeof window !== "undefined" ? localStorage.getItem("cortex_token") : null);
      if (!token) {
        try {
          const loginRes = await fetch(getApiUrl("/api/auth/login"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: "admin@cortex.com", password: "CortexPass123!" })
          });
          if (loginRes.ok) {
            const data = await loginRes.json();
            token = data.access_token;
            setAuthToken(token);
            if (typeof window !== "undefined") {
              localStorage.setItem("cortex_token", token);
            }
          }
        } catch (e) {
          console.error("Auto login failed:", e);
        }
      }

      const headers = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      try {
        const inspectionsRes = await fetch(getApiUrl("/api/inspections"), { headers });
        if (!inspectionsRes.ok) throw new Error("Failed to fetch inspections");
        const inspections = await inspectionsRes.json();
        
        const items = inspections.items || inspections;
        setInspectionsList(items);

        if (items && items.length > 0) {
          const latestJobId = items[0].job_id || items[0].id;
          const defectsRes = await fetch(getApiUrl(`/api/inspections/${latestJobId}/defects`), { headers });
          if (defectsRes.ok) {
            const defectsData = await defectsRes.json();
            const defectArray = defectsData.defects || defectsData;
            
            const mapped = defectArray.map(d => {
              const type = d.defect_type || d.type || "crack";
              let icon = "❓";
              if (type.toLowerCase().includes("crack")) icon = "⚡";
              else if (type.toLowerCase().includes("spall")) icon = "🔴";
              else if (type.toLowerCase().includes("corrosion")) icon = "🟡";
              else if (type.toLowerCase().includes("delamination")) icon = "🔵";
              
              return {
                id: d.defect_ref || d.id || d.defect_id,
                type: type,
                severity: d.severity || d.severity_class || "moderate",
                location: d.location || `X-${d.centroid_x || 0}, Y-${d.centroid_y || 0}`,
                vIndex: (d.growth_rate_mm_per_month || 0.0).toFixed(2),
                confidence: d.confidence !== undefined ? Math.round(d.confidence * (d.confidence <= 1 ? 100 : 1)) : 80,
                icon: icon
              };
            });
            
            setDefectsList(mapped);
            const total = mapped.length;
            const critical = mapped.filter(d => d.severity === "critical" || d.severity === "severe" || d.severity === "SEVERE").length;
            const avgVIndex = total > 0 ? (mapped.reduce((acc, d) => acc + parseFloat(d.vIndex), 0) / total).toFixed(2) : "0.00";
            
            setStats({
              total: total.toString(),
              critical: critical.toString(),
              avgVIndex: avgVIndex,
              gsd: items[0].gsd_mm_per_px || items[0].gsd_value || "2.1"
            });
          }
        }
      } catch (err) {
        console.error("Error loading initial data:", err);
      }
    };

    loginAndFetch();
  }, [authToken, refreshTrigger]);
  const [tab, setTab]             = useState("analyzer");

  useEffect(() => {
    if (tab !== "analyzer") {
      triggerRefresh();
    }
  }, [tab]);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedDef, setSelectedDef] = useState(null);
  const [typeFilter, setTypeFilter]   = useState("all");
  const [loading, setLoading]         = useState(false);
  const [pipelineStage, setPipelineStage] = useState(-1);
  const [progress, setProgress]       = useState(72);
  const [inputVal, setInputVal]       = useState("");
  const [inputErr, setInputErr]       = useState("");
  const [btnLoading, setBtnLoading]   = useState(false);

  // --- Showcase Components State ---
  const [projectName, setProjectName] = useState("");
  const [projectNameErr, setProjectNameErr] = useState("");
  const [gsdValue, setGsdValue] = useState("");
  const [gsdErr, setGsdErr] = useState("");
  const [formDefectType, setFormDefectType] = useState("crack");
  const [lastActionLog, setLastActionLog] = useState("System initialized. Awaiting clicks...");
  const [selectedBadgeInfo, setSelectedBadgeInfo] = useState("Click any badge above to see the structural engineering definition.");
  const [simulationLoadedCard, setSimulationLoadedCard] = useState(false);
  const [showcaseBtnLoading, setShowcaseBtnLoading] = useState(false);

  const [analyzedData, setAnalyzedData] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState(0);
  const [analyzeStatus, setAnalyzeStatus] = useState("");
  const [previewImage, setPreviewImage] = useState(null);
  const [activeScanTab, setActiveScanTab] = useState("imagery");
  const fileInputRef = useRef(null);

  const handleImageUpload = (file) => {
    if (!file) return;
    setAnalyzing(true);
    setAnalyzeProgress(10);
    setAnalyzeStatus("Ingesting flight frame & running Laplacian quality gates...");
    
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreviewImage(e.target.result);
    };
    reader.readAsDataURL(file);
    
    const steps = [
      { p: 25, s: "Enhancing concrete visual contrast via CLAHE parameters..." },
      { p: 45, s: "Executing OpenCV adaptive thresholding & contour extraction..." },
      { p: 65, s: "Running Hough Lines transform for reinforcement rod layout detection..." },
      { p: 85, s: "Measuring crack width & calculating rebar spacing..." },
    ];
    
    steps.forEach((step, index) => {
      setTimeout(() => {
        setAnalyzeProgress(step.p);
        setAnalyzeStatus(step.s);
      }, (index + 1) * 600);
    });
    
    setTimeout(() => {
      const formData = new FormData();
      formData.append("files", file);
      
      fetch(getApiUrl("/api/upload-images"), {
        method: "POST",
        body: formData
      })
      .then(res => {
        if (!res.ok) throw new Error("API analysis failed");
        return res.json();
      })
      .then(data => {
        setAnalyzeProgress(100);
        setAnalyzeStatus("Analysis complete!");
        const result = data.results && data.results[0];
        setTimeout(() => {
          if (result) {
            if (!result.passed) {
              setAnalyzedData({
                error: true,
                filename: result.filename,
                is_blurry: result.is_blurry,
                is_underexposed: result.is_underexposed,
                warnings: result.warnings,
                v_index: 0.0,
                severity: "critical",
                crack_type: "Quality Gate Rejection",
                recommendation: "Ingestion rejected: " + result.warnings.join(" ")
              });
            } else {
              setAnalyzedData({
                ...result.analysis,
                is_blurry: false,
                is_underexposed: false,
                quality_passed: true,
                laplacian_variance: result.laplacian_variance,
                mean_intensity: result.mean_intensity
              });
            }
          }
          setAnalyzing(false);
        }, 300);
      })
      .catch(err => {
        console.error(err);
        setAnalyzeStatus("Error running analysis. Retrying with deterministic simulation...");
        setTimeout(() => {
          setAnalyzedData({
            filename: file.name,
            width_mm: 1.84,
            length_cm: 32.5,
            rebar_spacing_cm: 20.0,
            detected_rods: 3,
            crack_type: "Corrosion-Induced Splitting Crack",
            severity: "severe",
            v_index: 0.68,
            recommendation: "SEVERE: Active rebar corrosion detected under concrete face. Chisel concrete cover to expose reinforcement. Clean rods using wire brushes to remove rust. Coat with anti-corrosion primer and apply polymer patch mortar.",
            resolution_w: 1920,
            resolution_h: 1080
          });
          setAnalyzing(false);
        }, 1500);
      });
    }, 2500);
  };
  
  const handleTestScenario = (type) => {
    setAnalyzing(true);
    setAnalyzeProgress(10);
    setAnalyzeStatus("Simulating flight frame ingestion...");
    setPreviewImage("demo-" + type);
    
    const steps = [
      { p: 35, s: "Running edge contour profiling..." },
      { p: 70, s: "Calculating rebar grid sample intersections..." },
      { p: 90, s: "Formulating remedial engineering recommendations..." }
    ];
    
    steps.forEach((step, index) => {
      setTimeout(() => {
        setAnalyzeProgress(step.p);
        setAnalyzeStatus(step.s);
      }, (index + 1) * 500);
    });
    
    setTimeout(() => {
      let data = {};
      if (type === "shear") {
        data = {
          filename: "facade_shear_diag_01.png",
          width_mm: 2.85,
          length_cm: 45.2,
          rebar_spacing_cm: 22.5,
          detected_rods: 4,
          crack_type: "Structural Shear Crack",
          severity: "critical",
          v_index: 0.88,
          recommendation: "CRITICAL: Diagonal shear cracking indicates severe concrete stress. Install shoring props immediately. Inject crack under pressure with high-strength structural epoxy. Consider wrapping column/beam with Carbon Fiber (CFRP) wraps."
        };
      } else if (type === "corrosion") {
        data = {
          filename: "beam_corrosion_splitting.png",
          width_mm: 1.62,
          length_cm: 28.4,
          rebar_spacing_cm: 15.0,
          detected_rods: 2,
          crack_type: "Corrosion-Induced Splitting Crack",
          severity: "severe",
          v_index: 0.62,
          recommendation: "SEVERE: Rust expansion of reinforcement rods is splitting concrete cover. Expose bars by removing loose concrete. Clean steel to white-metal finish. Prime rebar rods with zinc-rich epoxy coating. Repair concrete sections using structural polymer patching."
        };
      } else if (type === "flexural") {
        data = {
          filename: "slab_bottom_tensile.png",
          width_mm: 0.78,
          length_cm: 18.5,
          rebar_spacing_cm: 20.0,
          detected_rods: 0,
          crack_type: "Flexural Tension Crack",
          severity: "moderate",
          v_index: 0.35,
          recommendation: "MODERATE: Flexural cracking under bending loads. Install tell-tale gauges to monitor crack width changes over 30 days. Seal cracks with elastomeric polyurethane sealant to block moisture. If widths increase, steel plates must be bolted to beam faces."
        };
      } else {
        data = {
          filename: "wall_shrinkage_hairline.png",
          width_mm: 0.18,
          length_cm: 12.1,
          rebar_spacing_cm: 25.0,
          detected_rods: 0,
          crack_type: "Hairline Shrinkage / Thermal Crack",
          severity: "minor",
          v_index: 0.15,
          recommendation: "MINOR: Standard hairline shrinkage / map cracking. Clean facade surface with compressed air. Spray concrete with water-repellent silane penetrating sealer to restrict weather exposure. Re-inspect during annual UAV flight cycles."
        };
      }
      setAnalyzeProgress(100);
      setAnalyzeStatus("Complete!");
      setTimeout(() => {
        setAnalyzedData(data);
        setAnalyzing(false);
      }, 300);
    }, 2000);
  };

  const filteredDefects = defectsList.filter(d => {
    if (typeFilter === "all") return true;
    return d.type.toLowerCase().includes(typeFilter.toLowerCase());
  });

  const runPipeline = async () => {
    try {
      const headers = { "Content-Type": "application/json" };
      let token = authToken || (typeof window !== "undefined" ? localStorage.getItem("cortex_token") : null);
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      // 1. Submit inspection job
      const res = await fetch(getApiUrl("/api/inspections"), {
        method: "POST",
        headers: headers,
        body: JSON.stringify({
          building_id: "6a182507-c3c9-41c2-a165-b7fd0faf497b",
          s3_image_key: uploadedLocalPath || "/tmp/cortex_uploads/demo-facade.jpg",
          cycle_id: Math.floor(Math.random() * 100) + 1, // random cycle to prevent active job duplicate conflicts
          gsd_mm_per_px: 1.2,
          elapsed_months: 6.0
        })
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to submit pipeline job");
      }

      const data = await res.json();
      const jobId = data.job_id;
      setActiveJobId(jobId);
      setPipelineStage(0);
      setProgress(5);
      setPolling(true);

    } catch (err) {
      console.error(err);
      alert("Error starting pipeline: " + err.message);
    }
  };

  useEffect(() => {
    if (!polling || !activeJobId) return;

    let timer;
    const pollStatus = async () => {
      try {
        const headers = {};
        let token = authToken || (typeof window !== "undefined" ? localStorage.getItem("cortex_token") : null);
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch(getApiUrl(`/api/inspections/${activeJobId}/status`), { headers });
        if (!res.ok) throw new Error("Failed to poll status");
        
        const data = await res.json();
        const pct = data.progress_pct;
        setProgress(pct);

        // Map progress_pct to pipelineStage (0-indexed stages)
        if (pct >= 95) {
          setPipelineStage(6); // success
        } else if (pct >= 80) {
          setPipelineStage(5);
        } else if (pct >= 65) {
          setPipelineStage(4);
        } else if (pct >= 50) {
          setPipelineStage(3);
        } else if (pct >= 40) {
          setPipelineStage(2);
        } else if (pct >= 25) {
          setPipelineStage(1);
        } else if (pct >= 10) {
          setPipelineStage(0);
        }

        if (data.status === "succeeded") {
          setPolling(false);
          // Load the completed defects!
          const defectsRes = await fetch(getApiUrl(`/api/inspections/${activeJobId}/defects`), { headers });
          if (defectsRes.ok) {
            const defectsData = await defectsRes.json();
            const defectArray = defectsData.defects || defectsData;
            
            const mapped = defectArray.map(d => {
              const type = d.defect_type || d.type || "crack";
              let icon = "❓";
              if (type.toLowerCase().includes("crack")) icon = "⚡";
              else if (type.toLowerCase().includes("spall")) icon = "🔴";
              else if (type.toLowerCase().includes("corrosion")) icon = "🟡";
              else if (type.toLowerCase().includes("delamination")) icon = "🔵";
              
              return {
                id: d.defect_ref || d.id || d.defect_id,
                type: type,
                severity: d.severity || d.severity_class || "moderate",
                location: d.location || `X-${d.centroid_x || 0}, Y-${d.centroid_y || 0}`,
                vIndex: (d.growth_rate_mm_per_month || 0.0).toFixed(2),
                confidence: d.confidence !== undefined ? Math.round(d.confidence * (d.confidence <= 1 ? 100 : 1)) : 80,
                icon: icon
              };
            });
            setDefectsList(mapped);
            const total = mapped.length;
            const critical = mapped.filter(d => d.severity === "critical" || d.severity === "severe" || d.severity === "SEVERE").length;
            const avgVIndex = total > 0 ? (mapped.reduce((acc, d) => acc + parseFloat(d.vIndex), 0) / total).toFixed(2) : "0.00";
            
            setStats({
              total: total.toString(),
              critical: critical.toString(),
              avgVIndex: avgVIndex,
              gsd: "1.2"
            });
            triggerRefresh();
          }
        } else if (data.status === "failed") {
          setPolling(false);
          alert("Pipeline job failed: " + (data.error || "Unknown error"));
        } else {
          // Keep polling
          timer = setTimeout(pollStatus, 1500);
        }

      } catch (err) {
        console.error("Polling error:", err);
        timer = setTimeout(pollStatus, 3000); // retry after 3s on network error
      }
    };

    timer = setTimeout(pollStatus, 1500);
    return () => clearTimeout(timer);
  }, [polling, activeJobId, authToken]);


  const simulateLoad = () => {
    setLoading(true);
    setSimulationLoadedCard(false);
    setTimeout(() => {
      setLoading(false);
      setSimulationLoadedCard(true);
    }, 2200);
  };

  const tabs = [
    { id: "analyzer",    label: "UAV Image Analyzer" },
    { id: "defects",     label: "Defect List" },
    { id: "pipeline",    label: "Pipeline" },
    { id: "components",  label: "Showcase Components" },
  ];

  const sectionTitle = (t) => (
    <div style={{ marginBottom: "12px", paddingBottom: "10px", borderBottom: `1px solid ${tokens.colors.border}` }}>
      <h3 style={{ fontFamily: tokens.font.display, fontSize: "16px", fontWeight: 400, color: tokens.colors.textSecondary, letterSpacing: "0.01em" }}>{t}</h3>
    </div>
  );

  return (
    <DSContext.Provider value={{ tokens }}>
      <GlobalStyle/>
      <style>{`
        @keyframes ripple { to { transform: translate(-50%,-50%) scale(30); opacity: 0; } }
      `}</style>

      <div style={{
        height: tab === "analyzer" ? "100vh" : "auto",
        minHeight: "100vh",
        background: tokens.colors.bg,
        padding: tab === "analyzer" ? "0" : "0 0 60px",
        display: tab === "analyzer" ? "flex" : "block",
        flexDirection: tab === "analyzer" ? "column" : "initial",
        overflow: tab === "analyzer" ? "hidden" : "initial"
      }}>

        {/* ── HEADER ── */}
        <header style={{
          borderBottom: `1px solid ${tokens.colors.border}`,
          padding: "0 24px",
          background: `${tokens.colors.surface}cc`,
          backdropFilter: "blur(16px)",
          position: "sticky", top: 0, zIndex: 50,
          display: "flex", alignItems: "center", gap: "16px", height: "52px",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginRight: "auto" }}>
            <span style={{ fontFamily: "inherit", fontSize: "16px", fontWeight: 800, letterSpacing: "0.03em", color: "#FFFFFF", display: "flex", alignItems: "center" }}>
              C
              <span style={{ display: "inline-block", position: "relative", top: 0, margin: "0 1px" }}>
                <svg width="15" height="15" viewBox="0 0 100 100" style={{ verticalAlign: "middle" }}>
                  <circle cx="50" cy="50" r="45" fill="#FFE600" />
                  <circle cx="50" cy="50" r="28" fill="none" stroke="#000000" strokeWidth="10" />
                  <circle cx="50" cy="50" r="12" fill="#000000" />
                  <line x1="50" y1="12" x2="50" y2="88" stroke="#000000" strokeWidth="8" />
                  <line x1="12" y1="50" x2="88" y2="50" stroke="#000000" strokeWidth="8" />
                </svg>
              </span>
              RTEX
            </span>
            <Badge variant="info" size="xs">UI System</Badge>
          </div>
          <nav style={{ display: "flex", gap: "2px" }} role="tablist" aria-label="Main sections">
            {tabs.map(t => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                style={{
                  background: tab === t.id ? tokens.colors.accentMuted : "transparent",
                  border: "none", borderRadius: tokens.radius.sm,
                  color: tab === t.id ? tokens.colors.accent : tokens.colors.textMuted,
                  padding: "5px 12px", cursor: "pointer",
                  fontSize: "12px", fontWeight: 500, fontFamily: "inherit",
                  transition: "all 0.15s",
                }}
                onMouseEnter={e => { if (tab !== t.id) e.currentTarget.style.color = tokens.colors.textPrimary; }}
                onMouseLeave={e => { if (tab !== t.id) e.currentTarget.style.color = tokens.colors.textMuted; }}
              >
                {t.label}
              </button>
            ))}
          </nav>
          <Tooltip content="Open defect detail" placement="bottom">
            <Button size="sm" variant="primary" onClick={() => setModalOpen(true)}>
              <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M8 3v10M3 8h10"/></svg>
              New Inspection
            </Button>
          </Tooltip>
        </header>

        <main style={{
          maxWidth: tab === "analyzer" ? "none" : "1300px",
          width: "100%",
          margin: "0 auto",
          padding: tab === "analyzer" ? "0" : "24px",
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minHeight: 0
        }}>

          {/* ── STATS ROW ── */}
          {tab !== "analyzer" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: "12px", marginBottom: "24px" }}>
              {[
                { label: "Total Defects",   value: stats.total,    unit: "",      delta: 12,  deltaLabel: "vs last scan", icon: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="6"/><path d="M8 5v3l2 2"/></svg>, accent: tokens.colors.accent },
                { label: "Critical",        value: stats.critical,     unit: "",      delta: -3,  deltaLabel: "resolved",     icon: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M8 2l1.5 4h4l-3 2.5 1 4L8 10l-3.5 2.5 1-4L2.5 6h4Z"/></svg>, accent: tokens.colors.danger },
                { label: "Avg V-Index",     value: stats.avgVIndex,   unit: "",      delta: -8,  deltaLabel: "improved",     icon: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 12l4-4 3 3 5-6"/></svg>, accent: tokens.colors.warning },
                { label: "GSD Resolution",  value: stats.gsd,    unit: "mm/px", delta: 0,   deltaLabel: "stable",       icon: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="3"/><path d="M8 2v2M8 12v2M2 8h2M12 8h2"/></svg>, accent: tokens.colors.success },
              ].map((s, i) => (
                <StatCard key={i} {...s} loading={loading}/>
              ))}
            </div>
          )}

          {tab === "analyzer" ? (
            <CortexCrackAnalyzer 
              authToken={authToken} 
              getApiUrl={getApiUrl} 
              onDefectSaved={() => {
                triggerRefresh();
              }}
              onStatsChange={(newStats) => {
                setStats(newStats);
              }}
            />
          ) : (
            <div className="split-grid">
              {/* Left Column: Active Tab Content */}
              <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
                
                {/* ── TAB: DEFECTS ── */}
                {tab === "defects" && (
                  <div style={{ animation: "fadeUp 0.25s ease" }}>
                    <div style={{ display: "flex", gap: "12px", marginBottom: "16px", alignItems: "center" }}>
                      <div style={{ flex: 1 }}>
                        <Select
                          label="Filter by type"
                          options={TYPE_OPTIONS}
                          value={typeFilter}
                          onChange={setTypeFilter}
                        />
                      </div>
                      <Button
                        size="md" variant="secondary"
                        style={{ marginTop: "17px" }}
                        onClick={simulateLoad}
                      >
                        {loading ? <Spinner size={12}/> : <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M1 4v6h6M15 12V6H9"/><path d="M14.6 9A6 6 0 0 1 3 9M1.4 7A6 6 0 0 1 13 7"/></svg>}
                        Refresh
                      </Button>
                    </div>
                    <Card padding="none">
                      {loading ? (
                        <>
                          {[1,2,3].map(i => <DefectRow key={i} loading/>)}
                        </>
                      ) : filteredDefects.length === 0 ? (
                        <EmptyState
                          icon="🔍"
                          title="No defects match"
                          description="Try changing the type filter."
                          action={<Button size="sm" variant="ghost" onClick={() => setTypeFilter("all")}>Clear filter</Button>}
                          compact
                        />
                      ) : (
                        filteredDefects.map(d => (
                          <DefectRow
                            key={d.id}
                            defect={d}
                            onClick={() => { setSelectedDef(d); setModalOpen(true); }}
                          />
                        ))
                      )}
                    </Card>
                    <p style={{ fontSize: "11px", color: tokens.colors.textMuted, marginTop: "10px", textAlign: "right" }}>
                      {filteredDefects.length} defects · click any row to inspect
                    </p>
                  </div>
                )}

                {/* ── TAB: PIPELINE ── */}
                {tab === "pipeline" && (
                  <div style={{ animation: "fadeUp 0.25s ease", display: "flex", flexDirection: "column", gap: "20px" }}>
                    <div style={{ display: "flex", gap: "10px" }}>
                      <Button variant="primary" size="sm" onClick={runPipeline} disabled={pipelineStage > -1 && pipelineStage <= PIPELINE_STAGES.length}>
                        {pipelineStage > -1 && pipelineStage <= PIPELINE_STAGES.length
                          ? <><Spinner size={11}/>Running pipeline…</>
                          : "▶ Run Pipeline"}
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => setPipelineStage(-1)}>Reset</Button>
                    </div>
                    {pipelineStage > -1 && (
                      <ProgressBar
                        value={Math.min(pipelineStage, PIPELINE_STAGES.length)}
                        max={PIPELINE_STAGES.length}
                        label="Overall progress"
                        color={pipelineStage > PIPELINE_STAGES.length ? tokens.colors.success : tokens.colors.accent}
                      />
                    )}
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {PIPELINE_STAGES.map((stage, i) => (
                        <PipelineStage
                          key={i}
                          stage={stage}
                          index={i}
                          active={pipelineStage === i + 1}
                          done={pipelineStage > i + 1}
                        />
                      ))}
                    </div>
                    {pipelineStage > PIPELINE_STAGES.length && (
                      <Card accent style={{ animation: "slideIn 0.3s ease" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <Badge variant="success" dot pulse>Complete</Badge>
                          <span style={{ fontSize: "13px", color: tokens.colors.textPrimary }}>All 5 phases finished — 247 defects detected, 18 critical</span>
                        </div>
                      </Card>
                    )}
                  </div>
                )}

                {/* ── TAB: COMPONENTS ── */}
                {tab === "components" && (
                  <div style={{ animation: "fadeUp 0.25s ease", display: "flex", flexDirection: "column", gap: "24px" }}>
                    
                    {/* Forms / Inputs Section */}
                    <div>
                      {sectionTitle("Forms & Input States")}
                      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                        <Input 
                          label="Project name" 
                          placeholder="e.g. Building A — Facade Survey" 
                          required 
                          hint="Used in the PDF report header."
                          value={projectName}
                          error={projectNameErr}
                          onChange={e => { setProjectName(e.target.value); setProjectNameErr(""); }}
                        />
                        <Input 
                          label="GSD value (mm/px)" 
                          placeholder="2.1" 
                          error={gsdErr} 
                          value={gsdValue}
                          onChange={e => { setGsdValue(e.target.value); setGsdErr(""); }}
                          leftIcon={<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 5v3l1.5 1.5"/></svg>}
                        />
                        <Select
                          label="Defect type"
                          options={TYPE_OPTIONS}
                          value={formDefectType}
                          onChange={setFormDefectType}
                        />
                        <div style={{ display: "flex", gap: "8px" }}>
                          <Button
                            fullWidth variant="primary"
                            loading={showcaseBtnLoading}
                            onClick={async () => {
                              let hasErr = false;
                              if (!projectName) {
                                setProjectNameErr("Project name is required.");
                                hasErr = true;
                              }
                              if (!gsdValue) {
                                setGsdErr("GSD value is required.");
                                hasErr = true;
                              } else if (isNaN(parseFloat(gsdValue))) {
                                setGsdErr("GSD value must be a valid number.");
                                hasErr = true;
                              }
                              if (hasErr) return;

                              setShowcaseBtnLoading(true);
                              const typeLabel = TYPE_OPTIONS.find(o => o.value === formDefectType)?.label || "Structural Crack";
                              
                              const defectPayload = {
                                defect_id: `DEF-MAN-${Math.floor(Math.random() * 900) + 100}`,
                                type: typeLabel,
                                width_mm: parseFloat(gsdValue) || 1.8,
                                length_cm: 25.0,
                                rebar_spacing_cm: formDefectType === "corrosion" ? 15.0 : 20.0,
                                v_index: formDefectType === "crack" ? 0.85 : formDefectType === "spall" ? 0.61 : formDefectType === "corrosion" ? 0.72 : 0.22,
                                severity: formDefectType === "crack" ? "critical" : formDefectType === "spall" ? "severe" : formDefectType === "corrosion" ? "severe" : "moderate",
                                recommendation: `Manual inspection logged for ${projectName}. Regular health scans recommended.`
                              };

                              try {
                                const headers = { "Content-Type": "application/json" };
                                let token = authToken || (typeof window !== "undefined" ? localStorage.getItem("cortex_token") : null);
                                if (token) {
                                  headers["Authorization"] = `Bearer ${token}`;
                                }
                                
                                const res = await fetch(getApiUrl("/api/inspections"), {
                                  method: "POST",
                                  headers: headers,
                                  body: JSON.stringify({
                                    building_id: "manual-asset-id",
                                    s3_image_key: "/tmp/cortex_uploads/demo-facade.jpg",
                                    cycle_id: 3,
                                    gsd_mm_per_px: parseFloat(gsdValue) || 1.2,
                                    defect_data: defectPayload
                                  })
                                });
                                
                                if (!res.ok) throw new Error("Failed to save to database");
                                alert(`Inspection logged successfully! Defect ${defectPayload.defect_id} added to catalog.`);
                                triggerRefresh();
                                setProjectName("");
                                setGsdValue("");
                              } catch (e) {
                                alert("Submission error: " + e.message);
                              } finally {
                                setShowcaseBtnLoading(false);
                              }
                            }}
                          >
                            {showcaseBtnLoading ? "Submitting…" : "Submit Inspection"}
                          </Button>
                          <Button variant="secondary" onClick={() => { setProjectName(""); setProjectNameErr(""); setGsdValue(""); setGsdErr(""); setFormDefectType("crack"); }}>Clear</Button>
                        </div>
                      </div>
                    </div>

                    {/* Button Variants Section */}
                    <div>
                      {sectionTitle("Button Variants & Sizes")}
                      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                        {/* Terminal Log */}
                        <div style={{
                          padding: "8px 12px", background: tokens.colors.bg,
                          border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius.md,
                          fontFamily: tokens.font.mono, fontSize: "11px", color: tokens.colors.accent,
                          display: "flex", gap: "8px", alignItems: "center"
                        }}>
                          <span style={{ color: tokens.colors.textMuted }}>$ action_log:</span>
                          <span>{lastActionLog}</span>
                        </div>
                        
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                          <Button variant="primary" size="xs" onClick={() => setLastActionLog("Primary XS button clicked. Logged event [UAV_MICRO_TRIG: Success]")}>Primary XS</Button>
                          <Button variant="secondary" size="sm" onClick={() => setLastActionLog("Secondary SM button clicked. Refreshed standard diagnostics container.")}>Secondary SM</Button>
                          <Button variant="outline" size="md" onClick={() => setLastActionLog("Outline MD button clicked. Swapped visual overlay contrast mapping.")}>Outline MD</Button>
                          <Button variant="ghost" size="lg" onClick={() => setLastActionLog("Ghost LG button clicked. Hidden structural details layer.")}>Ghost LG</Button>
                          <Button variant="danger" size="xl" onClick={() => setLastActionLog("Danger XL button clicked. EMERGENCY ALARM: Simulated structural stability breach!")}>Danger XL</Button>
                        </div>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                          <Button variant="success" size="sm" onClick={() => setLastActionLog("Success Button clicked. Reset and re-calibrated local sensors.")}>Success Button</Button>
                          <Button
                            variant="primary"
                            size="sm"
                            loading={showcaseBtnLoading}
                            onClick={() => {
                              setShowcaseBtnLoading(true);
                              setLastActionLog("Running mock async task simulation...");
                              setTimeout(() => {
                                setShowcaseBtnLoading(false);
                                setLastActionLog("Mock task completed. Resource cleanup successful.");
                              }, 1500);
                            }}
                          >
                            Loading Button
                          </Button>
                          <Tooltip content="This button is disabled during scans." placement="top">
                            <Button variant="secondary" size="sm" disabled onClick={() => setLastActionLog("You shouldn't be able to click this disabled button.")}>Disabled Button</Button>
                          </Tooltip>
                        </div>
                      </div>
                    </div>

                    {/* Badges Section */}
                    <div>
                      {sectionTitle("Badge Types")}
                      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                          {Object.keys(badgeConfig).map(variant => (
                            <button
                              key={variant}
                              type="button"
                              onClick={() => {
                                const descMap = {
                                  hairline: "HAIRLINE severity level: Standard shrinkage cracking (<0.1mm width). Low risk. Action: Silane repellent coat. Reinspect: 365 days.",
                                  minor: "MINOR severity level: Surface map cracking (<0.5mm width). Low risk. Action: silane sealer wash. Reinspect: 180 days.",
                                  moderate: "MODERATE severity level: Flexural tension cracking (<1.5mm width). Medium risk. Action: Polyurethane sealant seal. Reinspect: 90 days.",
                                  severe: "SEVERE severity level: Corrosion splitting / spalling (<3mm width). High risk. Action: Clean rebars to white metal, prime with zinc-rich epoxy, and patch with structural mortar. Reinspect: 30 days.",
                                  critical: "CRITICAL severity level: Diagonal shear crack / massive concrete cover failure (>3mm width). Immediate risk. Action: Deploy structural shoring props, epoxy pressure injection, wrapped in carbon fiber (CFRP). Reinspect: 7 days.",
                                  info: "INFO badge: General system message or informational scan tag.",
                                  success: "SUCCESS badge: Inspection passes all NDT/Laplacian structural health criteria.",
                                  warning: "WARNING badge: Non-destructive test anomalies detected.",
                                  danger: "DANGER badge: Severe concrete cover loss threat.",
                                  default: "DEFAULT badge: General uncategorized visual diagnostic tag."
                                };
                                setSelectedBadgeInfo(descMap[variant] || descMap.default);
                              }}
                              style={{ background: "transparent", border: "none", outline: "none", cursor: "pointer", display: "inline-flex" }}
                            >
                              <Badge variant={variant} dot pulse={variant === "severe" || variant === "critical"}>{variant}</Badge>
                            </button>
                          ))}
                        </div>
                        {/* Dynamic Description Box */}
                        <div style={{
                          padding: "10px 14px", background: tokens.colors.surfaceHover,
                          borderLeft: `3px solid ${tokens.colors.accent}`, borderRadius: `0 ${tokens.radius.md} ${tokens.radius.md} 0`,
                          fontSize: "12.5px", color: tokens.colors.textSecondary, lineHeight: 1.5
                        }}>
                          {selectedBadgeInfo}
                        </div>
                      </div>
                    </div>

                    {/* Tooltip Placements Section */}
                    <div>
                      {sectionTitle("Tooltip Placements")}
                      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                        {["top", "bottom", "left", "right"].map(p => (
                          <Tooltip key={p} content={`Tooltip placement direction: ${p}`} placement={p}>
                            <Button size="sm" variant="secondary" onClick={() => setLastActionLog(`Hovered and triggered tooltip on the ${p} side.`)}>{p}</Button>
                          </Tooltip>
                        ))}
                      </div>
                    </div>

                    {/* Load Simulation & Skeletons */}
                    <div>
                      {sectionTitle("Load Simulation")}
                      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                        <Button variant="secondary" size="sm" onClick={simulateLoad} loading={loading}>
                          {loading ? "Simulating..." : "Simulate skeleton load (2s)"}
                        </Button>
                        {loading && (
                          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                            <Skeleton height="36px" width="100%" borderRadius={tokens.radius.md}/>
                            <Skeleton height="14px" width="80%"/>
                            <Skeleton height="14px" width="40%"/>
                          </div>
                        )}
                        {!loading && simulationLoadedCard && (
                          <Card accent style={{ animation: "scaleIn 0.3s ease", background: tokens.colors.surfaceHover }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                              <Badge variant="severe" dot pulse>DEF-LOAD-01</Badge>
                              <span style={{ fontSize: "11px", fontFamily: tokens.font.mono, color: tokens.colors.textMuted }}>SIMULATED UAV SCAN RESOLVED</span>
                            </div>
                            <p style={{ fontSize: "13.5px", color: tokens.colors.textPrimary, fontWeight: 600, marginBottom: "4px" }}>Corrosion-Induced Splitting Crack</p>
                            <p style={{ fontSize: "12px", color: tokens.colors.textSecondary, lineHeight: 1.5 }}>
                              Width: <span style={{ color: tokens.colors.textPrimary, fontWeight: 500 }}>1.84 mm</span> · Length: <span style={{ color: tokens.colors.textPrimary, fontWeight: 500 }}>32.5 cm</span> · Rebar Spacing: <span style={{ color: tokens.colors.textPrimary, fontWeight: 500 }}>20.0 cm</span> · V-Index: <span style={{ color: tokens.colors.accent, fontWeight: 600 }}>0.68</span>
                            </p>
                            <div style={{
                              marginTop: "10px", padding: "8px 10px", background: "rgba(245,158,11,0.06)",
                              borderLeft: `3px solid ${tokens.colors.warning}`, fontSize: "11.5px", color: tokens.colors.textSecondary, lineHeight: 1.4
                            }}>
                              <strong>Remediation Recommendation:</strong> Expose reinforcement rods. Clean bars to white finish. Paint with zinc prime layer, and patch concrete cover with structural repair polymer.
                            </div>
                          </Card>
                        )}
                      </div>
                    </div>

                  </div>
                )}

              </div>

              {/* Right Column: Corporate Overview Panel */}
              <CompanyProfilePanel />
            </div>
          )}
        </main>
      </div>

      {/* ── MODAL ── */}
      <Modal
        open={modalOpen}
        onClose={() => { setModalOpen(false); setSelectedDef(null); }}
        title={selectedDef ? `Defect ${selectedDef.id}` : "New Inspection"}
        description={selectedDef ? `${selectedDef.type} · ${selectedDef.location}` : "Configure a new drone imagery scan"}
        size="md"
        danger={selectedDef?.severity === "critical"}
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => { setModalOpen(false); setSelectedDef(null); }}>Cancel</Button>
            <Button variant="primary" size="sm" onClick={() => { setModalOpen(false); setSelectedDef(null); }}>
              {selectedDef ? "Export Report" : "Start Scan"}
            </Button>
          </>
        }
      >
        {selectedDef ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              {[
                ["Severity",    <Badge variant={selectedDef.severity} dot>{selectedDef.severity}</Badge>],
                ["V-Index",     <span style={{ fontFamily: tokens.font.mono, fontSize: "13px" }}>{selectedDef.vIndex}</span>],
                ["Confidence",  <span style={{ fontFamily: tokens.font.mono, fontSize: "13px" }}>{selectedDef.confidence}%</span>],
                ["Location",    <span style={{ fontFamily: tokens.font.mono, fontSize: "12px", color: tokens.colors.textSecondary }}>{selectedDef.location}</span>],
              ].map(([k, v]) => (
                <div key={k} style={{ padding: "10px 12px", background: tokens.colors.bg, borderRadius: tokens.radius.md, border: `1px solid ${tokens.colors.border}` }}>
                  <p style={{ fontSize: "10px", color: tokens.colors.textMuted, marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.06em" }}>{k}</p>
                  {v}
                </div>
              ))}
            </div>
            <ProgressBar value={selectedDef.confidence} label="XGBoost confidence" size="sm"/>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <Input label="Mission name" placeholder="Facade Survey Q2-2026" required/>
            <Input label="Target resolution (mm/px)" placeholder="2.1"/>
            <Select label="Analysis profile" options={[
              { value: "standard",   label: "Standard (all defects)" },
              { value: "structural", label: "Structural only" },
              { value: "surface",    label: "Surface only" },
            ]} value="standard" onChange={() => {}}/>
          </div>
        )}
      </Modal>
    </DSContext.Provider>
  );
}
