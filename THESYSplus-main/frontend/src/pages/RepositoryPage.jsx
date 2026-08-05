/**
 * RepositoryPage — thesis repository list with semantic similarity threshold.
 *
 * Authenticated route. Lists approved theses (students see approved only;
 * faculty/admin see all). Supports basic search, year/program filters,
 * a similarity threshold slider, and pagination.
 *
 * Performance notes:
 *   - Threshold changes are debounced (500ms) so dragging the slider does
 *     not fire a new API request on every tick.
 *   - While a debounced threshold update is in flight the existing results
 *     stay visible; only a small "Updating results…" badge appears.
 *   - Filter / search / page changes use a module-level memory cache keyed
 *     on the full query string. Cache entries expire after 2 minutes so
 *     returning to a prior search is instant while stale data is avoided.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { BookOpen } from 'lucide-react';
import client from '../api/client';
import { registerCacheClearer } from '../utils/appCaches';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import AppNavbar from '../components/layout/AppNavbar';
import PageShell from '../components/layout/PageShell';
import SimilaritySlider from '../components/ui/SimilaritySlider';
import { Badge } from '../components/shadcn/badge';
import { Tooltip, TooltipTrigger, TooltipContent } from '../components/shadcn/tooltip';

const PROGRAMS = [
  'BS Information System',
  'BS Information Technology',
  'BS Computer Science',
  'Associate in Computer Technology',
];

// Dynamically generate years from current year back 10 years
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 10 }, (_, i) => CURRENT_YEAR - i);

const DEFAULT_THRESHOLD = 60; // 60 % — maps to 0.60 cosine score
const PAGE_SIZE = 20;
const DEBOUNCE_MS = 500;   // threshold debounce window
const CACHE_TTL_MS = 2 * 60 * 1000; // 2-minute memory cache

// Seeded example queries — known to return matches in the CCS corpus.
// Used as cold-start guidance and zero-result recovery.
const EXAMPLE_QUERIES = [
  'RFID attendance monitoring',
  'inventory and POS systems',
  'AI and machine learning',
];

// ---------------------------------------------------------------------------
// Module-level memory cache — survives re-renders, cleared on page unload.
// Keys are the full query string; values are { data, ts }.
// ---------------------------------------------------------------------------
const repoCache = new Map();

function getCached(key) {
  const entry = repoCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.ts > CACHE_TTL_MS) { repoCache.delete(key); return null; }
  return entry.data;
}

function setCache(key, data) {
  repoCache.set(key, { data, ts: Date.now() });
}

// Register cache clearer so logout wipes stale data across user sessions
registerCacheClearer(() => repoCache.clear());

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusVariantClass(status, isDark) {
  const map = {
    approved: isDark
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/15'
      : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-50',
    pending_review: isDark
      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/15'
      : 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-50',
    rejected: isDark
      ? 'bg-rose-500/15 text-rose-300 border-rose-500/30 hover:bg-rose-500/15'
      : 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-50',
  };
  return map[status] || map.pending_review;
}

function semanticBadgeClass(score, isDark) {
  if (score >= 0.80) {
    return isDark
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/15'
      : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-50';
  }
  if (score >= 0.60) {
    return isDark
      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/15'
      : 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-50';
  }
  return isDark
    ? 'bg-blue-500/15 text-blue-300 border-blue-500/30 hover:bg-blue-500/15'
    : 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-50';
}

function semanticDotColor(score) {
  if (score >= 0.80) return '#10b981';
  if (score >= 0.60) return '#f59e0b';
  return '#3b82f6';
}

// ---------------------------------------------------------------------------
// ThesisCard
// ---------------------------------------------------------------------------

function ThesisCard({ thesis, isDark }) {
  const score = thesis.similarity_score;
  const showScore = typeof score === 'number';
  // Use one decimal place so displayed value (e.g. "47.6%") reflects the
  // actual score used in threshold filtering, preventing confusion where a
  // thesis showing "48%" disappears when the threshold is raised to 48%.
  const pct = showScore ? (score * 100).toFixed(1) : null;

  return (
    <Link
      to={`/repository/${thesis.id}`}
      className="block thesys-card thesys-card-lift p-5"
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3
          className={`font-semibold text-base leading-snug line-clamp-2 ${
            isDark ? 'text-white' : 'text-gray-900'
          }`}
        >
          {thesis.title}
        </h3>

        <div className="flex items-center gap-1.5 flex-shrink-0">
          {showScore && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge
                  variant="outline"
                  className={`gap-1 text-xs px-2 py-0.5 h-auto cursor-default ${semanticBadgeClass(score, isDark)}`}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: semanticDotColor(score) }}
                    aria-hidden="true"
                  />
                  {pct}% Semantic Match
                </Badge>
              </TooltipTrigger>
              <TooltipContent side="top">
                Cosine similarity score: {score.toFixed(3)}
              </TooltipContent>
            </Tooltip>
          )}
          <Badge
            variant="outline"
            className={`text-xs px-2 py-0.5 h-auto uppercase tracking-wide ${statusVariantClass(thesis.status, isDark)}`}
          >
            {thesis.status.replace('_', ' ')}
          </Badge>
        </div>
      </div>

      <div className={`text-xs mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
        {thesis.program} · {thesis.year}
      </div>

      <div className={`text-sm mb-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
        {thesis.authors.slice(0, 3).join(', ')}
        {thesis.authors.length > 3 && ` +${thesis.authors.length - 3} more`}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {thesis.keywords.slice(0, 4).map((kw) => (
          <Badge
            key={kw}
            variant="outline"
            className={`text-xs px-2 py-0.5 h-auto ${
              isDark
                ? 'bg-blue-500/10 text-blue-300 border-blue-500/20 hover:bg-blue-500/10'
                : 'bg-blue-50 text-blue-700 border-blue-100 hover:bg-blue-50'
            }`}
          >
            {kw}
          </Badge>
        ))}
        {thesis.keywords.length > 4 && (
          <Badge
            variant="outline"
            className={`text-xs px-2 py-0.5 h-auto ${
              isDark
                ? 'bg-white/[0.05] text-gray-400 border-white/10 hover:bg-white/[0.05]'
                : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-50'
            }`}
          >
            +{thesis.keywords.length - 4} more
          </Badge>
        )}
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function RepositoryPage() {
  const { theme } = useTheme();
  const { isAuthenticated, isInitializing } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isDark = theme === 'dark';

  const initialQ = searchParams.get('q') || '';

  const [theses, setTheses] = useState([]);
  // loading: true only when no results are currently displayed (first load / hard filter change)
  const [loading, setLoading] = useState(true);
  // softLoading: true when results are visible but a background refresh is happening
  const [softLoading, setSoftLoading] = useState(false);
  const [error, setError] = useState('');

  // Committed search term (triggers fetch)
  const [search, setSearch] = useState(initialQ);
  // Controlled input value (not committed until form submit)
  const [searchInput, setSearchInput] = useState(initialQ);

  const [year, setYear] = useState('');
  const [program, setProgram] = useState('');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // sliderThreshold: live value shown in the slider UI (updates on every drag tick)
  const [sliderThreshold, setSliderThreshold] = useState(DEFAULT_THRESHOLD);
  // committedThreshold: debounced value actually used in API calls
  const [committedThreshold, setCommittedThreshold] = useState(DEFAULT_THRESHOLD);

  // Debounce threshold changes: update committedThreshold 500ms after dragging stops
  const debounceRef = useRef(null);
  const handleThresholdChange = useCallback((v) => {
    setSliderThreshold(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setCommittedThreshold(v);
      setPage(1);
    }, DEBOUNCE_MS);
  }, []);

  // Clean up debounce timer on unmount
  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current); }, []);

  const loadTheses = useCallback(async () => {
    const params = new URLSearchParams();
    if (search) {
      params.set('q', search);
      params.set('min_score', (committedThreshold / 100).toFixed(2));
    }
    if (year) params.set('year', year);
    if (program) params.set('program', program);
    params.set('page', String(page));
    params.set('page_size', String(PAGE_SIZE));

    const cacheKey = params.toString();
    const cached = getCached(cacheKey);

    if (cached) {
      // Instant render from cache — no skeleton shown
      setTheses(cached.results || []);
      setTotalCount(cached.count || 0);
      setLoading(false);
      setSoftLoading(false);
      return;
    }

    // No cache: show skeleton only if we have no results yet, otherwise use soft indicator
    if (theses.length === 0) {
      setLoading(true);
    } else {
      setSoftLoading(true);
    }
    setError('');

    try {
      const res = await client.get(`/theses/?${cacheKey}`);
      setCache(cacheKey, res.data);
      setTheses(res.data.results || []);
      setTotalCount(res.data.count || 0);
    } catch (err) {
      // Ignore request cancellations (component unmounted mid-fetch)
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') {
        return;
      }
      // If we were doing a background refresh and already have results visible,
      // silently swallow the error — don't replace good data with an error banner.
      // Only show the error state when the page has nothing to display.
      if (theses.length === 0) {
        setError('Failed to load theses. Please try again.');
        setTheses([]);
      }
      // If theses.length > 0 (soft-loading), leave existing data intact
    } finally {
      setLoading(false);
      setSoftLoading(false);
    }
  }, [search, year, program, page, committedThreshold]); // eslint-disable-line react-hooks/exhaustive-deps
  // Note: `theses` is intentionally excluded from deps — it's read only to
  // decide skeleton vs soft-indicator, and including it would cause an extra
  // render cycle after every fetch.

  useEffect(() => {
    if (isInitializing || !isAuthenticated) return;
    loadTheses();
  }, [isAuthenticated, isInitializing, loadTheses]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  // Run a seeded example query — populates the input and commits the search.
  const runExampleQuery = (q) => {
    setSearchInput(q);
    setSearch(q);
    setPage(1);
  };

  // Lower the similarity threshold in one click (zero-result recovery).
  // Sets both slider + committed value so the fetch re-runs immediately.
  const applyThreshold = (pct) => {
    setSliderThreshold(pct);
    setCommittedThreshold(pct);
    setPage(1);
  };

  // Reusable example-query chip row
  const ExampleChips = () => (
    <div className="flex flex-wrap items-center justify-center gap-2">
      {EXAMPLE_QUERIES.map((q) => (
        <button
          key={q}
          type="button"
          onClick={() => runExampleQuery(q)}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
            isDark
              ? 'border-white/15 text-gray-300 hover:bg-white/[0.07] hover:text-white'
              : 'border-gray-300 text-gray-700 hover:bg-gray-100 hover:text-gray-900'
          }`}
        >
          <svg className="w-3 h-3 flex-shrink-0 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          {q}
        </button>
      ))}
    </div>
  );

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      <AppNavbar activePage="repository" />

      <PageShell>

        {/* Page heading */}
        <div className="mb-6">
          <h1 className={`text-2xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
            Research Repository
          </h1>
          <p className={`text-sm flex items-center gap-2 flex-wrap ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
            <span>
              {search
                ? <>Semantic search results for: <strong className={isDark ? 'text-gray-200' : 'text-gray-800'}>{search}</strong></>
                : <>Browsing all approved theses from PampangaStateU CCS</>
              }
            </span>
            {!search && (
              <>
                <span className={isDark ? 'text-gray-600' : 'text-gray-300'}>·</span>
                <span className={isDark ? 'text-gray-500' : 'text-gray-500'}>{totalCount} indexed</span>
              </>
            )}
            <span className={isDark ? 'text-gray-600' : 'text-gray-300'}>·</span>
            <span className={`inline-flex items-center gap-1 text-primary`}>
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
              </svg>
              Semantic Search Enabled
            </span>
            {/* Soft-loading indicator — appears beside the heading during background refreshes */}
            {softLoading && (
              <span className={`inline-flex items-center gap-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" className="opacity-20"/>
                  <path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
                </svg>
                Updating results…
              </span>
            )}
          </p>
        </div>

        {/* ── Filter bar ────────────────────────────────────────────────── */}
        <div className="thesys-card p-4 mb-6">
          <form onSubmit={handleSearchSubmit} className="flex flex-col gap-3">

            {/* Row 1: search input + year/program selects + submit */}
            <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto_auto] gap-3">
              <input
                type="text"
                placeholder="Search title, abstract, authors, keywords..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className={`px-4 py-2.5 rounded-lg border text-sm outline-none transition-colors ${
                  isDark
                    ? 'bg-white/[0.04] border-white/10 text-gray-200 placeholder-gray-500 focus:border-blue-500/40'
                    : 'bg-white border-gray-200 text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100'
                }`}
              />

              <select
                value={year}
                onChange={(e) => { setPage(1); setYear(e.target.value); }}
                className={`px-3 py-2.5 rounded-lg border text-sm outline-none transition-colors ${
                  isDark
                    ? 'bg-white/[0.04] border-white/10 text-gray-200'
                    : 'bg-white border-gray-200 text-gray-700'
                }`}
              >
                <option value="">All years</option>
                {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>

              <select
                value={program}
                onChange={(e) => { setPage(1); setProgram(e.target.value); }}
                className={`px-3 py-2.5 rounded-lg border text-sm outline-none transition-colors ${
                  isDark
                    ? 'bg-white/[0.04] border-white/10 text-gray-200'
                    : 'bg-white border-gray-200 text-gray-700'
                }`}
              >
                <option value="">All programs</option>
                {PROGRAMS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>

              <button
                type="submit"
                className="px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors"
              >
                {searchInput.trim() ? 'Semantic Search' : 'Search'}
              </button>
            </div>

            {/* Row 2: similarity threshold — always visible */}
            <div
              className={`pt-3 mt-1 border-t ${
                isDark ? 'border-white/[0.06]' : 'border-gray-100'
              }`}
            >
              <Tooltip>
                <TooltipTrigger asChild>
                  <div>
                    <SimilaritySlider
                      value={sliderThreshold}
                      onChange={handleThresholdChange}
                      isDark={isDark}
                      disabled={false}
                      helperText="Similarity threshold applies only when using Semantic Search. Set your preferred strictness before searching."
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-xs">
                  Controls the minimum cosine similarity score (0–1) that results must meet. 60% is the recommended default for balanced results.
                </TooltipContent>
              </Tooltip>
            </div>
          </form>
        </div>

        {/* Cold-start guidance — example queries shown before any search is run */}
        {!search && !loading && !error && (
          <div className="mb-6 flex flex-col items-center gap-2 text-center">
            <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              Try a semantic search:
            </p>
            <ExampleChips />
          </div>
        )}

        {/* ── Results ───────────────────────────────────────────────────── */}
        {loading ? (
          <>
            <p className={`text-xs mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              {search ? 'Searching semantically…' : 'Loading repository…'}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="thesys-card p-5">
                  <div className="thesys-skeleton h-5 w-3/4 mb-3" />
                  <div className="thesys-skeleton h-3 w-1/3 mb-3" />
                  <div className="thesys-skeleton h-3 w-1/2 mb-4" />
                  <div className="flex gap-1.5">
                    <div className="thesys-skeleton h-4 w-14 rounded-full" />
                    <div className="thesys-skeleton h-4 w-18 rounded-full" />
                    <div className="thesys-skeleton h-4 w-12 rounded-full" />
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : error ? (
          <div className={`rounded-xl p-8 text-center ${isDark ? 'bg-rose-500/10 text-rose-300' : 'bg-rose-50 text-rose-700'}`}>
            {error}
          </div>
        ) : theses.length === 0 ? (
          search ? (
            /* ── Zero Results — a query ran but nothing matched ─────────── */
            <div className="thesys-empty">
              <BookOpen className="w-10 h-10 text-primary" aria-hidden="true" />
              <p className={`font-semibold ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                {committedThreshold > 50
                  ? `No theses found above ${committedThreshold}% similarity.`
                  : 'No related theses found.'}
              </p>
              <p className={`text-sm max-w-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                {committedThreshold > 50
                  ? 'Lower the similarity threshold to broaden the search, or try a different query.'
                  : 'Try a broader query or one of the examples below.'}
              </p>

              {/* One-click threshold broadening */}
              {committedThreshold > 50 && (
                <button
                  type="button"
                  onClick={() => applyThreshold(50)}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  Try lowering the threshold to 50%
                </button>
              )}

              {/* Example-query recovery */}
              <div className="mt-2 flex flex-col items-center gap-2">
                <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>Or try one of these searches:</p>
                <ExampleChips />
              </div>
            </div>
          ) : (
            /* ── Empty Corpus — repository has no theses at all ─────────── */
            <div className="thesys-empty">
              <BookOpen className="w-10 h-10 text-primary" aria-hidden="true" />
              <p className={`font-semibold ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                No theses in repository yet.
              </p>
              <p className={`text-sm max-w-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                Upload and approve theses to populate the repository. Approved theses become "Semantic Ready" and are indexed for AI-assisted search.
              </p>
            </div>
          )
        ) : (
          <>
            {/* Result count summary — distinguishes semantic matches from title-rescued results */}
            {search && (() => {
              const threshold = committedThreshold / 100;
              const aboveThreshold = theses.filter(t => (t.similarity_score ?? 0) >= threshold).length;
              const belowThreshold = theses.filter(t => (t.similarity_score ?? 0) < threshold).length;
              // Use totalCount for the above-threshold count only when all current-page results pass,
              // otherwise use page-level counts which are what the user actually sees.
              const totalAbove = belowThreshold === 0 ? totalCount : aboveThreshold;
              const totalBelow = belowThreshold;

              let summary;
              if (totalBelow === 0) {
                // All results passed semantic threshold — original wording
                summary = `${totalAbove} result${totalAbove !== 1 ? 's' : ''} above ${committedThreshold}% similarity`;
              } else if (totalAbove === 0) {
                // All results are title-rescued (below threshold)
                summary = `${totalBelow} exact title match${totalBelow !== 1 ? 'es' : ''} found below ${committedThreshold}% semantic similarity`;
              } else {
                // Mixed: some semantic, some title-rescued
                summary = `${totalAbove + totalBelow} result${totalAbove + totalBelow !== 1 ? 's' : ''} found: ${totalAbove} above ${committedThreshold}% similarity, ${totalBelow} exact title match${totalBelow !== 1 ? 'es' : ''} below threshold`;
              }

              return (
                <p className={`text-xs mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  {summary}
                </p>
              );
            })()}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {theses.map((t) => (
                <ThesisCard key={t.id} thesis={t} isDark={isDark} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                    isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Previous
                </button>
                <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                    isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}

      </PageShell>
    </div>
  );
}
