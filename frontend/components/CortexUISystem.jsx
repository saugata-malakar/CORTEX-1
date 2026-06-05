import { useState, useEffect, useRef, createContext, useContext, forwardRef } from "react";

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

export default function CortexUISystem() {
  const [tab, setTab]             = useState("components");
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedDef, setSelectedDef] = useState(null);
  const [typeFilter, setTypeFilter]   = useState("all");
  const [loading, setLoading]         = useState(false);
  const [pipelineStage, setPipelineStage] = useState(-1);
  const [progress, setProgress]       = useState(72);
  const [inputVal, setInputVal]       = useState("");
  const [inputErr, setInputErr]       = useState("");
  const [btnLoading, setBtnLoading]   = useState(false);

  const runPipeline = () => {
    setPipelineStage(0);
    const advance = (i) => {
      if (i >= PIPELINE_STAGES.length) { setPipelineStage(PIPELINE_STAGES.length); return; }
      setTimeout(() => { setPipelineStage(i + 1); advance(i + 1); }, 900);
    };
    advance(0);
  };

  const simulateLoad = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 2200);
  };

  const tabs = [
    { id: "components",  label: "Components" },
    { id: "defects",     label: "Defect List" },
    { id: "pipeline",    label: "Pipeline" },
    { id: "forms",       label: "Forms" },
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

      <div style={{ minHeight: "100vh", background: tokens.colors.bg, padding: "0 0 60px" }}>

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
            <div style={{
              width: 24, height: 24, borderRadius: tokens.radius.sm,
              background: `linear-gradient(135deg, ${tokens.colors.accent}, #8B5CF6)`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg>
            </div>
            <span style={{ fontFamily: tokens.font.display, fontSize: "15px", letterSpacing: "0.02em", color: tokens.colors.textPrimary }}>Cortex</span>
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

        <main style={{ maxWidth: "900px", margin: "0 auto", padding: "32px 24px" }}>

          {/* ── STATS ROW ── */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: "12px", marginBottom: "32px" }}>
            {[
              { label: "Total Defects",   value: "247",    unit: "",      delta: 12,  deltaLabel: "vs last scan", icon: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="6"/><path d="M8 5v3l2 2"/></svg>, accent: tokens.colors.accent },
              { label: "Critical",        value: "18",     unit: "",      delta: -3,  deltaLabel: "resolved",     icon: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M8 2l1.5 4h4l-3 2.5 1 4L8 10l-3.5 2.5 1-4L2.5 6h4Z"/></svg>, accent: tokens.colors.danger },
              { label: "Avg V-Index",     value: "0.43",   unit: "",      delta: -8,  deltaLabel: "improved",     icon: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 12l4-4 3 3 5-6"/></svg>, accent: tokens.colors.warning },
              { label: "GSD Resolution",  value: "2.1",    unit: "mm/px", delta: 0,   deltaLabel: "stable",       icon: <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="3"/><path d="M8 2v2M8 12v2M2 8h2M12 8h2"/></svg>, accent: tokens.colors.success },
            ].map((s, i) => (
              <StatCard key={i} {...s} loading={loading}/>
            ))}
          </div>

          {/* ── TAB: COMPONENTS ── */}
          {tab === "components" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "32px", animation: "fadeUp 0.25s ease" }}>

              {sectionTitle("Button variants")}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
                <Button variant="primary">Primary</Button>
                <Button variant="secondary">Secondary</Button>
                <Button variant="outline">Outline</Button>
                <Button variant="ghost">Ghost</Button>
                <Button variant="danger">Danger</Button>
                <Button variant="success">Success</Button>
                <Button variant="primary" loading>Processing</Button>
                <Button variant="primary" disabled>Disabled</Button>
              </div>

              {sectionTitle("Button sizes")}
              <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                {["xs","sm","md","lg","xl"].map(s => (
                  <Button key={s} size={s} variant="primary">{s.toUpperCase()}</Button>
                ))}
              </div>

              {sectionTitle("Badge variants")}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
                {["hairline","minor","moderate","severe","critical","info","success","warning","danger","default"].map(v => (
                  <Badge key={v} variant={v} dot>{v}</Badge>
                ))}
              </div>

              {sectionTitle("Progress bars")}
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <ProgressBar value={progress} label="Analysis progress" stages={["Ingest","Stitch","Detect","Report"]}/>
                <ProgressBar value={18} max={247} label="Critical defects" color={tokens.colors.danger}/>
                <ProgressBar value={94} label="XGBoost confidence" color={tokens.colors.success} size="sm"/>
                <div style={{ display: "flex", gap: "10px", marginTop: "4px" }}>
                  <Button size="sm" variant="secondary" onClick={() => setProgress(p => Math.max(0, p - 10))}>−10%</Button>
                  <Button size="sm" variant="secondary" onClick={() => setProgress(p => Math.min(100, p + 10))}>+10%</Button>
                </div>
              </div>

              {sectionTitle("Cards")}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(240px,1fr))", gap: "12px" }}>
                <Card accent padding="lg"><p style={{ fontSize: "13px", color: tokens.colors.textSecondary }}>Default card with accent top border.</p></Card>
                <Card interactive padding="lg" onClick={() => alert("Card clicked!")}><p style={{ fontSize: "13px", color: tokens.colors.textSecondary }}>Interactive card — hover and click me.</p></Card>
                <Card loading padding="lg"><p style={{ fontSize: "13px", color: tokens.colors.textSecondary }}>Loading state — shimmer overlay.</p></Card>
              </div>

              {sectionTitle("Empty states")}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <Card padding="none">
                  <EmptyState
                    icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/></svg>}
                    title="No defects found"
                    description="Try adjusting your filters or run a new pipeline scan."
                    action={<Button size="sm" variant="primary">Run Scan</Button>}
                    compact
                  />
                </Card>
                <Card padding="none">
                  <EmptyState
                    icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 17H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5"/><path d="M17 17l2 2 4-4"/></svg>}
                    title="Report pending"
                    description="Waiting for pipeline phase 4 to complete."
                    compact
                  />
                </Card>
              </div>

              {sectionTitle("Skeleton loaders")}
              <Card padding="lg">
                <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  <Skeleton width="44px" height="44px" borderRadius={tokens.radius.md}/>
                  <div style={{ flex: 1 }}>
                    <Skeleton width="160px" height="14px" style={{ marginBottom: "6px" }}/>
                    <Skeleton count={2} width={(i) => i === 0 ? "100%" : "70%"} height="11px"/>
                  </div>
                </div>
              </Card>

              {sectionTitle("Tooltips")}
              <div style={{ display: "flex", gap: "16px" }}>
                {["top","bottom","left","right"].map(p => (
                  <Tooltip key={p} content={`Placement: ${p}`} placement={p}>
                    <Button size="sm" variant="secondary">{p}</Button>
                  </Tooltip>
                ))}
              </div>

              {sectionTitle("Load simulation")}
              <Button variant="secondary" size="sm" onClick={simulateLoad} loading={loading}>
                {loading ? "Simulating..." : "Simulate skeleton load (2s)"}
              </Button>
            </div>
          )}

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
                ) : MOCK_DEFECTS.length === 0 ? (
                  <EmptyState
                    icon="🔍"
                    title="No defects match"
                    description="Try changing the type filter."
                    action={<Button size="sm" variant="ghost" onClick={() => setTypeFilter("all")}>Clear filter</Button>}
                    compact
                  />
                ) : (
                  MOCK_DEFECTS.map(d => (
                    <DefectRow
                      key={d.id}
                      defect={d}
                      onClick={() => { setSelectedDef(d); setModalOpen(true); }}
                    />
                  ))
                )}
              </Card>
              <p style={{ fontSize: "11px", color: tokens.colors.textMuted, marginTop: "10px", textAlign: "right" }}>
                {MOCK_DEFECTS.length} defects · click any row to inspect
              </p>
            </div>
          )}

          {/* ── TAB: PIPELINE ── */}
          {tab === "pipeline" && (
            <div style={{ animation: "fadeUp 0.25s ease", display: "flex", flexDirection: "column", gap: "20px" }}>
              <div style={{ display: "flex", gap: "10px" }}>
                <Button variant="primary" size="sm" onClick={runPipeline} disabled={pipelineStage > -1 && pipelineStage < PIPELINE_STAGES.length}>
                  {pipelineStage > -1 && pipelineStage < PIPELINE_STAGES.length
                    ? <><Spinner size={11}/>Running pipeline…</>
                    : "▶ Run Pipeline"}
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setPipelineStage(-1)}>Reset</Button>
              </div>
              {pipelineStage > -1 && (
                <ProgressBar
                  value={pipelineStage}
                  max={PIPELINE_STAGES.length}
                  label="Overall progress"
                  color={pipelineStage === PIPELINE_STAGES.length ? tokens.colors.success : tokens.colors.accent}
                />
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {PIPELINE_STAGES.map((stage, i) => (
                  <PipelineStage
                    key={i}
                    stage={stage}
                    index={i}
                    active={pipelineStage === i + 1}
                    done={pipelineStage > i + 1 || pipelineStage === PIPELINE_STAGES.length}
                  />
                ))}
              </div>
              {pipelineStage === PIPELINE_STAGES.length && (
                <Card accent style={{ animation: "slideIn 0.3s ease" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <Badge variant="success" dot pulse>Complete</Badge>
                    <span style={{ fontSize: "13px", color: tokens.colors.textPrimary }}>All 5 phases finished — 247 defects detected, 18 critical</span>
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* ── TAB: FORMS ── */}
          {tab === "forms" && (
            <div style={{ animation: "fadeUp 0.25s ease", maxWidth: "440px", display: "flex", flexDirection: "column", gap: "20px" }}>
              {sectionTitle("Input states")}
              <Input label="Project name" placeholder="e.g. Building A — Facade Survey" required hint="Used in the PDF report header."/>
              <Input label="GSD value (mm/px)" placeholder="2.1" error={inputErr} value={inputVal}
                onChange={e => { setInputVal(e.target.value); setInputErr(""); }}
                leftIcon={<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 5v3l1.5 1.5"/></svg>}
              />
              <Select
                label="Defect type"
                options={TYPE_OPTIONS}
                value={typeFilter}
                onChange={setTypeFilter}
              />
              <div style={{ display: "flex", gap: "8px" }}>
                <Button
                  fullWidth variant="primary"
                  loading={btnLoading}
                  onClick={() => {
                    if (!inputVal) { setInputErr("GSD value is required."); return; }
                    setBtnLoading(true);
                    setTimeout(() => setBtnLoading(false), 1800);
                  }}
                >
                  {btnLoading ? "Submitting…" : "Submit Inspection"}
                </Button>
                <Button variant="secondary" onClick={() => { setInputVal(""); setInputErr(""); }}>Clear</Button>
              </div>
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
