/**
 * LandingPage — THESYS+ public landing page.
 *
 * Layout (reference: attached screenshot):
 *   Sticky Navbar · Split Hero (left: text+search / right: CCS building photo) ·
 *   Repository Snapshot · Feature Showcase (4-col) ·
 *   [Trending Topics Preview + Why THESYS+] side-by-side · Dark Footer
 *
 * Privacy: logged-out users see aggregate-only data. No thesis titles,
 * abstracts, authors, or documents are exposed.
 *
 * Building image: public/ccs-bldg.jpg — rendered directly in the right
 * panel with only a subtle left-edge fade for blending. Falls back to a
 * light-blue institutional tint when absent.
 */

import { Link, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  Sun, Moon, Search, ShieldCheck, TrendingUp, BarChart3,
  ArrowRight, BookOpen, GraduationCap, LayoutDashboard,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../hooks/useAuth';
import client from '../api/client';
import { AvatarDropdown } from '../components/layout/AppNavbar';
import { useUploadModal } from '../hooks/useUploadModal';
import LegalModal from '../components/legal/LegalModal';
import ThesysLogo from '../components/brand/ThesysLogo';
import useFocusTrap from '../hooks/useFocusTrap';

const CORE_NAV = [
  { label: 'Home',             to: '/',                 implemented: true },
  { label: 'Repository',       to: '/repository',       implemented: true },
  { label: 'Title Similarity', to: '/title-similarity', implemented: true },
  { label: 'Trend Analysis',   to: '/trend-analysis',   implemented: true },
  { label: 'Analytics',        to: '/analytics',        implemented: true },
];

const CCS_BUILDING_IMG = '/ccs-bldg.jpg';

// Feature cards — "Learn more" only links to pages that actually exist.
const FEATURES = [
  {
    icon: Search,
    iconBg:   { light: 'bg-blue-50',    dark: 'bg-blue-500/15'    },
    iconColor:{ light: 'text-primary',  dark: 'text-blue-300'     },
    title: 'Semantic Search',
    desc:  'Find relevant theses by meaning, not just keywords using SBERT embeddings.',
    to:    '/repository',
    linkLabel: 'Open Repository',
  },
  {
    icon: ShieldCheck,
    iconBg:   { light: 'bg-blue-50',    dark: 'bg-blue-500/15'    },
    iconColor:{ light: 'text-primary',  dark: 'text-blue-300'     },
    title: 'Title Similarity Validation',
    desc:  'Check the originality of your proposed title using cosine similarity and TF-IDF.',
    to:    '/title-similarity',
    linkLabel: 'Validate a title',
  },
  {
    icon: TrendingUp,
    iconBg:   { light: 'bg-emerald-50', dark: 'bg-emerald-500/15' },
    iconColor:{ light: 'text-emerald-600', dark: 'text-emerald-300' },
    title: 'Trend Analysis',
    desc:  'Discover emerging and saturated research areas using clustering and topic modeling.',
    to:    '/trend-analysis',
    linkLabel: 'View trends',
  },
  {
    icon: BarChart3,
    iconBg:   { light: 'bg-amber-50',   dark: 'bg-amber-500/15'   },
    iconColor:{ light: 'text-amber-600', dark: 'text-amber-300'   },
    title: 'Analytics Dashboard',
    desc:  'Visualize repository insights, search behavior, and research trends over time.',
    to:    '/analytics',
    linkLabel: 'Open Analytics',
  },
];

export default function LandingPage() {
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated, isInitializing, user, signOut } = useAuth();
  const { open: openUpload } = useUploadModal();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery]   = useState('');
  const [thesisCount, setThesisCount]   = useState(null);
  const [topics, setTopics]             = useState(null);
  const [legalModal, setLegalModal]     = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [hasBuildingImg, setHasBuildingImg] = useState(false);
  const isDark = theme === 'dark';
  const drawerRef = useFocusTrap(mobileMenuOpen);

  // Escape closes mobile menu
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape' && mobileMenuOpen) setMobileMenuOpen(false); }
    if (mobileMenuOpen) document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [mobileMenuOpen]);

  // Probe whether the building photo is available
  useEffect(() => {
    let cancelled = false;
    const img = new Image();
    img.onload  = () => { if (!cancelled) setHasBuildingImg(true);  };
    img.onerror = () => { if (!cancelled) setHasBuildingImg(false); };
    img.src = CCS_BUILDING_IMG;
    return () => { cancelled = true; };
  }, []);

  // Public thesis count — aggregate only, no auth required
  useEffect(() => {
    let cancelled = false;
    client.get('/theses/public-stats/')
      .then((res) => {
        if (!cancelled && typeof res.data.indexed_theses_count === 'number')
          setThesisCount(res.data.indexed_theses_count);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Trending topics — auth-gated; fallback shown to logged-out users
  useEffect(() => {
    if (isInitializing || !isAuthenticated) return;
    let cancelled = false;
    client.get('/theses/topic-trends/')
      .then((res) => {
        if (!cancelled && res.data?.clusters)
          setTopics(res.data.clusters.slice(0, 6).map((c) => ({
            topic: c.topic, count: c.thesis_count, trend: c.trend,
          })));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [isAuthenticated, isInitializing]);

  const thesisCountLabel = thesisCount !== null ? String(thesisCount) : '…';

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    const q = searchQuery.trim();
    navigate(q ? `/repository?q=${encodeURIComponent(q)}` : '/repository');
  };

  // ── Trend chip helper ──────────────────────────────────────────────
  const trendChip = (trend) => {
    const map = {
      SATURATED:     { label: 'Saturated',     cls: isDark ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'     : 'bg-rose-50 text-rose-700 border-rose-200'     },
      EMERGING:      { label: 'Emerging',      cls: isDark ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'  : 'bg-amber-50 text-amber-700 border-amber-200'  },
      UNDEREXPLORED: { label: 'Underexplored', cls: isDark ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    };
    return map[trend] || map.EMERGING;
  };

  const TREND_FALLBACK = [
    { topic: 'Attendance Monitoring Systems', count: 12, trend: 'SATURATED'     },
    { topic: 'Inventory Management Systems',  count: 12, trend: 'SATURATED'     },
    { topic: 'AI and Machine Learning',       count:  9, trend: 'EMERGING'      },
    { topic: 'Mobile Applications',           count:  8, trend: 'EMERGING'      },
    { topic: 'Health Information Systems',    count:  6, trend: 'UNDEREXPLORED' },
  ];
  const trendList = (topics && topics.length > 0) ? topics.slice(0, 4) : TREND_FALLBACK.slice(0, 4);

  return (
    <div className={`min-h-screen flex flex-col ${isDark ? 'bg-[#080d24]' : 'bg-white'} transition-colors duration-300`}>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          NAVBAR — sticky, auth-aware, matches app branding
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <nav className={`sticky top-0 z-30 px-5 sm:px-8 lg:px-14 py-3 border-b ${
        isDark
          ? 'border-white/[0.06] bg-[#080d24]/90 backdrop-blur-md'
          : 'border-gray-200 bg-white/95 backdrop-blur-md'
      }`}>
        {/* Mobile row */}
        <div className="flex items-center justify-between lg:hidden">
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setMobileMenuOpen(true)} aria-label="Open navigation menu"
              className={`w-9 h-9 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                isDark ? 'text-gray-400 hover:text-white hover:bg-white/10' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
              }`}>
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
              </svg>
            </button>
            <Link to="/" className="flex items-center gap-2 select-none">
              <ThesysLogo variant="wordmark" size={28} isDark={isDark} />
            </Link>
          </div>
          <div className="flex items-center gap-2">
            {!isInitializing && isAuthenticated && (
              <AvatarDropdown user={user} isDark={isDark} onSignOut={async () => { await signOut(); navigate('/'); }} />
            )}
            {!isInitializing && !isAuthenticated && (
              <Link to="/sign-in" className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                Sign In
              </Link>
            )}
            <button type="button" onClick={toggleTheme} aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className={`w-9 h-9 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                isDark ? 'text-gray-400 hover:text-white hover:bg-white/10' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
              }`}>
              {isDark ? <Sun className="h-5 w-5 text-primary" /> : <Moon className="h-5 w-5 text-primary" />}
            </button>
          </div>
        </div>

        {/* Desktop row */}
        <div className="hidden lg:grid grid-cols-[1fr_auto_1fr] items-center">
          <Link to="/" className="flex items-center gap-2 select-none">
            <ThesysLogo variant="wordmark" size={28} isDark={isDark} />
          </Link>
          <ul className="flex items-center gap-1">
            {CORE_NAV.map(({ label, to, implemented }) => (
              <li key={label}>
                <Link to={to} onClick={implemented ? undefined : (e) => e.preventDefault()}
                  aria-disabled={!implemented}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                    implemented
                      ? isDark ? 'text-gray-400 hover:text-white hover:bg-white/[0.06]' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100/70'
                      : isDark ? 'text-gray-600 cursor-default pointer-events-none'      : 'text-gray-300 cursor-default pointer-events-none'
                  }`}>
                  {label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2 justify-end">
            {!isInitializing && isAuthenticated && (
              <>
                <button type="button" onClick={openUpload} className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                  Upload Thesis
                </button>
                <AvatarDropdown user={user} isDark={isDark} onSignOut={async () => { await signOut(); navigate('/'); }} />
              </>
            )}
            {!isInitializing && !isAuthenticated && (
              <Link to="/sign-in" className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                Sign In
              </Link>
            )}
            <button type="button" onClick={toggleTheme} aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className={`w-9 h-9 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                isDark ? 'text-gray-400 hover:text-white hover:bg-white/10' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
              }`}>
              {isDark ? <Sun className="h-5 w-5 text-primary" /> : <Moon className="h-5 w-5 text-primary" />}
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile drawer */}
      {mobileMenuOpen && createPortal(
        <div className="fixed inset-0 z-[9999] lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation menu">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm thesys-overlay-enter" onClick={() => setMobileMenuOpen(false)} aria-hidden="true" />
          <div ref={drawerRef} className={`absolute top-0 left-0 bottom-0 w-72 max-w-[85vw] shadow-2xl thesys-drawer-enter ${isDark ? 'bg-[#0f1a3a] border-r border-white/10' : 'bg-white border-r border-gray-200'}`}>
            <div className={`flex items-center justify-between px-5 py-4 border-b ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
              <ThesysLogo variant="wordmark" size={28} isDark={isDark} />
              <button type="button" onClick={() => setMobileMenuOpen(false)} aria-label="Close navigation menu"
                className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${isDark ? 'text-gray-400 hover:text-white hover:bg-white/10' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'}`}>
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
                    </Link>
                  </li>
                ))}
              </ul>
              {!isInitializing && isAuthenticated
                ? <button type="button" onClick={() => { setMobileMenuOpen(false); openUpload(); }} className="mt-4 block w-full px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold text-center hover:bg-[var(--color-primary-hover)] transition-colors">Upload Thesis</button>
                : <Link to="/sign-in" onClick={() => setMobileMenuOpen(false)} className="mt-4 block w-full px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold text-center hover:bg-[var(--color-primary-hover)] transition-colors">Sign In</Link>
              }
            </nav>
          </div>
        </div>,
        document.body
      )}

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          HERO — split layout: left text+search / right building photo
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <main>
        <section className={`relative overflow-hidden ${isDark ? 'bg-[#080d24]' : 'bg-[#eef3fb]'}`}>
          {/* Mobile building strip — visible only below lg, gives the hero institutional
              presence on phones without the full split layout (m2 fix) */}
          {hasBuildingImg && (
            <div className="lg:hidden relative h-36 overflow-hidden" aria-hidden="true">
              <img
                src={CCS_BUILDING_IMG}
                alt=""
                className="w-full h-full object-cover"
                style={{ objectPosition: '60% 30%' }}
                loading="eager"
                draggable="false"
              />
              <div className="absolute inset-0" style={{
                background: isDark
                  ? 'linear-gradient(180deg, rgba(8,13,36,0.2) 0%, rgba(8,13,36,0.85) 100%)'
                  : 'linear-gradient(180deg, rgba(238,243,251,0.1) 0%, rgba(238,243,251,0.9) 100%)',
              }} />
            </div>
          )}
          {/* Full-width grid — no max-w cap on the hero itself so it fills the viewport */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr] min-h-[min(68vh,520px)]">

            {/* LEFT — text + search: padded column, inner content capped so it reads
                  toward the center seam rather than drifting to the outer edge on
                  wide viewports (m3 fix) */}
            <div className="relative z-10 flex flex-col justify-center px-8 sm:px-12 lg:px-16 xl:px-20 py-12 lg:py-16 max-w-3xl lg:max-w-none lg:ml-auto lg:mr-0 lg:w-full">
              <div className="lg:max-w-2xl lg:ml-auto lg:mr-8">
              {/* Breadcrumb eyebrow */}
              <p className={`text-xs font-medium mb-4 ${isDark ? 'text-blue-300' : 'text-primary'}`}>
                Pampanga State University
                <span className={`mx-1.5 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>•</span>
                College of Computing Studies
              </p>

              {/* Headline — "undergraduate research" emphasized via weight + ink-blue,
                  deliberately NOT the link/action blue so it doesn't read as clickable */}
              <h1 className={`font-bold tracking-tight mb-4 leading-tight ${isDark ? 'text-white' : 'text-gray-900'}`}
                style={{ fontSize: 'clamp(1.75rem, 2.8vw, 3rem)' }}>
                Explore, validate, and discover{' '}
                <span className={`font-extrabold ${isDark ? 'text-blue-200' : 'text-[#1e3a8a]'}`}>undergraduate research</span>{' '}
                within PampangaStateU CCS.
              </h1>

              {/* Supporting text */}
              <p className={`text-sm sm:text-base leading-relaxed mb-7 max-w-lg ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                Search previous studies by meaning, check title originality,
                and analyze emerging research trends through AI-assisted retrieval.
              </p>

              {/* Unified search unit: input + trailing Search Semantically button read
                  as one control. Stacks the button below the field only on the
                  narrowest screens (flex-wrap). Enter / form submission unchanged. */}
              <form id="hero-search-form" onSubmit={handleSearchSubmit}
                className="mb-4 max-w-xl flex flex-wrap sm:flex-nowrap items-stretch gap-2">
                <div
                  className={`flex items-center rounded-lg px-4 py-2.5 border transition-all duration-200 flex-1 min-w-0 ${
                    isDark
                      ? 'bg-white/[0.07] border-white/15 hover:border-white/25 focus-within:border-blue-500/60 focus-within:bg-white/[0.09]'
                      : 'bg-white border-gray-300 shadow-sm hover:border-gray-400 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100'
                  }`}>
                  <Search className={`w-4 h-4 mr-3 flex-shrink-0 ${isDark ? 'text-gray-400' : 'text-gray-400'}`} aria-hidden="true" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search for thesis topics, keywords, or authors..."
                    className={`flex-1 bg-transparent text-sm outline-none min-w-0 ${isDark ? 'text-gray-100 placeholder-gray-500' : 'text-gray-700 placeholder-gray-400'}`}
                    aria-label="Search thesis topics, keywords, or authors"
                  />
                </div>
                <button type="submit"
                  className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold whitespace-nowrap w-full sm:w-auto flex-shrink-0 hover:bg-[var(--color-primary-hover)] transition-all duration-150 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                  <Search className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                  Search Semantically
                </button>
              </form>

              {/* Secondary CTA */}
              <div className="flex flex-wrap gap-3">
                <Link to="/title-similarity"
                  className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold border transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                    isDark
                      ? 'border-white/20 text-gray-100 hover:bg-white/[0.08] hover:border-white/30'
                      : 'border-gray-300 text-gray-700 bg-white hover:bg-gray-50 hover:border-gray-400'
                  }`}>
                  <ShieldCheck className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                  Check Title Similarity
                </Link>
              </div>
              </div>
            </div>

            {/* RIGHT — CCS building photo: fills the full grid column */}
            <div className="relative hidden lg:block overflow-hidden" aria-hidden="true">
              {hasBuildingImg ? (
                <>
                  <img
                    src={CCS_BUILDING_IMG}
                    alt=""
                    className="w-full h-full object-cover"
                    style={{ objectPosition: '60% 40%' }}
                    loading="eager"
                    draggable="false"
                  />
                  {/* Left-edge fade: extended multi-stop blend so the panel and photo
                      read as one cohesive hero. Transparent stop pushed ~25% further
                      right while keeping the façade recognizable. */}
                  <div className="absolute inset-0" style={{
                    background: isDark
                      ? 'linear-gradient(90deg, rgba(8,13,36,1) 0%, rgba(8,13,36,0.9) 18%, rgba(8,13,36,0.6) 38%, rgba(8,13,36,0.28) 58%, rgba(8,13,36,0.08) 78%, transparent 92%)'
                      : 'linear-gradient(90deg, rgba(238,243,251,1) 0%, rgba(238,243,251,0.9) 16%, rgba(238,243,251,0.6) 36%, rgba(238,243,251,0.28) 56%, rgba(238,243,251,0.08) 76%, transparent 90%)',
                  }} />
                  {/* Bottom vignette to blend with snapshot section */}
                  <div className="absolute inset-0" style={{
                    background: 'linear-gradient(180deg, transparent 62%, rgba(0,0,0,0.16) 100%)',
                  }} />
                </>
              ) : (
                <div className={`absolute inset-0 ${isDark ? 'bg-blue-950/40' : 'bg-blue-100/60'}`} />
              )}
            </div>
          </div>
        </section>

        {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            REPOSITORY SNAPSHOT — enough bottom padding to seal the fold
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
        <section className={`border-t border-b ${isDark ? 'border-white/[0.06] bg-[#0c1228]' : 'border-gray-200 bg-white'}`}>
          <div className="max-w-7xl mx-auto px-8 sm:px-12 lg:px-16 py-10 pb-16">
            <h2 className={`text-center text-base font-semibold tracking-wide mb-6 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              Repository Snapshot
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x
              divide-gray-200 dark:divide-white/[0.06]">

              {/* Card 1 — thesis count */}
              <div className="flex items-center gap-4 px-6 py-5">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-500/15' : 'bg-blue-50'}`}>
                  <BookOpen className={`w-5 h-5 ${isDark ? 'text-blue-300' : 'text-primary'}`} aria-hidden="true" />
                </div>
                <div>
                  <div className={`text-2xl font-bold leading-none ${isDark ? 'text-primary' : 'text-primary'}`}>
                    {thesisCountLabel}
                  </div>
                  <div className={`text-xs font-semibold mt-0.5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    Undergraduate Theses Indexed
                  </div>
                  <div className={`text-xs mt-0.5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    Approved and ready for semantic search
                  </div>
                </div>
              </div>

              {/* Card 2 — corpus coverage */}
              <div className="flex items-center gap-4 px-6 py-5">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-500/15' : 'bg-blue-50'}`}>
                  <GraduationCap className={`w-5 h-5 ${isDark ? 'text-blue-300' : 'text-primary'}`} aria-hidden="true" />
                </div>
                <div>
                  <div className={`text-2xl font-bold leading-none ${isDark ? 'text-primary' : 'text-primary'}`}>
                    2023 – 2025
                  </div>
                  <div className={`text-xs font-semibold mt-0.5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    Corpus Coverage
                  </div>
                  <div className={`text-xs mt-0.5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    Theses from SY 2023 to SY 2025
                  </div>
                </div>
              </div>

              {/* Card 3 — research domains */}
              <div className="flex items-center gap-4 px-6 py-5">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-500/15' : 'bg-blue-50'}`}>
                  <LayoutDashboard className={`w-5 h-5 ${isDark ? 'text-blue-300' : 'text-primary'}`} aria-hidden="true" />
                </div>
                <div>
                  <div className={`text-2xl font-bold leading-none ${isDark ? 'text-primary' : 'text-primary'}`}>
                    BSIS • BSIT • BSCS
                  </div>
                  <div className={`text-xs font-semibold mt-0.5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    Research Domains
                  </div>
                  <div className={`text-xs mt-0.5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    Computing programs covered
                  </div>
                </div>
              </div>

            </div>
          </div>
        </section>
      </main>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          FEATURE SHOWCASE — begins below first fold (scroll-reveal point)
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <section className={`px-5 sm:px-8 lg:px-14 pt-12 pb-12 border-t ${isDark ? 'bg-[#080d24] border-white/[0.06]' : 'bg-white border-gray-200'}`}>
        <div className="max-w-6xl mx-auto">
          <h2 className={`text-center text-base font-semibold tracking-wide mb-8 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
            Research tools built for CCS
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {FEATURES.map(({ icon: Icon, iconBg, iconColor, title, desc, to, linkLabel }) => (
              <div key={title} className="flex flex-col gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${isDark ? iconBg.dark : iconBg.light}`}>
                  <Icon className={`w-5 h-5 ${isDark ? iconColor.dark : iconColor.light}`} aria-hidden="true" />
                </div>
                <div>
                  <h3 className={`text-sm font-semibold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>{title}</h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{desc}</p>
                </div>
                <Link to={to}
                  className={`inline-flex items-center gap-1 text-xs font-semibold mt-auto ${isDark ? 'text-blue-300 hover:text-blue-200' : 'text-primary hover:opacity-80'}`}>
                  {linkLabel} <ArrowRight className="w-3 h-3" aria-hidden="true" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          TRENDING TOPICS PREVIEW + WHY THESYS+ — side by side
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <section className={`px-5 sm:px-8 lg:px-14 py-10 border-t ${isDark ? 'border-white/[0.06] bg-[#080d24]' : 'border-gray-100 bg-gray-50'}`}>
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-10">

          {/* LEFT — Trending Topics Preview */}
          <div>
            <h2 className={`text-base font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
              Trending Topics Preview
            </h2>
            <p className={`text-xs mb-5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              Aggregate topic clusters — labels and counts only.
            </p>

            <div className="space-y-2">
              {trendList.map((t) => {
                const chip = trendChip(t.trend);
                return (
                  <div key={t.topic}
                    className={`flex items-center justify-between gap-3 px-3 py-2 rounded-lg border ${
                      isDark ? 'bg-white/[0.03] border-white/[0.07]' : 'bg-white border-gray-200'
                    }`}>
                    <span className={`text-sm truncate ${isDark ? 'text-gray-200' : 'text-gray-800'}`} title={t.topic}>
                      {t.topic}
                    </span>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`text-xs font-semibold ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>{t.count}</span>
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border ${chip.cls}`}>
                        {chip.label}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            <Link to="/trend-analysis"
              className={`inline-flex items-center gap-1.5 mt-5 text-xs font-semibold ${isDark ? 'text-blue-300 hover:text-blue-200' : 'text-primary hover:opacity-80'}`}>
              View all trends <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
            </Link>
          </div>

          {/* RIGHT — Why THESYS+ (lighter stacked layout, no card containers) */}
          <div>
            <h2 className={`text-base font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
              Why THESYS+
            </h2>
            <p className={`text-xs mb-6 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              Built to support the CCS undergraduate thesis lifecycle.
            </p>

            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-500/15' : 'bg-blue-50'}`}>
                  <ShieldCheck className={`w-5 h-5 ${isDark ? 'text-blue-300' : 'text-primary'}`} aria-hidden="true" />
                </div>
                <div>
                  <h3 className={`text-sm font-semibold mb-0.5 ${isDark ? 'text-white' : 'text-gray-900'}`}>Prevent Topic Duplication</h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Validate thesis titles early to avoid duplication and ensure research originality.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-500/15' : 'bg-blue-50'}`}>
                  <Search className={`w-5 h-5 ${isDark ? 'text-blue-300' : 'text-primary'}`} aria-hidden="true" />
                </div>
                <div>
                  <h3 className={`text-sm font-semibold mb-0.5 ${isDark ? 'text-white' : 'text-gray-900'}`}>Improve Discoverability</h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Make completed CCS theses findable by meaning, not just by exact keywords.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'}`}>
                  <TrendingUp className={`w-5 h-5 ${isDark ? 'text-emerald-300' : 'text-emerald-600'}`} aria-hidden="true" />
                </div>
                <div>
                  <h3 className={`text-sm font-semibold mb-0.5 ${isDark ? 'text-white' : 'text-gray-900'}`}>Reveal Research Trends</h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Identify saturated and emerging research areas to guide future thesis topics.
                  </p>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          FOOTER — dark band with institutional links
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <footer className={`border-t ${isDark ? 'border-white/[0.06] bg-[#060b1e]' : 'border-gray-800 bg-[#0f172a]'}`}>
        <div className="max-w-6xl mx-auto px-5 sm:px-8 lg:px-14 py-6">
          {/* Desktop: 4-column flex row | Mobile: stacked */}
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6 sm:gap-4">

            {/* Col 1 — logo + institution */}
            <div className="flex flex-col gap-1 min-w-0">
              <ThesysLogo variant="wordmark" size={26} isDark={true} />
              <p className="text-xs text-gray-300 mt-1">Pampanga State University</p>
              <p className="text-xs text-gray-300">College of Computing Studies</p>
              <p className="text-xs text-gray-400 mt-1">© 2026 THESYS+. All rights reserved.</p>
            </div>

            {/* Col 2 — page links */}
            <nav aria-label="Footer navigation">
              <p className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">Resources</p>
              <ul className="flex flex-col gap-1.5">
                {[
                  { label: 'About',   onClick: () => setLegalModal('about') },
                  { label: 'Privacy', onClick: () => setLegalModal('privacy') },
                  { label: 'Terms',   onClick: () => setLegalModal('terms') },
                  { label: 'Help',    onClick: () => setLegalModal('help') },
                ].map(({ label, onClick }) => (
                  <li key={label}>
                    <button type="button" onClick={onClick}
                      className="text-xs text-gray-300 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-400">
                      {label}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>

            {/* Col 3 — institutional links (NEW) */}
            <nav aria-label="Institutional links">
              <p className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">Institutional Links</p>
              <ul className="flex flex-col gap-1.5">
                <li>
                  <a
                    href="https://pampangastateu.edu.ph/"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Visit the Pampanga State University official website (opens in new tab)"
                    className="text-xs text-gray-300 hover:text-blue-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-400"
                  >
                    Pampanga State University
                  </a>
                </li>
                <li>
                  <a
                    href="https://web.facebook.com/dhvsu.ccssc"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Visit the CCS Facebook page (opens in new tab)"
                    className="text-xs text-gray-300 hover:text-blue-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-400"
                  >
                    CCS Facebook Page
                  </a>
                </li>
              </ul>
            </nav>

            {/* Col 4 — social icons (only verified destinations) */}
            <div className="flex items-center gap-3 sm:self-end">
              <a
                href="https://web.facebook.com/dhvsu.ccssc"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Visit CCS Facebook page (opens in new tab)"
                className="w-8 h-8 rounded-full bg-white/[0.06] flex items-center justify-center hover:bg-white/[0.12] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-400"
              >
                <svg className="w-4 h-4 text-gray-400" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/>
                </svg>
              </a>
            </div>

          </div>
        </div>
      </footer>

      {/* Legal modal */}
      <LegalModal
        isOpen={legalModal !== null}
        onClose={() => setLegalModal(null)}
        type={legalModal}
        isDark={isDark}
      />
    </div>
  );
}
