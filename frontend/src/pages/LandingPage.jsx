/**
 * LandingPage — THESYS+ public landing page.
 *
 * Layout:
 *   Sticky Navbar · Hero (full-bleed CCS building photo) ·
 *   Repository snapshot · [Research tools + Research subjects] side-by-side ·
 *   Dark Footer. Only the hero animates.
 *
 * Privacy: logged-out users see aggregate-only data. No thesis titles,
 * abstracts, authors, or documents are exposed.
 *
 * Hero: art-directed building photo — landscape crop at lg+ (1024px),
 * portrait crop below. Mobile (< lg) is theme-invariant: dark scrim,
 * light text, in both light and dark mode (see HERO_SCRIM_MOBILE).
 * Desktop (lg+) inverts in light mode — white scrim, near-black text,
 * brand-blue accent (see HERO_SCRIM_DESKTOP_LIGHT and the heroEyebrowCls
 * etc. constants) — so light/dark mode are visually distinct at desktop
 * widths while mobile stays untouched. Falls back to a solid dark
 * surface if the asset fails to load, since the mobile-first light text
 * doesn't adapt to a light background.
 */

import { Link, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { LazyMotion, domAnimation, m } from 'framer-motion';
import {
  Sun, Moon, Search, ShieldCheck, TrendingUp, BarChart3, ArrowRight,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../hooks/useAuth';
import client from '../api/client';
import { AvatarDropdown, NAV_BAR_CLASS, NAV_LINK_ACTIVE, NAV_LINK_BASE, NAV_LINK_IDLE, NAV_LINK_SOON } from '../components/layout/AppNavbar';
import { useUploadModal } from '../hooks/useUploadModal';
import LegalModal from '../components/legal/LegalModal';
import ThesysLogo from '../components/brand/ThesysLogo';
import useFocusTrap from '../hooks/useFocusTrap';
import usePresence from '../hooks/usePresence';
import { useMotionVariants } from '../lib/motion';

const CORE_NAV = [
  { label: 'Home',             to: '/',                 implemented: true },
  { label: 'Repository',       to: '/repository',       implemented: true },
  { label: 'Title Similarity', to: '/title-similarity', implemented: true },
  { label: 'Trend Analysis',   to: '/trend-analysis',   implemented: true },
  { label: 'Analytics',        to: '/analytics',        implemented: true },
];

// Hero scrim — soft multi-stop gradients. Many closely-spaced stops so there
// is no visible seam (an earlier hard-stop version produced a hard vertical
// edge across the photo).
//
// Desktop: dense on the left where the text sits, fully clear by 88% so the
// entrance arch stays sunlit. Angled 100deg so it doesn't read as a band.
// Mobile: dense at the bottom, because mobile text is bottom-anchored.
const HERO_SCRIM_DESKTOP =
  'linear-gradient(100deg, rgba(2,6,23,0.92) 0%, rgba(2,6,23,0.80) 28%, rgba(2,6,23,0.58) 52%, rgba(2,6,23,0.15) 76%, transparent 90%)';

const HERO_SCRIM_MOBILE =
  'linear-gradient(0deg, rgba(2,6,23,0.94) 0%, rgba(2,6,23,0.86) 32%, rgba(2,6,23,0.70) 60%, rgba(2,6,23,0.28) 80%, transparent 94%)';

// Light-mode desktop scrim — white wash mirroring the dark gradient's falloff
// shape. Holds ~0.62 alpha out to 58% so the near-black eyebrow/paragraph and
// the #1e40af accent clear WCAG AA over the photo's dark window bands, then
// clears to 0.12 by 74% so the entrance arch stays visible.
// Mobile has no light variant — the mobile scrim stays dark in both themes.
const HERO_SCRIM_DESKTOP_LIGHT =
  'linear-gradient(100deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.88) 32%, rgba(255,255,255,0.62) 58%, rgba(255,255,255,0.12) 74%, transparent 88%)';

// One container for every band below the hero, so all left edges line up.
const CONTAINER = 'max-w-6xl mx-auto px-5 sm:px-8 lg:px-14';

// Tool list — titles match the nav labels exactly, and each links to its page.
const FEATURES = [
  {
    icon: Search,
    title: 'Repository',
    desc:  'Find related theses by meaning, not just matching keywords, using SBERT sentence embeddings.',
    to:    '/repository',
  },
  {
    icon: ShieldCheck,
    title: 'Title Similarity',
    desc:  'See how close your proposed title is to existing theses before you commit to a topic.',
    to:    '/title-similarity',
  },
  {
    icon: TrendingUp,
    title: 'Trend Analysis',
    desc:  'See which research subjects are saturated, emerging, or underexplored, based on how many theses each has.',
    to:    '/trend-analysis?view=subjects',
  },
  {
    icon: BarChart3,
    title: 'Analytics',
    desc:  'Thesis counts by program and by year, plus the most common keywords.',
    to:    '/analytics',
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
  const [reviewedSubjectsEnabled, setReviewedSubjectsEnabled] = useState(false);
  const [legalModal, setLegalModal]     = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [heroImgFailed, setHeroImgFailed] = useState(false);
  const isDark = theme === 'dark';
  const drawerRef = useFocusTrap(mobileMenuOpen);
  const [menuMounted, menuClosing] = usePresence(mobileMenuOpen, 200);
  const { fadeUp, staggerContainer } = useMotionVariants();

  // ── Hero text + chrome classes ─────────────────────────────────────────
  // Mobile (< lg) keeps light-on-dark in BOTH themes because the mobile scrim
  // stays dark. Only desktop light mode inverts, hence the lg: scoping.
  // Dark mode matches the mobile scrim (light text). Light mode inverts to ink
  // on the white desktop wash, so those overrides are `lg:` scoped.
  const heroEyebrowCls   = 'text-slate-300 lg:text-ink dark:lg:text-slate-300';
  const heroDotCls       = 'text-slate-500 lg:text-body dark:lg:text-slate-500';
  const heroHeadingCls   = 'text-white lg:text-ink dark:lg:text-white';
  const heroAccentCls    = 'text-blue-400 lg:text-primary dark:text-primary';
  const heroParagraphCls = 'text-slate-200 lg:text-ink dark:lg:text-slate-200';

  // Light-only desktop overrides sit on top of dark base classes, so these four
  // stay theme-conditional: dark mode adds nothing.
  const heroInputWrapCls  = isDark ? '' : 'lg:bg-white lg:border-gray-300 lg:hover:border-gray-400 lg:focus-within:border-blue-400 lg:focus-within:ring-2 lg:focus-within:ring-blue-100';
  const heroInputIconCls  = isDark ? '' : 'lg:text-muted';
  const heroInputTextCls  = isDark ? '' : 'lg:text-gray-700 lg:placeholder-gray-500';
  const heroOutlineBtnCls = isDark ? '' : 'lg:border-gray-300 lg:text-ink lg:hover:bg-gray-50 lg:hover:border-gray-400';

  // Escape closes mobile menu
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape' && mobileMenuOpen) setMobileMenuOpen(false); }
    if (mobileMenuOpen) document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [mobileMenuOpen]);

  // Public thesis count — aggregate only, no auth required
  useEffect(() => {
    let cancelled = false;
    client.get('/theses/public-stats/')
      .then((res) => {
        if (!cancelled) {
          if (typeof res.data.indexed_theses_count === 'number') setThesisCount(res.data.indexed_theses_count);
          setReviewedSubjectsEnabled(Boolean(res.data.reviewed_subjects_enabled));
          if (res.data.reviewed_subjects_enabled) setTopics(res.data.reviewed_subject_preview || []);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Trending topics — auth-gated; fallback shown to logged-out users
  useEffect(() => {
    if (isInitializing || !isAuthenticated) return;
    let cancelled = false;
    client.get('/theses/subject-trends/')
      .then((res) => {
        if (cancelled || res.data?.main_view_enabled) return null;
        return client.get('/theses/topic-trends/');
      })
      .then((res) => {
        if (!cancelled && res?.data?.clusters)
          setTopics(res.data.clusters.slice(0, 6).map((c) => ({ topic: c.topic, count: c.thesis_count, trend: c.trend })));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [isAuthenticated, isInitializing]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    const q = searchQuery.trim();
    navigate(q ? `/repository?q=${encodeURIComponent(q)}` : '/repository');
  };

  // ── Trend chip helper ──────────────────────────────────────────────
  const trendChip = (trend) => {
    const map = {
      SATURATED:     { label: 'Saturated',     cls: 'bg-danger-bg text-danger-text border-danger-border'     },
      EMERGING:      { label: 'Emerging',      cls: 'bg-warning-bg text-warning-text border-warning-border'  },
      UNDEREXPLORED: { label: 'Underexplored', cls: 'bg-success-bg text-success-text border-success-border' },
    };
    return map[trend] || map.EMERGING;
  };

  const trendList = topics?.slice(0, 6) || [];

  return (
    <div className="min-h-screen flex flex-col bg-canvas transition-colors duration-300">

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          NAVBAR — sticky, auth-aware, matches app branding
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <nav className={NAV_BAR_CLASS}>
        {/* Mobile row */}
        <div className="flex items-center justify-between lg:hidden">
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setMobileMenuOpen(true)} aria-label="Open navigation menu"
              className={`w-9 h-9 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary text-muted hover:text-ink hover:bg-icon-btn-hover`}>
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
              </svg>
            </button>
            <Link to="/" className="flex items-center gap-2 select-none">
              <ThesysLogo variant="wordmark" size={28} />
            </Link>
          </div>
          <div className="flex items-center gap-2">
            {!isInitializing && isAuthenticated && (
              <AvatarDropdown user={user} onSignOut={async () => { await signOut(); navigate('/'); }} />
            )}
            {!isInitializing && !isAuthenticated && (
              <Link to="/sign-in" className="px-3 py-1.5 rounded-lg bg-primary-solid text-white text-sm font-semibold hover:bg-primary-solid-hover transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                Sign In
              </Link>
            )}
            <button type="button" onClick={toggleTheme} aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className={`w-9 h-9 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary text-muted hover:text-ink hover:bg-icon-btn-hover`}>
              {isDark ? <Sun className="h-5 w-5 text-primary" /> : <Moon className="h-5 w-5 text-primary" />}
            </button>
          </div>
        </div>

        {/* Desktop row */}
        <div className="hidden lg:grid grid-cols-[1fr_auto_1fr] items-center">
          <Link to="/" className="flex items-center gap-2 select-none">
            <ThesysLogo variant="wordmark" size={28} />
          </Link>
          <ul className="flex items-center gap-1">
            {CORE_NAV.map(({ label, to, implemented }) => (
              <li key={label}>
                <Link to={to} onClick={implemented ? undefined : (e) => e.preventDefault()}
                  aria-disabled={!implemented}
                  aria-current={to === '/' ? 'page' : undefined}
                  className={`${NAV_LINK_BASE} ${!implemented ? NAV_LINK_SOON : to === '/' ? NAV_LINK_ACTIVE : NAV_LINK_IDLE}`}>
                  {label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2 justify-end">
            {!isInitializing && isAuthenticated && (
              <>
                <button type="button" onClick={openUpload} className="px-3 py-1.5 rounded-lg bg-primary-solid text-white text-sm font-semibold hover:bg-primary-solid-hover transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                  Upload Thesis
                </button>
                <AvatarDropdown user={user} onSignOut={async () => { await signOut(); navigate('/'); }} />
              </>
            )}
            {!isInitializing && !isAuthenticated && (
              <Link to="/sign-in" className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary-solid text-white text-sm font-semibold hover:bg-primary-solid-hover transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                Sign In
              </Link>
            )}
            <button type="button" onClick={toggleTheme} aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className={`w-9 h-9 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary text-muted hover:text-ink hover:bg-icon-btn-hover`}>
              {isDark ? <Sun className="h-5 w-5 text-primary" /> : <Moon className="h-5 w-5 text-primary" />}
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile drawer */}
      {menuMounted && createPortal(
        <div data-closing={menuClosing || undefined} className="fixed inset-0 z-[9999] lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation menu">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm thesys-overlay-enter" onClick={() => setMobileMenuOpen(false)} aria-hidden="true" />
          <div ref={drawerRef} className="absolute top-0 left-0 bottom-0 w-72 max-w-[85vw] shadow-2xl thesys-drawer-enter bg-surface-elevated border-r border-border-default">
            <div className={`flex items-center justify-between px-5 py-4 border-b border-border-default`}>
              <ThesysLogo variant="wordmark" size={28} />
              <button type="button" onClick={() => setMobileMenuOpen(false)} aria-label="Close navigation menu"
                className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors text-muted hover:text-ink hover:bg-icon-btn-hover`}>
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
                      aria-current={to === '/' ? 'page' : undefined}
                      className={`block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                        !implemented
                          ? 'text-subtle cursor-default'
                          : to === '/'
                            ? NAV_LINK_ACTIVE
                            : 'text-body hover:bg-nav-hover-bg hover:text-ink'
                      }`}>
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
              {!isInitializing && isAuthenticated
                ? <button type="button" onClick={() => { setMobileMenuOpen(false); openUpload(); }} className="mt-4 block w-full px-4 py-2.5 rounded-lg bg-primary-solid text-white text-sm font-semibold text-center hover:bg-primary-solid-hover transition-colors">Upload Thesis</button>
                : <Link to="/sign-in" onClick={() => setMobileMenuOpen(false)} className="mt-4 block w-full px-4 py-2.5 rounded-lg bg-primary-solid text-white text-sm font-semibold text-center hover:bg-primary-solid-hover transition-colors">Sign In</Link>
              }
            </nav>
          </div>
        </div>,
        document.body
      )}

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          HERO — full-bleed, art-directed building photo (landscape crop
          at lg+, portrait crop below). Mobile (< lg) keeps a dark scrim
          with light text in BOTH themes — unaffected by this change.
          Desktop (lg+) inverts in light mode: white scrim, near-black
          text, brand-blue accent, so light and dark mode read as visibly
          distinct at desktop widths. Every light-mode desktop override
          is `lg:`-scoped (see heroEyebrowCls etc. above) so mobile light
          mode never inherits a dark-on-dark override meant for desktop.
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <main>
        <LazyMotion features={domAnimation}>
        <section className="relative w-full min-h-[100svh] flex items-end lg:items-center overflow-hidden">
          {/* Background photo — decorative, never animated (avoids layout jank).
              Art-directed crops: landscape (16:9, entrance right-of-center)
              at lg+ (1024px, matches Tailwind's lg — kept in sync with the
              scrim/text-anchor breakpoint below), portrait (9:16, entrance
              centered) below that. WebP first, JPEG fallback per crop. */}
          {heroImgFailed ? (
            // Fallback if the asset fails to load — solid dark surface, since
            // the scrim + hardcoded light text depend on a dark base
            // regardless of theme (a light fallback would put white text on
            // a light background).
            <div className="absolute inset-0 w-full h-full bg-slate-950 z-0" aria-hidden="true" />
          ) : (
            <picture>
              <source media="(min-width: 1024px)" type="image/webp" srcSet="/ccsdesktop.webp" />
              <source media="(min-width: 1024px)" type="image/jpeg" srcSet="/ccsdesktop.jpeg" />
              <source type="image/webp" srcSet="/ccsmobile.webp" />
              <img
                src="/ccsmobile.jpeg"
                alt=""
                className="absolute inset-0 w-full h-full object-cover object-[center_40%] z-0"
                loading="eager"
                fetchPriority="high"
                draggable="false"
                aria-hidden="true"
                onError={() => setHeroImgFailed(true)}
              />
            </picture>
          )}

          {/* Scrim — soft multi-stop gradients (see HERO_SCRIM_* above), one
              shape per breakpoint rather than per theme: dense at the
              bottom on mobile (text is bottom-anchored there), dense on
              the left at lg+ (text is left-aligned and vertically
              centered there). Two plain divs instead of Tailwind
              arbitrary values — keeps the gradient strings readable and
              avoids the arbitrary-value parser tripping on nested commas. */}
          <div
            className="absolute inset-0 z-0 lg:hidden"
            style={{ backgroundImage: HERO_SCRIM_MOBILE }}
            aria-hidden="true"
          />
          <div
            className="absolute inset-0 z-0 hidden lg:block"
            style={{ backgroundImage: isDark ? HERO_SCRIM_DESKTOP : HERO_SCRIM_DESKTOP_LIGHT }}
            aria-hidden="true"
          />

          {/* Text container */}
          <m.div
            className="relative z-10 max-w-2xl lg:max-w-none px-8 sm:px-12 lg:px-16 xl:px-20 pb-20 pt-16 lg:py-16"
            initial="hidden"
            animate="visible"
            variants={staggerContainer}
          >
            {/* Breadcrumb eyebrow */}
            <m.p variants={fadeUp} className={`text-xs font-medium mb-4 ${heroEyebrowCls}`}>
              Pampanga State University
              <span className={`mx-1.5 ${heroDotCls}`}>•</span>
              College of Computing Studies
            </m.p>

            {/* Headline — "undergraduate research" emphasized in the blue accent */}
            <m.h1 variants={fadeUp} className={`font-bold tracking-tight mb-4 leading-tight ${heroHeadingCls}`}
              style={{ fontSize: 'clamp(1.75rem, 2.8vw, 3rem)' }}>
              {/* Forced desktop breaks keep the same 3-line shape on every monitor
                  (the font scales with the viewport; a fixed box width didn't). */}
              Explore, validate, and discover<br className="hidden lg:inline" />{' '}
              <span className={`font-extrabold ${heroAccentCls}`}>undergraduate research</span><br className="hidden lg:inline" />{' '}
              within PampangaStateU CCS.
            </m.h1>

            {/* Supporting text */}
            <m.p variants={fadeUp} className={`text-sm sm:text-base leading-relaxed mb-7 max-w-lg ${heroParagraphCls}`}>
              Search previous studies by meaning, check title similarity,
              and compare research areas by thesis count.
            </m.p>

            {/* Unified search unit — kept as-is; handles its own states well. */}
            <m.form variants={fadeUp} id="hero-search-form" onSubmit={handleSearchSubmit}
              className="mb-4 max-w-xl flex flex-wrap sm:flex-nowrap items-stretch gap-2">
              <div className={`flex items-center rounded-lg px-4 py-2.5 border transition-[border-color,background-color] duration-200 flex-1 min-w-0 bg-white/[0.07] border-white/15 hover:border-white/25 focus-within:border-blue-500/60 focus-within:bg-white/[0.09] ${heroInputWrapCls}`}>
                <Search className={`w-4 h-4 mr-3 flex-shrink-0 text-gray-400 ${heroInputIconCls}`} aria-hidden="true" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search titles, topics, or authors…"
                  className={`flex-1 bg-transparent text-sm outline-none min-w-0 text-gray-100 placeholder-gray-500 ${heroInputTextCls}`}
                  aria-label="Search titles, topics, or authors"
                />
              </div>
              <button type="submit"
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-primary-solid text-white text-sm font-semibold whitespace-nowrap w-full sm:w-auto flex-shrink-0 hover:bg-primary-solid-hover transition-[color,background-color,border-color,box-shadow,transform] duration-150 ease-out hover:shadow-md active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                <Search className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                Search Theses
              </button>
            </m.form>

            {/* Secondary CTA */}
            <m.div variants={fadeUp} className="flex flex-wrap gap-3">
              <Link to="/title-similarity"
                className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold border transition-[color,background-color,border-color,box-shadow,transform] duration-150 ease-out active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary border-white/20 text-gray-100 hover:bg-white/[0.08] hover:border-white/30 ${heroOutlineBtnCls}`}>
                <ShieldCheck className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                Check Title Similarity
              </Link>
            </m.div>
          </m.div>
        </section>
        </LazyMotion>

        {/* Repository snapshot — the values are the focus, each with a short
            label under it. The count comes from the public stats endpoint;
            the rest are the corpus bounds. Aggregate only for logged-out
            visitors. flex-col-reverse keeps dt before dd in the markup while
            the value shows first. */}
        <section className="bg-surface-elevated border-b border-border-default">
          <div className={`${CONTAINER} py-10`}>
            <h2 className="text-center text-base font-semibold tracking-wide text-body">
              Repository Snapshot
            </h2>
            <dl className="mt-6 grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-border-default">
              {[
                { label: 'Undergraduate Theses Indexed', value: thesisCount ?? '—' },
                { label: 'Corpus Coverage',              value: '2021–2025' },
                { label: 'Programs',                     value: 'BSIS • BSIT • BSCS' },
              ].map(({ label, value }) => (
                <div key={label} className="flex flex-col-reverse items-center gap-1.5 px-6 py-5 text-center">
                  <dt className="text-sm font-semibold text-body">{label}</dt>
                  <dd className="text-3xl font-bold leading-none tracking-tight whitespace-nowrap tabular-nums text-primary">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* Research tools + research subjects. The subject list is the one
            piece of live evidence a logged-out visitor can see. */}
        <section className="bg-canvas">
          <div className={`${CONTAINER} py-14 grid gap-12 lg:grid-cols-2 lg:gap-16`}>

            <div>
              <h2 className="text-lg font-semibold text-ink">Research tools</h2>
              <p className="mt-1 text-[15px] text-body">
                For the CCS undergraduate thesis lifecycle, from choosing a topic to finding related work.
              </p>
              <ul className="mt-6 divide-y divide-border-default border-y border-border-default">
                {FEATURES.map(({ icon: Icon, title, desc, to }) => (
                  <li key={to}>
                    <Link to={to}
                      className="group flex gap-4 py-4 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                      <Icon className="mt-0.5 w-5 h-5 flex-shrink-0 text-primary" aria-hidden="true" />
                      <span className="min-w-0">
                        <span className="flex items-center gap-1 text-[15px] font-semibold text-ink group-hover:text-primary transition-colors">
                          {title}
                          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" aria-hidden="true" />
                        </span>
                        <span className="mt-1 block text-[15px] leading-relaxed text-body">{desc}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-ink">
                {reviewedSubjectsEnabled ? 'Research subjects' : 'Topic groups'}
              </h2>
              <p className="mt-1 text-[15px] text-body">
                {reviewedSubjectsEnabled
                  ? 'Confirmed primary subjects among approved theses. Labels compare relative counts, not growth over time.'
                  : 'Groups of theses with similar meaning. Labels compare relative counts, not growth over time.'}
              </p>
              <ul className="mt-6 divide-y divide-border-default border-y border-border-default">
                {trendList.length === 0 && (
                  <li className="py-4 text-[15px] text-body">
                    {isAuthenticated ? 'Current topic results are unavailable.' : 'Sign in to explore current topic groups.'}
                  </li>
                )}
                {trendList.map((t) => {
                  const chip = trendChip(t.trend);
                  return (
                    <li key={t.topic} className="flex items-center justify-between gap-3 py-3">
                      <span className="text-[15px] truncate text-ink" title={t.topic}>{t.topic}</span>
                      <span className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-sm font-semibold tabular-nums text-muted">{t.count}</span>
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold border ${chip.cls}`}>
                          {chip.label}
                        </span>
                      </span>
                    </li>
                  );
                })}
              </ul>
              <Link to={reviewedSubjectsEnabled ? '/trend-analysis?view=subjects' : '/trend-analysis'}
                className="inline-flex items-center gap-1.5 mt-5 text-sm font-semibold text-primary hover:underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm">
                View all trends <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </Link>
            </div>

          </div>
        </section>
      </main>

      {/* Footer — dark band with institutional links */}
      <footer className={`border-t ${isDark ? 'border-white/[0.06] bg-[#060b1e]' : 'border-gray-800 bg-[#0f172a]'}`}>
        <div className={`${CONTAINER} py-6`}>
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6 sm:gap-4">

            <div className="flex flex-col gap-1 min-w-0">
              <ThesysLogo variant="wordmark" size={26} onDark />
              <p className="text-xs text-gray-300 mt-1">Pampanga State University</p>
              <p className="text-xs text-gray-300">College of Computing Studies</p>
              <p className="text-xs text-gray-400 mt-1">© 2026 THESYS+. All rights reserved.</p>
            </div>

            {/* Resources — 2×2: About / Terms on the first row, Privacy / Help on the second */}
            <nav aria-label="Footer navigation">
              <p className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">Resources</p>
              <ul className="grid w-fit grid-cols-[auto_auto] gap-x-10 gap-y-1.5">
                {[
                  { label: 'About',   onClick: () => setLegalModal('about') },
                  { label: 'Terms',   onClick: () => setLegalModal('terms') },
                  { label: 'Privacy', onClick: () => setLegalModal('privacy') },
                  { label: 'Help',    onClick: () => setLegalModal('help') },
                ].map(({ label, onClick }) => (
                  <li key={label}>
                    <button type="button" onClick={onClick}
                      className="text-xs text-gray-300 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary">
                      {label}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>

            <nav aria-label="Institutional links">
              <p className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">Institutional Links</p>
              <ul className="flex flex-col gap-1.5">
                <li>
                  <a
                    href="https://pampangastateu.edu.ph/"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Visit the Pampanga State University official website (opens in new tab)"
                    className="text-xs text-gray-300 hover:text-blue-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
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
                    className="text-xs text-gray-300 hover:text-blue-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                  >
                    CCS Facebook Page
                  </a>
                </li>
              </ul>
            </nav>

          </div>
        </div>
      </footer>

      {/* Legal modal */}
      <LegalModal
        isOpen={legalModal !== null}
        onClose={() => setLegalModal(null)}
        type={legalModal}
      />
    </div>
  );
}
