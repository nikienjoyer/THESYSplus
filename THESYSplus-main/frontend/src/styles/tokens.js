/**
 * THESYS+ Design Tokens — Phase 1.1 Step 0
 *
 * JS export consumed by tailwind.config.js to expose semantic token
 * utilities (bg-canvas, text-ink, text-muted, etc.) via CSS custom
 * properties. Also exports the chart palette so AnalyticsDashboardPage
 * and TrendAnalysisPage can reference a single source of truth instead
 * of hardcoding hex arrays inline.
 *
 * HOW THE SEMANTIC LAYER WORKS:
 * Each entry maps a Tailwind utility name to a CSS custom property defined
 * in tokens.css. Because :root and .dark both define the variable (with
 * different values), the Tailwind utility automatically resolves to the
 * correct value in each theme — no isDark ternary needed in JSX.
 *
 * PHASE 2: to change the brand color, edit --th-prim-600 / --th-prim-400
 * in tokens.css. Tailwind picks up the change everywhere bg-primary /
 * text-primary is used.
 */

// ── Semantic color utilities (exposed as Tailwind color tokens) ───────────
// eslint-disable-next-line import/no-anonymous-default-export
export default {
  // Legacy compat — three original tokens re-pointed at semantic layer
  background: 'var(--color-background)',
  primary:    'var(--color-primary)',
  accent:     'var(--color-accent)',

  // ── New semantic tokens ─────────────────────────────────────────────
  canvas:            'var(--color-canvas)',
  surface:           'var(--color-surface)',
  'surface-secondary': 'var(--color-surface-secondary)',
  'surface-elevated':  'var(--color-surface-elevated)',

  ink:       'var(--color-text)',
  body:      'var(--color-text-body)',
  muted:     'var(--color-text-muted)',
  subtle:    'var(--color-text-subtle)',

  'border-default': 'var(--color-border)',
  'border-strong':  'var(--color-border-strong)',
  'border-subtle':  'var(--color-border-subtle)',

  success: 'var(--color-success)',
  warning: 'var(--color-warning)',
  danger:  'var(--color-danger)',
  info:    'var(--color-info)',

  // ── Status/semantic bg + text for chips/badges ───────────────────────
  'success-bg':     'var(--color-success-bg)',
  'success-border': 'var(--color-success-border)',
  'success-text':   'var(--color-success-text)',
  'warning-bg':     'var(--color-warning-bg)',
  'warning-border': 'var(--color-warning-border)',
  'warning-text':   'var(--color-warning-text)',
  'danger-bg':      'var(--color-danger-bg)',
  'danger-border':  'var(--color-danger-border)',
  'danger-text':    'var(--color-danger-text)',
  'info-bg':        'var(--color-info-bg)',
  'info-border':    'var(--color-info-border)',
  'info-text':      'var(--color-info-text)',

  // ── Navigation / UI chrome ────────────────────────────────────────────
  'logo-bg':          'var(--color-logo-bg)',
  'nav-active-bg':    'var(--color-nav-active-bg)',
  'nav-active-text':  'var(--color-nav-active-text)',
  'nav-hover-bg':     'var(--color-nav-hover-bg)',
  'icon-btn-hover':   'var(--color-icon-btn-hover-bg)',
};


// ── Chart palette — single source of truth for inline SVG charts ─────────
// Used by AnalyticsDashboardPage and TrendAnalysisPage.
// Phase 2.B: slot 1 re-anchored to the institutional ink-blue (#1e40af).
// Values match --th-chart-1…8 primitives in tokens.css.
export const CHART_PALETTE = [
  '#1e40af', // institutional ink-blue  ← Phase 2.B (was #3b82f6)
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#f59e0b', // amber
  '#10b981', // emerald
  '#06b6d4', // cyan
  '#ef4444', // red
  '#84cc16', // lime
];


// ── Semantic JS color accessors ───────────────────────────────────────────
// For use in inline styles / prop values where a CSS class is not enough.
// Phase 2.B: primaryLight updated to institutional ink-blue (#1e40af).
export const TOKEN_COLORS = {
  // Success (emerald)
  successLight: '#059669',
  successDark:  '#34d399',
  // Warning (amber)
  warningLight: '#d97706',
  warningDark:  '#fbbf24',
  // Danger (rose)
  dangerLight:  '#e11d48',
  dangerDark:   '#f87171',
  // Primary (institutional ink-blue) — Phase 2.B
  primaryLight: '#1e40af',  // was #2563eb
  primaryDark:  '#60a5fa',  // unchanged — 7.55:1 on #080d24
};
