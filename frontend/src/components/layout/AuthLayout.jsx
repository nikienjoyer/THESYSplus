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
 */

import { Link, Outlet } from 'react-router-dom';
import { useTheme } from '../../context/ThemeContext';
import { Sun, Moon } from 'lucide-react';

export default function AuthLayout() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div
      className={`min-h-screen flex flex-col transition-colors duration-300 ${
        isDark ? 'bg-[#080d24]' : 'bg-slate-50'
      }`}
    >
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
      <header
        className={`relative z-10 flex items-center justify-between px-5 sm:px-10 py-4 border-b flex-shrink-0 ${
          isDark
            ? 'border-white/[0.06] bg-[#080d24]/70 backdrop-blur-md'
            : 'border-gray-200/80 bg-white/70 backdrop-blur-md'
        }`}
      >
        {/* Logo — internal navigation, no full page reload */}
        <Link
          to="/"
          className="flex items-center gap-2.5 select-none"
          aria-label="THESYS+ home"
        >
          <div
            className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm ${
              isDark
                ? 'bg-blue-600/20 ring-1 ring-blue-500/30'
                : 'bg-blue-100 ring-1 ring-blue-200'
            }`}
          >
            🎓
          </div>
          <span
            className={`text-sm font-bold tracking-wide ${
              isDark ? 'text-white' : 'text-gray-900'
            }`}
          >
            THESYS+
          </span>
        </Link>

        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          className={`w-9 h-9 flex items-center justify-center rounded-lg text-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
            isDark
              ? 'text-gray-400 hover:text-white hover:bg-white/10'
              : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
          }`}
        >
          {isDark ? <Sun className="h-5 w-5 text-primary" /> : <Moon className="h-5 w-5 text-primary" />}
        </button>
      </header>

      {/* ── Page content — provided by each nested route ────────────── */}
      {/*
        `flex-1` makes this area expand so child pages can use their own
        flex alignment (items-center or items-start). Each page renders
        a <div className="relative z-10 flex flex-1 ..."> body wrapper.
      */}
      <Outlet />
    </div>
  );
}
