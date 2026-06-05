/**
 * AuthLayout — shared wrapper for all THESYS+ public auth pages.
 *
 * Owns:
 *   - page background (grid overlay + optional dark radial glow)
 *   - sticky header (THESYS+ logo → "/" and theme toggle)
 *
 * Renders <Outlet /> so nested route children provide their own body content.
 * Because the header lives here, it never remounts during client-side
 * navigation between auth pages — which prevents the blank-screen flash
 * caused by header state being torn down and rebuilt on every transition.
 *
 * Every auth-page Route must be nested under this layout in App.jsx.
 * Internal navigation between auth pages must use React Router <Link> (not
 * <a href>) so the router drives all history operations.
 *
 * Phase 1.1 Step 1: isDark ternaries replaced with semantic token utilities.
 * Theme-switching behaviour and all layout/spacing/interaction unchanged.
 */

import { Link, Outlet } from 'react-router-dom';
import { useTheme } from '../../context/ThemeContext';
import { Sun, Moon } from 'lucide-react';

export default function AuthLayout() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div className="min-h-screen bg-canvas flex flex-col transition-colors duration-300">

      {/* ── Background layer (fixed, non-interactive) ──────────────── */}
      <div
        className="pointer-events-none fixed inset-0 z-0"
        aria-hidden="true"
        style={{
          backgroundImage: isDark
            ? 'linear-gradient(rgba(59,130,246,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.045) 1px, transparent 1px)'
            : 'linear-gradient(rgba(99,102,241,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.04) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />
      {isDark && (
        <div
          className="pointer-events-none fixed inset-0 z-0"
          aria-hidden="true"
          style={{
            background:
              'radial-gradient(ellipse 70% 45% at 50% -4%, rgba(37,99,235,0.15) 0%, transparent 68%)',
          }}
        />
      )}

      {/* ── Header — persists across all auth page navigations ─────── */}
      <header className="relative z-10 flex items-center justify-between px-5 sm:px-10 py-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-canvas)]/70 backdrop-blur-md flex-shrink-0">
        {/* Logo — internal navigation, no full page reload */}
        <Link
          to="/"
          className="flex items-center gap-2.5 select-none"
          aria-label="THESYS+ home"
        >
          <div className="w-7 h-7 rounded-lg flex items-center justify-center text-sm bg-[var(--color-logo-bg)] ring-1 ring-[var(--color-logo-ring)]">
            🎓
          </div>
          <span className="text-sm font-bold tracking-wide text-ink">
            THESYS+
          </span>
        </Link>

        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          className="w-9 h-9 flex items-center justify-center rounded-lg text-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 text-muted hover:text-ink hover:bg-[var(--color-icon-btn-hover-bg)]"
        >
          {isDark ? <Sun className="h-5 w-5 text-primary" /> : <Moon className="h-5 w-5 text-primary" />}
        </button>
      </header>

      {/* ── Page content — provided by each nested route ────────────── */}
      <Outlet />
    </div>
  );
}
