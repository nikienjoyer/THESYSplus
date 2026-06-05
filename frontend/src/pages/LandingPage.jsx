/**
 * LandingPage — THESYS+ public landing page.
 *
 * Stats row now shows accurate system data:
 *   - Indexed Theses: fetched from /api/v1/theses/ when authenticated,
 *     falls back to repository count label when not.
 *   - AI Components: static (SBERT, Cosine Similarity, TF-IDF, K-Means, OCR = 5)
 *   - Core Features: static (Repository, Semantic Search, Title Similarity,
 *     Trend Analysis, Upload Thesis, Profile = 6)
 */

import { Link, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../hooks/useAuth';
import client from '../api/client';
import { AvatarDropdown } from '../components/layout/AppNavbar';
import LegalModal from '../components/legal/LegalModal';

// Core module nav links.
// implemented: true  → active, routable
// implemented: false → visible but styled as "coming soon" (routes safely to /repository)
const CORE_NAV = [
  { label: 'Home',             to: '/',                 implemented: true  },
  { label: 'Repository',       to: '/repository',       implemented: true  },
  { label: 'Title Similarity', to: '/title-similarity', implemented: true  },
  { label: 'Trend Analysis',   to: '/trend-analysis',   implemented: true  },
  { label: 'Analytics',        to: '/analytics',        implemented: true  },  // Phase 3B
];

// Static stats — accurate counts for the implemented system
const STATIC_STATS = [
  { value: null,  key: 'theses',     label: 'Indexed Theses'  },  // filled dynamically
  { value: '5',   key: 'ai',         label: 'AI Components'   },  // SBERT · Cosine · TF-IDF · K-Means · OCR
  { value: '6',   key: 'features',   label: 'Core Features'   },  // Repository · Semantic Search · Title Similarity
                                                                   // · Trend Analysis · Upload · Profile
];

export default function LandingPage() {
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated, isInitializing, user, signOut } = useAuth();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [thesisCount, setThesisCount] = useState(null);
  const [legalModal, setLegalModal] = useState(null); // 'privacy' | 'terms' | 'help' | null
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isDark = theme === 'dark';

  // Close mobile menu on Escape key
  useEffect(() => {
    function handleEscape(e) {
      if (e.key === 'Escape' && mobileMenuOpen) setMobileMenuOpen(false);
    }
    if (mobileMenuOpen) document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [mobileMenuOpen]);

  // Fetch the public thesis count on every mount.
  // Uses the unauthenticated /theses/public-stats/ endpoint — returns only
  // { indexed_theses_count: number }, no thesis content or private data.
  useEffect(() => {
    let cancelled = false;
    client.get('/theses/public-stats/')
      .then((res) => {
        if (!cancelled && typeof res.data.indexed_theses_count === 'number') {
          setThesisCount(res.data.indexed_theses_count);
        }
      })
      .catch(() => { /* silently ignore — stat is best-effort */ });
    return () => { cancelled = true; };
  }, []); // runs once on mount, no auth dependency

  // Build the stats array with the live thesis count filled in
  const stats = STATIC_STATS.map((s) => {
    if (s.key === 'theses') {
      return {
        ...s,
        value: thesisCount !== null ? String(thesisCount) : '…',
      };
    }
    return s;
  });

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    const q = searchQuery.trim();
    navigate(q ? `/repository?q=${encodeURIComponent(q)}` : '/repository');
  };

  return (
    <div
      className={`relative min-h-screen flex flex-col overflow-hidden transition-colors duration-300 ${
        isDark ? 'bg-[#080d24]' : 'bg-slate-50'
      }`}
    >
      {/* ── Background decorations ─────────────────────────────────── */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        aria-hidden="true"
        style={{
          backgroundImage: isDark
            ? 'linear-gradient(rgba(59,130,246,0.065) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.065) 1px, transparent 1px)'
            : 'linear-gradient(rgba(99,102,241,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.05) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />
      {isDark && (
        <div
          className="pointer-events-none absolute inset-0 z-0"
          aria-hidden="true"
          style={{
            background:
              'radial-gradient(ellipse 70% 45% at 50% -4%, rgba(37,99,235,0.20) 0%, transparent 68%)',
          }}
        />
      )}
      {!isDark && (
        <div
          className="pointer-events-none absolute inset-0 z-0"
          aria-hidden="true"
          style={{
            background:
              'radial-gradient(ellipse 70% 40% at 50% 0%, rgba(219,234,254,0.6) 0%, transparent 70%)',
          }}
        />
      )}

      {/* ── Navbar ─────────────────────────────────────────────────── */}
      {/*
       * Three-column grid mirrors AppNavbar:
       *   col 1 (flex-1): logo — left
       *   col 2 (auto):   nav links — centered
       *   col 3 (flex-1): actions — right
       * Center column is hidden on < lg; nav is not shown on mobile here
       * because authenticated users get AppNavbar on interior pages.
       */}
      <nav
        className={`relative z-20 px-5 sm:px-8 lg:px-14 py-3 border-b ${
          isDark
            ? 'border-white/[0.06] bg-[#080d24]/75 backdrop-blur-md'
            : 'border-gray-200/80 bg-white/75 backdrop-blur-md'
        }`}
      >
        {/* ── MOBILE row (< lg): hamburger·logo LEFT, actions RIGHT ─── */}
        <div className="flex items-center justify-between lg:hidden">
          {/* Left group */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open navigation menu"
              className={`w-9 h-9 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 flex-shrink-0 ${
                isDark
                  ? 'text-gray-400 hover:text-white hover:bg-white/10'
                  : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
              }`}
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
              </svg>
            </button>
            <Link to="/" className="flex items-center gap-2 select-none">
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm flex-shrink-0 ${
                isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
              }`}>🎓</div>
              <span className={`text-sm font-bold tracking-wide ${isDark ? 'text-white' : 'text-gray-900'}`}>
                THESYS+
              </span>
            </Link>
          </div>
          {/* Right group */}
          <div className="flex items-center gap-2">
            {!isInitializing && isAuthenticated && (
              <AvatarDropdown
                user={user}
                isDark={isDark}
                onSignOut={async () => { await signOut(); navigate('/'); }}
              />
            )}
            {!isInitializing && !isAuthenticated && (
              <Link
                to="/sign-in"
                className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] active:bg-[var(--color-primary-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                Sign In
              </Link>
            )}
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
          </div>
        </div>

        {/* ── DESKTOP row (≥ lg): 3-column grid, nav centered ──────── */}
        <div className="hidden lg:grid grid-cols-[1fr_auto_1fr] items-center">
          {/* COL 1 — Logo */}
          <div className="flex items-center">
            <Link to="/" className="flex items-center gap-2 select-none">
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm flex-shrink-0 ${
                isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
              }`}>🎓</div>
              <span className={`text-sm font-bold tracking-wide ${isDark ? 'text-white' : 'text-gray-900'}`}>
                THESYS+
              </span>
            </Link>
          </div>

          {/* COL 2 — Centered nav links */}
          <ul className="flex items-center gap-1">
            {CORE_NAV.map(({ label, to, implemented }) => (
              <li key={label}>
                <Link
                  to={to}
                  title={implemented ? label : `${label} — coming soon`}
                  onClick={implemented ? undefined : (e) => e.preventDefault()}
                  aria-disabled={!implemented}
                  className={`
                    px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-150
                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400
                    ${implemented
                      ? isDark
                        ? 'text-gray-400 hover:text-white hover:bg-white/[0.06]'
                        : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100/70'
                      : isDark
                        ? 'text-gray-600 cursor-default pointer-events-none'
                        : 'text-gray-300 cursor-default pointer-events-none'
                    }
                  `}
                >
                  {label}
                  {!implemented && (
                    <span className={`ml-1 text-[9px] font-semibold uppercase tracking-wider align-middle ${
                      isDark ? 'text-gray-600' : 'text-gray-400'
                    }`}>soon</span>
                  )}
                </Link>
              </li>
            ))}
          </ul>

          {/* COL 3 — Actions */}
          <div className="flex items-center gap-2 justify-end">
            {!isInitializing && isAuthenticated && (
              <>
                <Link
                  to="/upload"
                  className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] active:bg-[var(--color-primary-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  Upload Thesis
                </Link>
                <AvatarDropdown
                  user={user}
                  isDark={isDark}
                  onSignOut={async () => { await signOut(); navigate('/'); }}
                />
              </>
            )}
            {!isInitializing && !isAuthenticated && (
              <Link
                to="/sign-in"
                className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] active:bg-[var(--color-primary-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                Sign In
              </Link>
            )}
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
          </div>
        </div>
      </nav>

      {/* Landing page mobile menu drawer */}
      {mobileMenuOpen && createPortal(
        <div className="fixed inset-0 z-[9999] lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation menu">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setMobileMenuOpen(false)} aria-hidden="true" />
          <div className={`absolute top-0 left-0 bottom-0 w-72 max-w-[85vw] shadow-2xl ${
            isDark ? 'bg-[#0f1a3a] border-r border-white/10' : 'bg-white border-r border-gray-200'
          }`}>
            <div className={`flex items-center justify-between px-5 py-4 border-b ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
              <div className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm ${
                  isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
                }`}>🎓</div>
                <span className={`text-sm font-bold tracking-wide ${isDark ? 'text-white' : 'text-gray-900'}`}>THESYS+</span>
              </div>
              <button type="button" onClick={() => setMobileMenuOpen(false)} aria-label="Close navigation menu"
                className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${
                  isDark ? 'text-gray-400 hover:text-white hover:bg-white/10' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
                }`}>
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>
            <nav className="p-4">
              <ul className="space-y-1">
                {CORE_NAV.map(({ label, to, implemented }) => (
                  <li key={label}>
                    <Link to={to} onClick={(e) => { if (!implemented) e.preventDefault(); else setMobileMenuOpen(false); }}
                      aria-disabled={!implemented}
                      className={`block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                        !implemented
                          ? isDark ? 'text-gray-600 cursor-default' : 'text-gray-300 cursor-default'
                          : isDark ? 'text-gray-300 hover:bg-white/[0.07] hover:text-white' : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                      }`}>
                      {label}
                      {!implemented && <span className={`ml-1.5 text-[9px] uppercase tracking-wider ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>soon</span>}
                    </Link>
                  </li>
                ))}
              </ul>
              {!isInitializing && isAuthenticated ? (
                <Link to="/upload" onClick={() => setMobileMenuOpen(false)}
                  className="mt-4 block w-full px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold text-center hover:bg-[var(--color-primary-hover)] transition-colors">
                  Upload Thesis
                </Link>
              ) : (
                <Link to="/sign-in" onClick={() => setMobileMenuOpen(false)}
                  className="mt-4 block w-full px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold text-center hover:bg-[var(--color-primary-hover)] transition-colors">
                  Sign In
                </Link>
              )}
            </nav>
          </div>
        </div>,
        document.body
      )}

      {/* ── Hero ───────────────────────────────────────────────────── */}
      <main className="relative z-10 flex flex-col items-center flex-1 justify-center px-4 py-12 sm:py-20 text-center">

        {/* AI badge */}
        <div
          className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-[11px] font-semibold tracking-[0.18em] uppercase mb-10 border select-none ${
            isDark
              ? 'border-blue-500/25 bg-blue-500/10 text-blue-400'
              : 'border-blue-200 bg-blue-50 text-blue-600'
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse inline-block" />
          AI-Assisted Research
        </div>

        {/* Title */}
        <h1
          className="font-extrabold tracking-tighter leading-none mb-6 select-none"
          style={{ fontSize: 'clamp(3.5rem, 12vw, 7.5rem)' }}
        >
          <span className={isDark ? 'text-white' : 'text-gray-900'}>THE</span>
          <span className="text-primary">SYS+</span>
        </h1>

        {/* Subtitle */}
        <p
          className={`max-w-xl text-sm sm:text-base leading-relaxed mb-10 ${
            isDark ? 'text-gray-400' : 'text-gray-500'
          }`}
        >
          A Semantic-Based Thesis Retrieval and Topic Trend Analysis System
          <br className="hidden sm:block" />
          designed to accelerate academic research with precision.
        </p>

        {/* Search bar */}
        <form
          id="hero-search-form"
          onSubmit={handleSearchSubmit}
          className={`w-full max-w-xl flex items-center rounded-xl px-4 py-3 mb-8 border transition-all duration-200 ${
            isDark
              ? 'bg-white/[0.04] border-white/10 hover:border-white/20 focus-within:border-blue-500/40 focus-within:bg-white/[0.06]'
              : 'bg-white border-gray-200 shadow-sm hover:border-gray-300 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100'
          }`}
        >
          <svg
            className={`w-4 h-4 mr-3 flex-shrink-0 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>

          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search for thesis topics, keywords, or authors..."
            className={`flex-1 bg-transparent text-sm outline-none min-w-0 ${
              isDark ? 'text-gray-200 placeholder-gray-600' : 'text-gray-700 placeholder-gray-400'
            }`}
            aria-label="Search thesis topics, keywords, or authors"
          />

          <kbd
            className={`hidden sm:flex items-center px-2 py-1 rounded text-[11px] font-mono border ml-3 flex-shrink-0 ${
              isDark ? 'border-white/15 text-gray-600 bg-white/[0.04]' : 'border-gray-200 text-gray-400 bg-gray-50'
            }`}
            aria-hidden="true"
          >
            ⌘K
          </kbd>
        </form>

        {/* CTA buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-3 mb-16 sm:mb-24">
          {/* Primary: Search Semantically — submits the hero search form */}
          <button
            type="submit"
            form="hero-search-form"
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] active:bg-[var(--color-primary-hover)] transition-all duration-150 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            Search Semantically
          </button>

          {/* Secondary: Check Title Similarity */}
          <Link
            to="/title-similarity"
            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold border transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
              isDark
                ? 'border-white/20 text-gray-200 hover:bg-white/[0.07] hover:border-white/30'
                : 'border-gray-300 text-gray-700 hover:bg-gray-100 hover:border-gray-400'
            }`}
          >
            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
            </svg>
            Check Title Similarity
          </Link>
        </div>

        {/* Stats row */}
        <div
          className={`w-full max-w-2xl grid grid-cols-3 rounded-2xl overflow-hidden border ${
            isDark
              ? 'border-white/[0.08] divide-x divide-white/[0.08]'
              : 'border-gray-200 divide-x divide-gray-200 shadow-sm'
          }`}
        >
          {stats.map((stat) => (
            <div
              key={stat.label}
              className={`flex flex-col items-center py-6 sm:py-8 px-3 sm:px-6 transition-colors ${
                isDark ? 'bg-white/[0.025] hover:bg-white/[0.05]' : 'bg-white hover:bg-gray-50'
              }`}
            >
              <span className={`text-2xl sm:text-4xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                {stat.value}
              </span>
              <span className={`text-xs sm:text-sm ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </main>

      {/* ── Cognitive Capabilities Section ────────────────────────── */}
      <section className="relative z-10 px-5 sm:px-8 lg:px-14 py-16 sm:py-20">
        <div className="max-w-6xl mx-auto">
          {/* Section header */}
          <div className="text-center mb-12">
            <h2 className={`text-3xl sm:text-4xl font-bold mb-3 ${isDark ? 'text-white' : 'text-gray-900'}`}>
              Cognitive Capabilities
            </h2>
            <p className={`text-sm sm:text-base max-w-2xl mx-auto ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              Advanced tools designed to streamline your academic research journey.
            </p>
          </div>

          {/* Feature cards grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Card 1: Semantic Search */}
            <div className="thesys-card p-6">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
                isDark ? 'bg-blue-500/15' : 'bg-blue-50'
              }`}>
                <svg className={`w-6 h-6 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
              </div>
              <h3 className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Semantic Search
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Find conceptually related studies using SBERT embeddings and cosine similarity.
              </p>
            </div>

            {/* Card 2: Title Similarity */}
            <div className="thesys-card p-6">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
                isDark ? 'bg-purple-500/15' : 'bg-purple-50'
              }`}>
                <svg className={`w-6 h-6 ${isDark ? 'text-purple-400' : 'text-purple-600'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                </svg>
              </div>
              <h3 className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Title Similarity
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Validate proposed thesis titles against existing repository records.
              </p>
            </div>

            {/* Card 3: Topic Trend Analysis */}
            <div className="thesys-card p-6">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
                isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'
              }`}>
                <svg className={`w-6 h-6 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                </svg>
              </div>
              <h3 className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Topic Trend Analysis
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Identify saturated, emerging, and underexplored research topics using TF-IDF and K-Means clustering.
              </p>
            </div>

            {/* Card 4: Analytics Dashboard */}
            <div className="thesys-card p-6">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
                isDark ? 'bg-amber-500/15' : 'bg-amber-50'
              }`}>
                <svg className={`w-6 h-6 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                </svg>
              </div>
              <h3 className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Analytics Dashboard
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                View repository insights, program distribution, and historical research growth.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer className={`relative z-10 border-t ${isDark ? 'border-white/[0.06] bg-[#080d24]' : 'border-gray-200 bg-white'}`}>
        <div className="max-w-6xl mx-auto px-5 sm:px-8 lg:px-14 py-8 sm:py-10">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
            {/* Brand column */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm ${
                  isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
                }`}>
                  🎓
                </div>
                <span className={`text-base font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                  THESYS+
                </span>
              </div>
              <p className={`text-xs leading-relaxed ${isDark ? 'text-gray-500' : 'text-gray-600'}`}>
                Semantic-Based Thesis Retrieval and Topic Trend Analysis System
              </p>
            </div>

            {/* Institution column */}
            <div>
              <h3 className={`text-xs font-semibold uppercase tracking-wider mb-3 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Institution
              </h3>
              <p className={`text-xs leading-relaxed ${isDark ? 'text-gray-500' : 'text-gray-600'}`}>
                Pampanga State University
                <br />
                College of Computing Studies
              </p>
            </div>

            {/* Links column */}
            <div>
              <h3 className={`text-xs font-semibold uppercase tracking-wider mb-3 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Resources
              </h3>
              <ul className="space-y-2">
                <li>
                  <button
                    type="button"
                    onClick={() => setLegalModal('privacy')}
                    className={`text-xs transition-colors text-left ${isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-600 hover:text-gray-900'}`}
                  >
                    Privacy Policy
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={() => setLegalModal('terms')}
                    className={`text-xs transition-colors text-left ${isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-600 hover:text-gray-900'}`}
                  >
                    Terms
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={() => setLegalModal('help')}
                    className={`text-xs transition-colors text-left ${isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-600 hover:text-gray-900'}`}
                  >
                    Help Center
                  </button>
                </li>
              </ul>
            </div>
          </div>

          {/* Copyright */}
          <div className={`pt-6 border-t text-center ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}>
            <p className={`text-xs ${isDark ? 'text-gray-600' : 'text-gray-500'}`}>
              © 2026 THESYS+. All rights reserved.
            </p>
          </div>
        </div>
      </footer>

      {/* Legal Modal */}
      <LegalModal
        isOpen={legalModal !== null}
        onClose={() => setLegalModal(null)}
        type={legalModal}
        isDark={isDark}
      />
    </div>
  );
}
