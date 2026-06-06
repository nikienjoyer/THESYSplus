/**
 * LandingPage — THESYS+ public landing page (Phase 3 institutional redesign).
 *
 * Sections: Navigation · Hero (with CCS building visual) · Repository Snapshot ·
 *           Feature Showcase · Trending Topics Preview · Why THESYS+ · Footer
 *
 * Privacy: logged-out users see aggregate-only data (thesis count, topic
 * labels + counts). No thesis titles, abstracts, authors, or documents.
 *
 * Building image: place a cleaned CCS façade photo at
 *   public/ccs-bldg.jpg
 * The hero detects and uses it with a gradient overlay; if absent, a
 * refined institutional gradient renders instead (graceful fallback).
 */

import { Link, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Sun, Moon, Search, ShieldCheck, TrendingUp, BarChart3, ArrowRight } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../hooks/useAuth';
import client from '../api/client';
import { AvatarDropdown } from '../components/layout/AppNavbar';
import LegalModal from '../components/legal/LegalModal';
import ThesysLogo from '../components/brand/ThesysLogo';

// Core module nav links.
const CORE_NAV = [
  { label: 'Home',             to: '/',                 implemented: true  },
  { label: 'Repository',       to: '/repository',       implemented: true  },
  { label: 'Title Similarity', to: '/title-similarity', implemented: true  },
  { label: 'Trend Analysis',   to: '/trend-analysis',   implemented: true  },
  { label: 'Analytics',        to: '/analytics',        implemented: true  },
];

// Path to the (optional) cleaned CCS building photo, served from /public.
const CCS_BUILDING_IMG = '/ccs-bldg.jpg';

export default function LandingPage() {
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated, isInitializing, user, signOut } = useAuth();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [thesisCount, setThesisCount] = useState(null);
  const [topics, setTopics] = useState(null);   // trending topics preview (aggregate only)
  const [legalModal, setLegalModal] = useState(null); // 'privacy' | 'terms' | 'help' | null
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [hasBuildingImg, setHasBuildingImg] = useState(false);
  const isDark = theme === 'dark';

  // Close mobile menu on Escape key
  useEffect(() => {
    function handleEscape(e) {
      if (e.key === 'Escape' && mobileMenuOpen) setMobileMenuOpen(false);
    }
    if (mobileMenuOpen) document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [mobileMenuOpen]);

  // Detect whether the cleaned CCS building photo is present in /public.
  // If it loads, the hero uses it; otherwise the gradient fallback renders.
  useEffect(() => {
    let cancelled = false;
    const img = new Image();
    img.onload = () => { if (!cancelled) setHasBuildingImg(true); };
    img.onerror = () => { if (!cancelled) setHasBuildingImg(false); };
    img.src = CCS_BUILDING_IMG;
    return () => { cancelled = true; };
  }, []);

  // Fetch the public thesis count (aggregate only, no auth, no content).
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
  }, []);

  // Fetch trending topics for the preview. Only used when authenticated
  // (the topic-trends endpoint requires auth). Logged-out users get the
  // graceful representative fallback. Aggregate labels + counts only —
  // never thesis content.
  useEffect(() => {
    if (isInitializing || !isAuthenticated) return;
    let cancelled = false;
    client.get('/theses/topic-trends/')
      .then((res) => {
        if (!cancelled && res.data?.clusters) {
          setTopics(res.data.clusters.slice(0, 6).map((c) => ({
            topic: c.topic,
            count: c.thesis_count,
            trend: c.trend,
          })));
        }
      })
      .catch(() => { /* best-effort — fallback preview shown */ });
    return () => { cancelled = true; };
  }, [isAuthenticated, isInitializing]);

  const thesisCountLabel = thesisCount !== null ? String(thesisCount) : '…';

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    const q = searchQuery.trim();
    navigate(q ? `/repository?q=${encodeURIComponent(q)}` : '/repository');
  };

  return (
    <div className="relative min-h-screen flex flex-col bg-canvas transition-colors duration-300">

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
              <ThesysLogo variant="wordmark" size={28} isDark={isDark} />
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
              <ThesysLogo variant="wordmark" size={28} isDark={isDark} />
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
              <ThesysLogo variant="wordmark" size={28} isDark={isDark} />
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
      <main className="relative z-10">
        <section className="relative overflow-hidden">
          {/* Building visual layer — uses cleaned CCS photo when present,
              otherwise an institutional gradient. Always overlaid so text
              stays legible and the page never looks like a photo gallery. */}
          <div className="absolute inset-0 z-0" aria-hidden="true">
            {hasBuildingImg && (
              <div
                className="absolute inset-0 bg-cover bg-center"
                style={{ backgroundImage: `url(${CCS_BUILDING_IMG})` }}
              />
            )}
            {/* Readability overlay.
                Dark:  unchanged — 0.72 → 0.86 → 1.
                Light: reduced white so the CCS façade reads clearly;
                       fades to solid canvas white only at the very bottom
                       so lower sections remain clean. */}
            <div
              className="absolute inset-0"
              style={{
                background: isDark
                  ? 'linear-gradient(180deg, rgba(8,13,36,0.72) 0%, rgba(8,13,36,0.86) 60%, rgba(8,13,36,1) 100%)'
                  : 'linear-gradient(180deg, rgba(248,250,252,0.52) 0%, rgba(248,250,252,0.72) 55%, rgba(248,250,252,1) 100%)',
              }}
            />
            {/* Institutional blue tint.
                Dark:  unchanged radial wash.
                Light: stronger coverage + linear sweep so the tint feels
                       intentional rather than accidental; still subtle enough
                       to keep text contrast intact. */}
            <div
              className="absolute inset-0"
              style={{
                background: isDark
                  ? 'radial-gradient(ellipse 70% 50% at 50% -10%, rgba(30,64,175,0.25) 0%, transparent 70%)'
                  : 'linear-gradient(160deg, rgba(30,64,175,0.18) 0%, rgba(30,64,175,0.10) 40%, transparent 70%)',
              }}
            />
          </div>

          {/* Hero content — ~12% less vertical padding than before (py-14/py-20) */}
          <div className="relative z-10 max-w-3xl mx-auto px-5 sm:px-8 py-14 sm:py-20 text-center">
            {/* Eyebrow — institutional framing */}
            <p className={`text-xs sm:text-sm font-semibold tracking-wide mb-5 ${isDark ? 'text-blue-300' : 'text-primary'}`}>
              PampangaStateU • College of Computing Studies
            </p>

            {/* Headline */}
            <h1
              className={`font-bold tracking-tight mb-5 ${isDark ? 'text-white' : 'text-gray-900'}`}
              style={{ fontSize: 'clamp(1.75rem, 5vw, 3rem)', textWrap: 'balance', lineHeight: 1.1 }}
            >
              Explore, validate, and discover undergraduate research within PampangaStateU CCS.
            </h1>

            {/* Supporting text */}
            <p
              className={`max-w-2xl mx-auto text-sm sm:text-base leading-relaxed mb-9 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}
              style={{ textWrap: 'pretty' }}
            >
              Search previous studies by meaning, check title originality, and analyze emerging
              research trends through AI-assisted retrieval.
            </p>

            {/* Search bar — widened to max-w-2xl to anchor it as primary interaction */}
            <form
              id="hero-search-form"
              onSubmit={handleSearchSubmit}
              className={`w-full max-w-2xl mx-auto flex items-center rounded-xl px-4 py-3 mb-5 border transition-all duration-200 ${
                isDark
                  ? 'bg-white/[0.06] border-white/15 hover:border-white/25 focus-within:border-blue-500/50 focus-within:bg-white/[0.08]'
                  : 'bg-white border-gray-200 shadow-sm hover:border-gray-300 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100'
              }`}
            >
              <Search className={`w-4 h-4 mr-3 flex-shrink-0 ${isDark ? 'text-gray-400' : 'text-gray-400'}`} aria-hidden="true" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search for thesis topics, keywords, or authors..."
                className={`flex-1 bg-transparent text-sm outline-none min-w-0 ${
                  isDark ? 'text-gray-100 placeholder-gray-500' : 'text-gray-700 placeholder-gray-400'
                }`}
                aria-label="Search thesis topics, keywords, or authors"
              />
              <kbd
                className={`hidden sm:flex items-center px-2 py-1 rounded text-[11px] font-mono border ml-3 flex-shrink-0 ${
                  isDark ? 'border-white/15 text-gray-500 bg-white/[0.04]' : 'border-gray-200 text-gray-400 bg-gray-50'
                }`}
                aria-hidden="true"
              >
                ⌘K
              </kbd>
            </form>

            {/* CTA buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                type="submit"
                form="hero-search-form"
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] active:bg-[var(--color-primary-hover)] transition-all duration-150 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                <Search className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                Search Semantically
              </button>
              <Link
                to="/title-similarity"
                className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold border transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                  isDark
                    ? 'border-white/20 text-gray-100 hover:bg-white/[0.08] hover:border-white/30'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-100 hover:border-gray-400'
                }`}
              >
                <ShieldCheck className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                Check Title Similarity
              </Link>
            </div>
          </div>
        </section>

        {/* ── Repository Snapshot ──────────────────────────────────── */}
        <section className="relative z-10 px-5 sm:px-8 lg:px-14 pb-4">
          <div className="max-w-4xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Card 1 — live thesis count */}
            <div className={`thesys-card p-6 text-center border-t-2 ${isDark ? 'border-t-blue-500/40' : 'border-t-blue-600/30'}`}>
              <div className={`text-3xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                {thesisCountLabel}
              </div>
              <div className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                Undergraduate Theses Indexed
              </div>
            </div>
            {/* Card 2 — corpus coverage */}
            <div className={`thesys-card p-6 text-center border-t-2 ${isDark ? 'border-t-blue-500/40' : 'border-t-blue-600/30'}`}>
              <div className={`text-3xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                2024–2025
              </div>
              <div className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                Corpus Coverage
              </div>
              <div className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                Current repository coverage
              </div>
            </div>
            {/* Card 3 — research domains */}
            <div className={`thesys-card p-6 text-center border-t-2 ${isDark ? 'border-t-blue-500/40' : 'border-t-blue-600/30'}`}>
              <div className={`text-3xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                BSIS • BSIT • BSCS
              </div>
              <div className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                Research Domains
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ── Feature Showcase ──────────────────────────────────────── */}
      <section className="relative z-10 px-5 sm:px-8 lg:px-14 py-16 sm:py-20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className={`text-2xl sm:text-3xl font-bold mb-3 ${isDark ? 'text-white' : 'text-gray-900'}`}>
              Research tools, built for CCS
            </h2>
            <p className={`text-sm sm:text-base max-w-2xl mx-auto ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              Four capabilities that support the undergraduate thesis lifecycle, from proposal to archive.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Semantic Search */}
            <div className="thesys-card p-6">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${isDark ? 'bg-blue-500/15' : 'bg-blue-50'}`}>
                <Search className={`w-6 h-6 ${isDark ? 'text-blue-300' : 'text-primary'}`} aria-hidden="true" />
              </div>
              <h3 className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Semantic Search
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Find relevant theses by meaning, not just keywords.
              </p>
            </div>

            {/* Title Similarity Validation */}
            <div className="thesys-card p-6">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${isDark ? 'bg-blue-500/15' : 'bg-blue-50'}`}>
                <ShieldCheck className={`w-6 h-6 ${isDark ? 'text-blue-300' : 'text-primary'}`} aria-hidden="true" />
              </div>
              <h3 className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Title Similarity Validation
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Evaluate thesis title originality before proposal submission.
              </p>
            </div>

            {/* Trend Analysis */}
            <div className="thesys-card p-6">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'}`}>
                <TrendingUp className={`w-6 h-6 ${isDark ? 'text-emerald-300' : 'text-emerald-600'}`} aria-hidden="true" />
              </div>
              <h3 className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Trend Analysis
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Identify emerging and saturated research areas.
              </p>
            </div>

            {/* Analytics Dashboard */}
            <div className="thesys-card p-6">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${isDark ? 'bg-amber-500/15' : 'bg-amber-50'}`}>
                <BarChart3 className={`w-6 h-6 ${isDark ? 'text-amber-300' : 'text-amber-600'}`} aria-hidden="true" />
              </div>
              <h3 className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Analytics Dashboard
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Understand repository growth and usage insights.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Trending Topics Preview ───────────────────────────────── */}
      <section className={`relative z-10 px-5 sm:px-8 lg:px-14 py-16 sm:py-20 border-t ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}>
        <div className="max-w-5xl mx-auto">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-8">
            <div>
              <h2 className={`text-2xl sm:text-3xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Trending research topics
              </h2>
              <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Aggregate topic clusters across the CCS thesis corpus. Topic labels and counts only.
              </p>
            </div>
            <Link
              to="/trend-analysis"
              className={`inline-flex items-center gap-1.5 text-sm font-semibold whitespace-nowrap ${isDark ? 'text-blue-300 hover:text-blue-200' : 'text-primary hover:opacity-80'}`}
            >
              View Full Trend Analysis
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </Link>
          </div>

          {(() => {
            // Use live trend data when available (authenticated); otherwise a
            // representative aggregate preview. No thesis content is shown.
            const TREND_FALLBACK = [
              { topic: 'Attendance and Monitoring Systems', count: 12, trend: 'SATURATED' },
              { topic: 'Inventory and POS Systems',         count: 12, trend: 'SATURATED' },
              { topic: 'Learning Management / EdTech',       count: 11, trend: 'SATURATED' },
              { topic: 'AI and Machine Learning',            count: 10, trend: 'EMERGING' },
              { topic: 'IoT and Embedded Systems',           count: 10, trend: 'EMERGING' },
              { topic: 'Health Information Systems',         count: 10, trend: 'EMERGING' },
            ];
            const list = (topics && topics.length > 0) ? topics : TREND_FALLBACK;

            const trendChip = (trend) => {
              const map = {
                SATURATED:      { label: 'Saturated',     cls: isDark ? 'bg-rose-500/15 text-rose-300 border-rose-500/30' : 'bg-rose-50 text-rose-700 border-rose-200' },
                EMERGING:       { label: 'Emerging',      cls: isDark ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' : 'bg-amber-50 text-amber-700 border-amber-200' },
                UNDEREXPLORED:  { label: 'Underexplored', cls: isDark ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-emerald-50 text-emerald-700 border-emerald-200' },
              };
              return map[trend] || map.EMERGING;
            };

            return (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {list.map((t) => {
                  const chip = trendChip(t.trend);
                  return (
                    <div key={t.topic} className="thesys-card p-4 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className={`text-sm font-semibold truncate ${isDark ? 'text-gray-100' : 'text-gray-900'}`} title={t.topic}>
                          {t.topic}
                        </div>
                        <div className={`text-xs mt-0.5 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                          {t.count} thes{t.count === 1 ? 'is' : 'es'}
                        </div>
                      </div>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border whitespace-nowrap flex-shrink-0 ${chip.cls}`}>
                        {chip.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </div>
      </section>

      {/* ── Why THESYS+ ───────────────────────────────────────────── */}
      <section className="relative z-10 px-5 sm:px-8 lg:px-14 py-16 sm:py-20">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className={`text-2xl sm:text-3xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
              Why THESYS+
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center px-2">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4 ${isDark ? 'bg-blue-500/15' : 'bg-blue-50'}`}>
                <ShieldCheck className={`w-6 h-6 ${isDark ? 'text-blue-300' : 'text-primary'}`} aria-hidden="true" />
              </div>
              <h3 className={`text-base font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Prevent Topic Duplication
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Validate titles early to avoid overlapping research.
              </p>
            </div>
            <div className="text-center px-2">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4 ${isDark ? 'bg-blue-500/15' : 'bg-blue-50'}`}>
                <Search className={`w-6 h-6 ${isDark ? 'text-blue-300' : 'text-primary'}`} aria-hidden="true" />
              </div>
              <h3 className={`text-base font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Improve Discoverability
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Find previous CCS theses using meaning-based retrieval.
              </p>
            </div>
            <div className="text-center px-2">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4 ${isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'}`}>
                <TrendingUp className={`w-6 h-6 ${isDark ? 'text-emerald-300' : 'text-emerald-600'}`} aria-hidden="true" />
              </div>
              <h3 className={`text-base font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Reveal Research Trends
              </h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Guide future researchers through trend insights.
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
                <ThesysLogo variant="wordmark" size={28} isDark={isDark} />
              </div>
              <p className={`text-xs leading-relaxed ${isDark ? 'text-gray-500' : 'text-gray-600'}`}>
                THESYS+ — Semantic-Based Thesis Retrieval and Topic Trend Analysis System
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
