/**
 * LandingPage — THESYS+ public landing page.
 *
 * Layout:
 *   Sticky Navbar · Hero (full-bleed CCS building photo dark island) ·
 *   Repository Snapshot · Feature Showcase (4-col) ·
 *   [Trending Topics Preview + Why THESYS+] side-by-side · Dark Footer
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
  Sun, Moon, Search, ShieldCheck, TrendingUp, BarChart3,
  ArrowRight, BookOpen, GraduationCap, LayoutDashboard,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../hooks/useAuth';
import client from '../api/client';
import { AvatarDropdown, NAV_BAR_CLASS, NAV_LINK_BASE, NAV_LINK_IDLE, NAV_LINK_SOON } from '../components/layout/AppNavbar';
import { useUploadModal } from '../hooks/useUploadModal';
import LegalModal from '../components/legal/LegalModal';
import ThesysLogo from '../components/brand/ThesysLogo';
import useFocusTrap from '../hooks/useFocusTrap';
import AnimatedCounter from '../components/ui/AnimatedCounter';
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

// Feature cards — "Learn more" only links to pages that actually exist.
const FEATURES = [
  {
    icon: Search,
    iconBg: 'bg-info-bg', iconColor: 'text-info-text',
    title: 'Semantic Search',
    desc:  'Find relevant theses by meaning, not just keywords using SBERT embeddings.',
    to:    '/repository',
    linkLabel: 'Open Repository',
  },
  {
    icon: ShieldCheck,
    iconBg: 'bg-info-bg', iconColor: 'text-info-text',
    title: 'Title Similarity Validation',
    desc:  'Check the originality of your proposed title using SBERT and cosine similarity.',
    to:    '/title-similarity',
    linkLabel: 'Validate a title',
  },
  {
    icon: TrendingUp,
    iconBg: 'bg-success-bg', iconColor: 'text-success-text',
    title: 'Trend Analysis',
    desc:  'Compare research areas by thesis count, with reviewed subjects and exploratory text clusters clearly identified.',
    to:    '/trend-analysis',
    linkLabel: 'View trends',
  },
  {
    icon: BarChart3,
    iconBg: 'bg-warning-bg', iconColor: 'text-warning-text',
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
  const [reviewedSubjectsEnabled, setReviewedSubjectsEnabled] = useState(false);
  const [legalModal, setLegalModal]     = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [heroImgFailed, setHeroImgFailed] = useState(false);
  const isDark = theme === 'dark';
  const drawerRef = useFocusTrap(mobileMenuOpen);
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

  const trendList = topics?.slice(0, 4) || [];

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
                  className={`${NAV_LINK_BASE} ${implemented ? NAV_LINK_IDLE : NAV_LINK_SOON}`}>
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
      {mobileMenuOpen && createPortal(
        <div className="fixed inset-0 z-[9999] lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation menu">
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
                      className={`block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                        !implemented
                          ? 'text-subtle cursor-default'
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
              Search previous studies by meaning, check title originality,
              and compare research areas by thesis count.
            </m.p>

            {/* Unified search unit — kept as-is; handles its own states well. */}
            <m.form variants={fadeUp} id="hero-search-form" onSubmit={handleSearchSubmit}
              className="mb-4 max-w-xl flex flex-wrap sm:flex-nowrap items-stretch gap-2">
              <div className={`flex items-center rounded-lg px-4 py-2.5 border transition-all duration-200 flex-1 min-w-0 bg-white/[0.07] border-white/15 hover:border-white/25 focus-within:border-blue-500/60 focus-within:bg-white/[0.09] ${heroInputWrapCls}`}>
                <Search className={`w-4 h-4 mr-3 flex-shrink-0 text-gray-400 ${heroInputIconCls}`} aria-hidden="true" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search topics or authors..."
                  className={`flex-1 bg-transparent text-sm outline-none min-w-0 text-gray-100 placeholder-gray-500 ${heroInputTextCls}`}
                  aria-label="Search thesis topics, keywords, or authors"
                />
              </div>
              <button type="submit"
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-primary-solid text-white text-sm font-semibold whitespace-nowrap w-full sm:w-auto flex-shrink-0 hover:bg-primary-solid-hover transition-all duration-150 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                <Search className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                Search Semantically
              </button>
            </m.form>

            {/* Secondary CTA */}
            <m.div variants={fadeUp} className="flex flex-wrap gap-3">
              <Link to="/title-similarity"
                className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold border transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary border-white/20 text-gray-100 hover:bg-white/[0.08] hover:border-white/30 ${heroOutlineBtnCls}`}>
                <ShieldCheck className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                Check Title Similarity
              </Link>
            </m.div>
          </m.div>
        </section>
        </LazyMotion>

        {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            REPOSITORY SNAPSHOT — enough bottom padding to seal the fold
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
        <section className="bg-surface-elevated">
          <div className="max-w-7xl mx-auto px-8 sm:px-12 lg:px-16 py-10 pb-16">
            <h2 className={`text-center text-base font-semibold tracking-wide mb-6 text-body`}>
              Repository Snapshot
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x
              divide-gray-200 dark:divide-white/[0.06]">

              {/* Card 1 — thesis count */}
              <div className="flex items-center gap-4 px-6 py-5">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-info-bg`}>
                  <BookOpen className={`w-5 h-5 text-primary`} aria-hidden="true" />
                </div>
                <div>
                  <div className={`text-2xl font-bold leading-none text-primary`}>
                    <AnimatedCounter value={thesisCount} />
                  </div>
                  <div className={`text-xs font-semibold mt-0.5 text-body`}>
                    Undergraduate Theses Indexed
                  </div>
                  <div className={`text-xs mt-0.5 text-muted`}>
                    Approved and ready for semantic search
                  </div>
                </div>
              </div>

              {/* Card 2 — corpus coverage */}
              <div className="flex items-center gap-4 px-6 py-5">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-info-bg`}>
                  <GraduationCap className={`w-5 h-5 text-primary`} aria-hidden="true" />
                </div>
                <div>
                  <div className={`text-2xl font-bold leading-none text-primary`}>
                    2021 – 2025
                  </div>
                  <div className={`text-xs font-semibold mt-0.5 text-body`}>
                    Corpus Coverage
                  </div>
                  <div className={`text-xs mt-0.5 text-muted`}>
                    Theses from SY 2021 to SY 2025
                  </div>
                </div>
              </div>

              {/* Card 3 — research domains */}
              <div className="flex items-center gap-4 px-6 py-5">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-info-bg`}>
                  <LayoutDashboard className={`w-5 h-5 text-primary`} aria-hidden="true" />
                </div>
                <div>
                  <div className={`text-2xl font-bold leading-none text-primary`}>
                    BSIS • BSIT • BSCS
                  </div>
                  <div className={`text-xs font-semibold mt-0.5 text-body`}>
                    Research Domains
                  </div>
                  <div className={`text-xs mt-0.5 text-muted`}>
                    Computing programs covered
                  </div>
                </div>
              </div>

            </div>
          </div>
        </section>
      </main>

      <LazyMotion features={domAnimation}>
      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          FEATURE SHOWCASE — begins below first fold (scroll-reveal point)
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <section className={`px-5 sm:px-8 lg:px-14 pt-12 pb-12 border-t bg-canvas border-border-default`}>
        <div className="max-w-6xl mx-auto">
          <h2 className={`text-center text-base font-semibold tracking-wide mb-8 text-body`}>
            Research tools built for CCS
          </h2>
          <m.div
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-80px' }}
            variants={staggerContainer}
          >
            {FEATURES.map(({ icon: Icon, iconBg, iconColor, title, desc, to, linkLabel }) => (
              <m.div key={title} variants={fadeUp} className="flex flex-col gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${iconBg}`}>
                  <Icon className={`w-5 h-5 ${iconColor}`} aria-hidden="true" />
                </div>
                <div>
                  <h3 className={`text-sm font-semibold mb-1 text-ink`}>{title}</h3>
                  <p className={`text-xs leading-relaxed text-body`}>{desc}</p>
                </div>
                <Link to={to}
                  className={`inline-flex items-center gap-1 text-xs font-semibold mt-auto text-primary hover:opacity-80`}>
                  {linkLabel} <ArrowRight className="w-3 h-3" aria-hidden="true" />
                </Link>
              </m.div>
            ))}
          </m.div>
        </div>
      </section>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          TRENDING TOPICS PREVIEW + WHY THESYS+ — side by side
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <section className={`px-5 sm:px-8 lg:px-14 py-10 border-t border-border-subtle bg-canvas`}>
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-10">

          {/* LEFT — Trending Topics Preview */}
          <div>
            <h2 className={`text-base font-bold mb-1 text-ink`}>
              {reviewedSubjectsEnabled ? 'Reviewed subjects preview' : 'Exploratory text clusters preview'}
            </h2>
            <p className={`text-xs mb-5 text-muted`}>
              {reviewedSubjectsEnabled
                ? 'Confirmed primary subjects among approved theses. Labels compare relative counts, not growth over time.'
                : 'Groups of theses with similar meaning. Labels compare relative counts, not growth over time.'}
            </p>

            <m.div
              className="divide-y border-y divide-border-default border-border-default"
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-80px' }}
              variants={staggerContainer}
            >
              {trendList.length === 0 && (
                <p className={`text-sm text-body`}>
                  {isAuthenticated ? 'Current topic results are unavailable.' : 'Sign in to explore current text clusters.'}
                </p>
              )}
              {trendList.map((t) => {
                const chip = trendChip(t.trend);
                return (
                  <m.div key={t.topic} variants={fadeUp}
                    className="flex items-center justify-between gap-3 py-2.5">
                    <span className={`text-sm truncate text-ink`} title={t.topic}>
                      {t.topic}
                    </span>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`text-xs font-semibold text-muted`}>{t.count}</span>
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-semibold border ${chip.cls}`}>
                        {chip.label}
                      </span>
                    </div>
                  </m.div>
                );
              })}
            </m.div>

            <Link to="/trend-analysis"
              className={`inline-flex items-center gap-1.5 mt-5 text-xs font-semibold text-primary hover:opacity-80`}>
              View all trends <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
            </Link>
          </div>

          {/* RIGHT — Why THESYS+ (lighter stacked layout, no card containers) */}
          <div>
            <h2 className={`text-base font-bold mb-1 text-ink`}>
              Why THESYS+
            </h2>
            <p className={`text-xs mb-6 text-muted`}>
              Built to support the CCS undergraduate thesis lifecycle.
            </p>

            <m.div
              className="space-y-6"
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-80px' }}
              variants={staggerContainer}
            >
              <m.div variants={fadeUp} className="flex items-start gap-4">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-info-bg`}>
                  <ShieldCheck className={`w-5 h-5 text-primary`} aria-hidden="true" />
                </div>
                <div>
                  <h3 className={`text-sm font-semibold mb-0.5 text-ink`}>Prevent Topic Duplication</h3>
                  <p className={`text-xs leading-relaxed text-body`}>
                    Validate thesis titles early to avoid duplication and ensure research originality.
                  </p>
                </div>
              </m.div>

              <m.div variants={fadeUp} className="flex items-start gap-4">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-info-bg`}>
                  <Search className={`w-5 h-5 text-primary`} aria-hidden="true" />
                </div>
                <div>
                  <h3 className={`text-sm font-semibold mb-0.5 text-ink`}>Improve Discoverability</h3>
                  <p className={`text-xs leading-relaxed text-body`}>
                    Make completed CCS theses findable by meaning, not just by exact keywords.
                  </p>
                </div>
              </m.div>

              <m.div variants={fadeUp} className="flex items-start gap-4">
                <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-success-bg`}>
                  <TrendingUp className={`w-5 h-5 text-success`} aria-hidden="true" />
                </div>
                <div>
                  <h3 className={`text-sm font-semibold mb-0.5 text-ink`}>Reveal Research Trends</h3>
                  <p className={`text-xs leading-relaxed text-body`}>
                    {reviewedSubjectsEnabled
                      ? 'Compare relative thesis counts in reviewed subjects, with exploratory text clusters available separately.'
                      : 'Explore AI-generated text clusters while subject assignments are being prepared.'}
                  </p>
                </div>
              </m.div>
            </m.div>
          </div>

        </div>
      </section>
      </LazyMotion>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          FOOTER — dark band with institutional links
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <footer className={`border-t ${isDark ? 'border-white/[0.06] bg-[#060b1e]' : 'border-gray-800 bg-[#0f172a]'}`}>
        <div className="max-w-6xl mx-auto px-5 sm:px-8 lg:px-14 py-6">
          {/* Desktop: 4-column flex row | Mobile: stacked */}
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6 sm:gap-4">

            {/* Col 1 — logo + institution */}
            <div className="flex flex-col gap-1 min-w-0">
              <ThesysLogo variant="wordmark" size={26} onDark />
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
                      className="text-xs text-gray-300 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary">
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

            {/* Col 4 — social icons (only verified destinations) */}
            <div className="flex items-center gap-3 sm:self-end">
              <a
                href="https://web.facebook.com/dhvsu.ccssc"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Visit CCS Facebook page (opens in new tab)"
                className="w-8 h-8 rounded-full bg-white/[0.06] flex items-center justify-center hover:bg-white/[0.12] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
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
      />
    </div>
  );
}
