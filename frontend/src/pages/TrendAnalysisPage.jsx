/**
 * TrendAnalysisPage — Phase 3 topic trend analysis dashboard.
 *
 * GET /api/v1/theses/topic-trends/
 *
 * Renders:
 *   1. Repository overview cards (total theses · total topics ·
 *      saturated · underexplored)
 *   2. Topic distribution doughnut + counts bar chart (lightweight inline
 *      SVG — no chart.js dependency)
 *   3. Topic cluster cards (label, trend badge, count, top TF-IDF keywords,
 *      sample thesis titles)
 *
 * Visual language matches Repository / Title Similarity / Upload pages.
 *
 * Performance:
 *   - Module-level memory cache with a 5-minute TTL.
 *   - On mount, cached data is rendered immediately (no skeleton on revisit).
 *   - Background refresh runs silently; state updates when it completes.
 *   - Full skeleton shown only on first load with no cached data.
 */

import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { LazyMotion, domAnimation, m } from 'framer-motion';
import { BarChart3 } from 'lucide-react';
import client from '../api/client';
import { registerCacheClearer } from '../utils/appCaches';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import AppNavbar from '../components/layout/AppNavbar';
import PageShell from '../components/layout/PageShell';
import PageHeader from '../components/layout/PageHeader';
import { Badge } from '../components/shadcn/badge';
import AnimatedCounter from '../components/ui/AnimatedCounter';
import { useMotionVariants, useAnimatedCounterValue } from '../lib/motion';
import { CHART_PALETTE } from '../styles/tokens';

// ---------------------------------------------------------------------------
// Module-level memory cache — 5-minute TTL, single slot for topic trends
// ---------------------------------------------------------------------------
const TRENDS_CACHE_TTL = 5 * 60 * 1000;
let trendsCache = null; // { data, ts }

function getTrendsCached() {
  if (!trendsCache) return null;
  if (Date.now() - trendsCache.ts > TRENDS_CACHE_TTL) { trendsCache = null; return null; }
  return trendsCache.data;
}

function setTrendsCache(data) {
  trendsCache = { data, ts: Date.now() };
}

// Register cache clearer so logout wipes stale data across user sessions
registerCacheClearer(() => { trendsCache = null; });

// Trend classifications (mirror backend constants)
const TREND_SATURATED = 'SATURATED';
const TREND_EMERGING = 'EMERGING';
const TREND_UNDEREXPLORED = 'UNDEREXPLORED';


// ---------------------------------------------------------------------------
// Visual helpers
// ---------------------------------------------------------------------------

function trendStyles(trend, isDark) {
  switch (trend) {
    case TREND_SATURATED:
      return {
        emoji: '🔴',
        label: 'Saturated',
        chip: isDark
          ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
          : 'bg-rose-50 text-rose-700 border-rose-200',
        accent: isDark ? '#f87171' : '#e11d48',
      };
    case TREND_EMERGING:
      return {
        emoji: '🟡',
        label: 'Emerging',
        chip: isDark
          ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
          : 'bg-amber-50 text-amber-700 border-amber-200',
        accent: isDark ? '#fbbf24' : '#d97706',
      };
    case TREND_UNDEREXPLORED:
    default:
      return {
        emoji: '🟢',
        label: 'Underexplored',
        chip: isDark
          ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
          : 'bg-emerald-50 text-emerald-700 border-emerald-200',
        accent: isDark ? '#34d399' : '#059669',
      };
  }
}

// Deterministic palette for clusters (cycles for >7 clusters) — from tokens.js
const CLUSTER_PALETTE = CHART_PALETTE;

// Max individual slices in the doughnut before the tail is grouped into "Other".
// Beyond this, the ring and its legend become unreadable (DESIGN.md note).
const MAX_DOUGHNUT_SLICES = 7;

/**
 * buildDoughnutSegments — caps the doughnut at MAX_DOUGHNUT_SLICES readable
 * slices. When there are more clusters, the largest (maxSlices − 1) are kept
 * as individual slices and the remainder collapse into a single neutral
 * "Other" slice.
 *
 * Color consistency: kept clusters retain the palette color of their ORIGINAL
 * index, so a topic's doughnut slice matches its dot in the cluster-cards
 * section below. "Other" uses a neutral gray (outside the cluster palette).
 */
function buildDoughnutSegments(clusters, isDark, maxSlices = MAX_DOUGHNUT_SLICES) {
  const withColor = clusters.map((c, idx) => ({
    id: c.cluster_id,
    topic: c.topic,
    thesis_count: c.thesis_count,
    color: CLUSTER_PALETTE[idx % CLUSTER_PALETTE.length],
  }));

  if (withColor.length <= maxSlices) return withColor;

  // Keep the largest (maxSlices − 1) by count; aggregate the rest as "Other".
  const sorted = [...withColor].sort((a, b) => b.thesis_count - a.thesis_count);
  const kept = sorted.slice(0, maxSlices - 1);
  const rest = sorted.slice(maxSlices - 1);
  const otherCount = rest.reduce((sum, c) => sum + c.thesis_count, 0);

  return [
    ...kept,
    {
      id: 'other',
      topic: `Other (${rest.length} topics)`,
      thesis_count: otherCount,
      color: isDark ? '#6b7280' : '#9ca3af',
    },
  ];
}


// ---------------------------------------------------------------------------
// Doughnut — topic distribution
// ---------------------------------------------------------------------------

function DoughnutChart({ segments, isDark }) {
  const { fadeIn, drawArc } = useMotionVariants();
  const total = segments.reduce((sum, s) => sum + s.thesis_count, 0);
  // Drives the center total count-up. The SVG <text> node can't host
  // AnimatedCounter's <span> markup, so we consume the shared tween hook
  // directly and render a plain text node (aria-hidden — the surrounding
  // <svg role="img"> already carries the full accessible summary).
  const { hasNumericValue, displayValue } = useAnimatedCounterValue(total, 0.5);
  const centerCountDisplay = hasNumericValue ? displayValue : total;
  if (total === 0) return null;

  const radius = 60;
  const stroke = 22;
  const circumference = 2 * Math.PI * radius;

  // Accessible summary for the chart's aria-label
  const summary = segments
    .map((s) => `${s.topic} ${s.thesis_count}`)
    .join(', ');

  // Prefix sums of thesis_count so each segment's cumulative offset can be
  // looked up by index instead of mutating a running total during render
  // (keeps the mapping pure — no `let` reassignment inside the JSX map).
  const prefixTotals = segments.reduce((acc, s, idx) => {
    acc.push((idx === 0 ? 0 : acc[idx - 1]) + s.thesis_count);
    return acc;
  }, []);

  return (
    <div className="flex items-center justify-center">
      <svg
        viewBox="0 0 160 160"
        className="w-44 h-44 -rotate-90"
        role="img"
        aria-label={`Topic distribution across ${segments.length} segments, ${total} theses total: ${summary}`}
      >
        {/* Background ring — static */}
        <circle
          cx="80" cy="80" r={radius}
          fill="none" stroke={isDark ? '#1e293b' : '#e5e7eb'}
          strokeWidth={stroke}
        />
        {segments.map((s, idx) => {
          const priorTotal = idx === 0 ? 0 : prefixTotals[idx - 1];
          const fraction = s.thesis_count / total;
          const dash = fraction * circumference;
          // strokeDashoffset stays fixed per segment — only the dash LENGTH
          // animates, so segments draw in at their correct angular position
          // rather than sweeping around the ring.
          const offset = -((priorTotal / total) * circumference);
          return (
            <m.circle
              key={s.id}
              cx="80" cy="80" r={radius}
              fill="none"
              stroke={s.color}
              strokeWidth={stroke}
              strokeDashoffset={offset}
              strokeLinecap="butt"
              initial="hidden"
              animate="visible"
              transition={{ delay: idx * 0.06 }}
              variants={drawArc(dash, circumference)}
            >
              <title>{`${s.topic} — ${s.thesis_count} thes${s.thesis_count === 1 ? 'is' : 'es'}`}</title>
            </m.circle>
          );
        })}
        {/* Center label — static geometry, fades in once arcs finish drawing */}
        <m.g
          transform="rotate(90, 80, 80)"
          initial="hidden"
          animate="visible"
          transition={{ delay: segments.length * 0.06 + 0.1 }}
          variants={fadeIn}
        >
          <text
            x="80" y="74" textAnchor="middle"
            className={`font-bold ${isDark ? 'fill-white' : 'fill-gray-900'}`}
            style={{ fontSize: '22px' }}
            aria-hidden="true"
          >
            {centerCountDisplay}
          </text>
          <text
            x="80" y="92" textAnchor="middle"
            className={isDark ? 'fill-gray-400' : 'fill-gray-500'}
            style={{ fontSize: '10px', letterSpacing: '0.1em' }}
          >
            THESES
          </text>
        </m.g>
      </svg>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Bar — thesis count per topic
// ---------------------------------------------------------------------------

function CountsBarChart({ clusters, isDark }) {
  const { staggerContainer, growWidth } = useMotionVariants();
  if (clusters.length === 0) return null;
  const max = Math.max(...clusters.map((c) => c.thesis_count), 1);
  const summary = clusters.map((c) => `${c.topic} ${c.thesis_count}`).join(', ');

  return (
    <m.div
      className="space-y-2"
      role="img"
      aria-label={`Theses per topic: ${summary}`}
      initial="hidden"
      animate="visible"
      variants={staggerContainer}
    >
      {clusters.map((c, idx) => {
        const pct = (c.thesis_count / max) * 100;
        const color = CLUSTER_PALETTE[idx % CLUSTER_PALETTE.length];
        return (
          <div key={c.cluster_id} className="flex items-center gap-3">
            <span
              className={`text-xs font-medium truncate w-32 sm:w-44 flex-shrink-0 ${
                isDark ? 'text-gray-300' : 'text-gray-700'
              }`}
              title={c.topic}
            >
              {c.topic}
            </span>
            <div
              className={`flex-1 h-3 rounded-full overflow-hidden ${
                isDark ? 'bg-white/[0.05]' : 'bg-gray-100'
              }`}
            >
              <m.div
                className="h-full"
                variants={growWidth(pct)}
                style={{ backgroundColor: color }}
              />
            </div>
            <span
              className={`text-xs font-semibold tabular-nums w-6 text-right flex-shrink-0 ${
                isDark ? 'text-gray-400' : 'text-gray-600'
              }`}
            >
              {c.thesis_count}
            </span>
          </div>
        );
      })}
    </m.div>
  );
}


// ---------------------------------------------------------------------------
// Stat card — shadcn Card
// ---------------------------------------------------------------------------

function StatCard({ label, value, sublabel, isDark, accent }) {
  const isNumeric = typeof value === 'number' && Number.isFinite(value);
  return (
    <div>
      <div
        className={`text-3xl sm:text-4xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-gray-900'}`}
        style={accent ? { color: accent } : undefined}
      >
        {isNumeric ? <AnimatedCounter value={value} /> : value}
      </div>
      <div className={`text-xs font-semibold uppercase tracking-wider mt-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
        {label}
      </div>
      {sublabel && (
        <div className={`text-xs mt-0.5 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          {sublabel}
        </div>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Cluster card — shadcn Card + Badge
// ---------------------------------------------------------------------------

function ClusterCard({ cluster, isDark, paletteColor, reviewed = false }) {
  const styles = trendStyles(cluster.trend, isDark);
  return (
    // The whole card is a Link (not an onClick on the <article>) so the
    // drill-down gets keyboard focus, Enter activation, and middle-click
    // "open in new tab" for free. Nothing inside the card is interactive
    // (badges are plain spans/divs), so nesting them inside the <a> is
    // safe — no interactive-in-interactive violation.
    <Link to={reviewed ? `?subject=${cluster.subject_code}` : `?view=clusters&cluster=${cluster.cluster_id}`} className="block h-full">
      <article className="thesys-panel thesys-card-lift h-full flex flex-col">
        <div className="flex flex-col flex-1">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: paletteColor }}
              aria-hidden="true"
            />
            <h3 className={`font-bold text-base ${isDark ? 'text-white' : 'text-gray-900'}`}>
              {cluster.topic}
            </h3>
          </div>
          <Badge
            variant="outline"
            className={`gap-1 text-xs px-2 py-0.5 h-auto uppercase tracking-wide whitespace-nowrap flex-shrink-0 ${styles.chip}`}
          >
            <span aria-hidden="true">{styles.emoji}</span>
            {styles.label}
          </Badge>
        </div>

        <div className={`text-xs mb-3 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
          <strong className={isDark ? 'text-gray-200' : 'text-gray-800'}>
            {cluster.thesis_count}
          </strong>{' '}
          thes{cluster.thesis_count === 1 ? 'is' : 'es'} in this {reviewed ? 'subject' : 'cluster'}
        </div>

        {cluster.keywords && cluster.keywords.length > 0 && (
          <div className="mb-3">
            <div className={`text-xs font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              Top keywords (TF-IDF)
            </div>
            <div className="flex flex-wrap gap-1.5">
              {cluster.keywords.map((kw) => (
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
            </div>
          </div>
        )}

        <TechnologyTags tags={cluster.technology_tags} isDark={isDark} />

        {cluster.sample_titles && cluster.sample_titles.length > 0 && (
          <div className="mt-auto">
            <div className={`text-xs font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              Sample studies
            </div>
            <ul className="space-y-1">
              {cluster.sample_titles.slice(0, 3).map((title, i) => (
                <li
                  key={i}
                  className={`text-xs leading-snug line-clamp-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}
                  title={title}
                >
                  · {title}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      </article>
    </Link>
  );
}


// ---------------------------------------------------------------------------
// Topic check — is a proposed title's topic saturated, emerging or
// underexplored? POST /theses/topic-trends/check-title/
// ---------------------------------------------------------------------------

function TopicCheck({ isDark }) {
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const trimmed = title.trim();

  const submit = async (e) => {
    e.preventDefault();
    if (trimmed.length < 5 || loading) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const res = await client.post('/theses/topic-trends/check-title/', { title: trimmed });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.error?.message || 'The topic check could not run. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const styles = result && trendStyles(result.trend, isDark);
  const muted = isDark ? 'text-gray-400' : 'text-gray-600';

  return (
    <section className="thesys-panel mb-8" aria-labelledby="topic-check-heading">
      <h2 id="topic-check-heading" className={`font-bold text-base ${isDark ? 'text-white' : 'text-gray-900'}`}>
        Check your proposed topic
      </h2>
      <p className={`text-sm mt-1 mb-4 ${muted}`}>
        Enter a thesis title to see how many uploaded theses already cover its topic.
      </p>
      <form onSubmit={submit} className="flex flex-col sm:flex-row gap-2">
        <label htmlFor="topic-check-title" className="sr-only">Proposed thesis title</label>
        <input
          id="topic-check-title"
          type="text"
          value={title}
          maxLength={500}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. IoT-based smart irrigation system for rice farmers"
          className={`flex-1 min-w-0 px-4 py-2.5 rounded-lg border text-sm outline-none transition-colors ${
            isDark
              ? 'bg-white/[0.04] border-white/10 text-gray-200 placeholder-gray-500 focus:border-blue-500/40 focus-visible:ring-2 focus-visible:ring-blue-400'
              : 'bg-white border-gray-200 text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100'
          }`}
        />
        <button
          type="submit"
          disabled={trimmed.length < 5 || loading}
          className="px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
        >
          {loading ? 'Analyzing…' : 'Analyze topic'}
        </button>
      </form>

      <div aria-live="polite">
        {error && (
          <p className={`text-sm mt-4 ${isDark ? 'text-rose-300' : 'text-rose-700'}`}>{error}</p>
        )}
        {result && (
          <div className={`mt-5 pt-5 border-t ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
            <Badge
              variant="outline"
              className={`gap-1 text-xs px-2 py-0.5 h-auto uppercase tracking-wide ${styles.chip}`}
            >
              <span aria-hidden="true">{styles.emoji}</span>
              {styles.label}
            </Badge>
            <p className={`text-sm mt-3 max-w-prose ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
              {result.explanation}
            </p>
            {result.related.length > 0 && (
              <>
                <h3 className={`text-xs font-semibold uppercase tracking-wider mt-5 mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                  Most related theses
                </h3>
                <ul className={`divide-y ${isDark ? 'divide-white/10' : 'divide-gray-100'}`}>
                  {result.related.map((t) => (
                    <li key={t.id}>
                      <Link
                        to={`/repository/${t.id}`}
                        className={`flex items-baseline justify-between gap-4 py-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${isDark ? 'hover:text-white' : 'hover:text-blue-700'}`}
                      >
                        <span className={`text-sm min-w-0 ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                          {t.title}
                          <span className={`block text-xs mt-0.5 ${muted}`}>{t.year} · {t.program}</span>
                        </span>
                        <span className={`text-xs tabular-nums flex-shrink-0 ${muted}`}>
                          {Math.round(t.similarity * 100)}% similar
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Cluster drill-down — one panel of thesis rows for a single cluster
// ---------------------------------------------------------------------------

// Technology tags — the technologies a group's theses are actually about
// (IoT, AI, NLP…). The backend only tags a thesis with evidence (a mention
// in its title, keywords or abstract, or dense full-text mentions), so a
// thesis that merely repeats "analysis" is never tagged IoT.
function TechnologyTags({ tags, isDark }) {
  if (!tags || tags.length === 0) return null;
  return (
    <div className="mb-3">
      <div className={`text-xs font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
        Technologies
      </div>
      <div className="flex flex-wrap gap-1.5">
        {tags.map(({ tag }) => (
          <Badge
            key={tag}
            variant="outline"
            className={`text-xs px-2 py-0.5 h-auto ${
              isDark
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20 hover:bg-emerald-500/10'
                : 'bg-emerald-50 text-emerald-700 border-emerald-100 hover:bg-emerald-50'
            }`}
          >
            {tag}
          </Badge>
        ))}
      </div>
    </div>
  );
}

/**
 * ClusterThesisRow — one row: title (line 1) + program · year (line 2) +
 * the thesis's technology tags, when it has any (line 3).
 * Deliberately excludes status (every thesis here is APPROVED — see
 * get_topic_trends_queryset — so a badge would be redundant), authors,
 * keyword chips, and abstract. This is a purpose-built simpler layout,
 * not RepositoryPage's ThesisCard.
 */
function ClusterThesisRow({ thesis, isDark, tags = [] }) {
  return (
    <Link
      to={`/repository/${thesis.id}`}
      className={`block px-4 py-3 transition-colors ${
        isDark ? 'hover:bg-white/[0.03]' : 'hover:bg-gray-50'
      }`}
    >
      <h3
        className={`font-bold text-sm leading-snug line-clamp-2 hover:underline ${
          isDark ? 'text-white' : 'text-gray-900'
        }`}
      >
        {thesis.title}
      </h3>
      <p className={`text-xs mt-0.5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
        {thesis.program} · {thesis.year}
      </p>
      {tags.length > 0 && (
        <p className="mt-1 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <span
              key={tag}
              className={`text-[11px] px-1.5 py-0.5 rounded ${isDark ? 'bg-emerald-500/10 text-emerald-300' : 'bg-emerald-50 text-emerald-700'}`}
            >
              {tag}
            </span>
          ))}
        </p>
      )}
    </Link>
  );
}

/**
 * ClusterDetailView — renders in place of the overview when ``?cluster``
 * resolves to a real cluster in the already-loaded topic-trends response.
 *
 * Fetches the full membership list in one request via the `ids` filter
 * added to GET /theses/ (Task 1) — no new backend endpoint. Owns its own
 * loading/error state, independent of the overview's.
 */
function ClusterDetailView({ cluster, isDark, paletteColor, reviewed = false, fromThesisDetail = false }) {
  const navigate = useNavigate();
  const thesisIds = cluster.thesis_ids || [];
  const hasIds = thesisIds.length > 0;

  const [fetchedRows, setFetchedRows] = useState(null);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [rowsError, setRowsError] = useState(false);

  // Stable key for the effect below — re-fetch only when the actual set of
  // IDs changes (e.g. navigating to a different cluster), not on every
  // parent re-render.
  const idsKey = thesisIds.join(',');

  useEffect(() => {
    // Empty/missing thesis_ids → empty state, no request ever fired. This
    // branch intentionally does nothing (no setState) — the empty case is
    // handled below via the `hasIds` render-time derivation instead of
    // effect-driven state, so it stays correct even if this component
    // re-renders with a different cluster's props without remounting
    // (no `key`, so navigating cluster A → cluster B reuses the instance).
    if (!hasIds) return undefined;
    let cancelled = false;
    (async () => {
      setRowsLoading(true);
      setRowsError(false);
      try {
        const res = await client.get(
          `/theses/?ids=${thesisIds.join(',')}&page_size=100`
        );
        if (!cancelled) setFetchedRows(res.data.results || []);
      } catch {
        if (!cancelled) setRowsError(true);
      } finally {
        if (!cancelled) setRowsLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey, hasIds]);

  // Derived, not effect-driven: an empty-ID cluster is unconditionally an
  // empty list, regardless of what a *previous* cluster's fetch left in
  // `fetchedRows`.
  const rows = hasIds ? fetchedRows : [];

  const styles = trendStyles(cluster.trend, isDark);
  const overflowCount = Math.max(0, thesisIds.length - 100);

  return (
    <div>
      {/* ── Panel header ──────────────────────────────────────────── */}
      <div className="mb-6">
        {reviewed && fromThesisDetail ? (
          <button
            type="button"
            onClick={() => navigate(-1)}
            aria-label="Back to thesis"
            className={`inline-flex items-center gap-1.5 mb-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-sm ${
              isDark ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Back to thesis
          </button>
        ) : (
          <Link
            to={reviewed ? '/trend-analysis' : '/trend-analysis?view=clusters'}
            className={`inline-flex items-center gap-1.5 mb-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-sm ${
              isDark ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Back to {reviewed ? 'reviewed subjects' : 'text clusters'}
          </Link>
        )}

        <div className="flex items-center gap-2 mb-2">
          <span
            className="w-3 h-3 rounded-full flex-shrink-0"
            style={{ backgroundColor: paletteColor }}
            aria-hidden="true"
          />
          <h1 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
            {cluster.topic}
          </h1>
          <Badge
            variant="outline"
            className={`gap-1 text-xs px-2 py-0.5 h-auto uppercase tracking-wide whitespace-nowrap flex-shrink-0 ${styles.chip}`}
          >
            <span aria-hidden="true">{styles.emoji}</span>
            {styles.label}
          </Badge>
        </div>

        <p className={`text-sm mb-3 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
          {cluster.thesis_count} thes{cluster.thesis_count === 1 ? 'is' : 'es'} in this {reviewed ? 'subject' : 'cluster'}
        </p>

        {cluster.keywords && cluster.keywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {cluster.keywords.map((kw) => (
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
          </div>
        )}
        {cluster.technology_tags?.length > 0 && (
          <div className="mt-3">
            <TechnologyTags tags={cluster.technology_tags} isDark={isDark} />
          </div>
        )}
      </div>

      {overflowCount > 0 && (
        <p className={`text-xs mb-3 ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>
          Showing first 100 of {thesisIds.length} theses in this cluster.
        </p>
      )}

      {/* ── The list — one panel containing rows ─────────────────── */}
      {rowsLoading ? (
        <div className="thesys-panel divide-y divide-[var(--color-border-subtle)]">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="px-4 py-3">
              <div className="thesys-skeleton h-4 w-3/4 mb-2" />
              <div className="thesys-skeleton h-3 w-1/3" />
            </div>
          ))}
        </div>
      ) : rowsError ? (
        <div className={`rounded-xl p-8 text-center ${isDark ? 'bg-rose-500/10 text-rose-300' : 'bg-rose-50 text-rose-700'}`}>
          Failed to load theses for this {reviewed ? 'subject' : 'cluster'}. Please try again.
        </div>
      ) : rows && rows.length === 0 ? (
        <div className="thesys-empty">
          <p className={`font-semibold ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
            No theses found for this {reviewed ? 'subject' : 'cluster'}.
          </p>
        </div>
      ) : rows ? (
        <div className="thesys-panel divide-y divide-[var(--color-border-subtle)] overflow-hidden">
          {rows.map((thesis) => (
            <ClusterThesisRow
              key={thesis.id}
              thesis={thesis}
              isDark={isDark}
              tags={cluster.member_tags?.[thesis.id] || []}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TrendAnalysisPage() {
  const { theme } = useTheme();
  const { isAuthenticated, isInitializing } = useAuth();
  const isDark = theme === 'dark';
  const [searchParams] = useSearchParams();
  const location = useLocation();

  // Seed state from cache immediately — avoids blank flash on revisit
  const [clusterData, setData] = useState(() => getTrendsCached());
  const [clusterLoading, setLoading] = useState(() => !getTrendsCached());
  const [clusterError, setError] = useState('');
  const [subjectData, setSubjectData] = useState(null);
  const [subjectLoading, setSubjectLoading] = useState(true);
  const [subjectError, setSubjectError] = useState('');
  const reviewedEnabled = Boolean(subjectData?.main_view_enabled);
  const showClusters = !reviewedEnabled || searchParams.get('view') === 'clusters' || searchParams.has('cluster');
  const shouldLoadClusters = !subjectLoading && showClusters;
  const reviewed = reviewedEnabled && !showClusters;

  useEffect(() => {
    if (isInitializing || !isAuthenticated) return;
    let cancelled = false;
    client.get('/theses/subject-trends/')
      .then((res) => { if (!cancelled) setSubjectData(res.data); })
      .catch(() => { if (!cancelled) setSubjectError('Failed to load reviewed subjects. Please try again.'); })
      .finally(() => { if (!cancelled) setSubjectLoading(false); });
    return () => { cancelled = true; };
  }, [isAuthenticated, isInitializing]);

  useEffect(() => {
    // Wait for auth initialization to complete before fetching.
    // This prevents a request firing with no token (causing an unnecessary
    // 401 → refresh → retry round-trip that extends the skeleton duration).
    if (isInitializing || !isAuthenticated || !shouldLoadClusters) return;
    let cancelled = false;

    (async () => {
      // If we already have cached data, keep it visible and refresh in background
      const cached = getTrendsCached();
      if (!cached) {
        setLoading(true);
        setError('');
      }

      try {
        const res = await client.get('/theses/topic-trends/');
        if (!cancelled) {
          setTrendsCache(res.data);
          setData(res.data);
        }
      } catch (err) {
        // Only show error if we have nothing to display
        if (!cancelled && !cached) {
          setError('Failed to load topic trends. Please try again.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [isAuthenticated, isInitializing, shouldLoadClusters]);

  const data = reviewed && subjectData ? {
    status: subjectData.reviewed_count ? 'ok' : 'empty',
    total_theses: subjectData.approved_count,
    total_topics: subjectData.subjects.length,
    clusters: subjectData.subjects.map((subject) => ({
      ...subject,
      cluster_id: subject.subject_code,
      keywords: [],
    })),
    saturated_count: subjectData.saturated_count,
    underexplored_count: subjectData.underexplored_count,
  } : clusterData;
  const loading = subjectLoading || (showClusters && clusterLoading);
  const error = reviewed ? subjectError : clusterError;

  // Memoise palette mapping so cluster colours stay stable across re-renders
  const colourFor = useMemo(() => {
    if (!data?.clusters) return () => CHART_PALETTE[0];
    return (idx) => CLUSTER_PALETTE[idx % CLUSTER_PALETTE.length];
  }, [data]);

  // Doughnut segments — caps slices at MAX_DOUGHNUT_SLICES, grouping the tail
  // into "Other" so the ring and its legend stay readable at high cluster counts.
  const doughnutSegments = useMemo(
    () => (data?.clusters ? buildDoughnutSegments(reviewed ? data.clusters.filter((group) => group.thesis_count > 0) : data.clusters, isDark) : []),
    [data, isDark, reviewed]
  );

  // ── Cluster drill-down resolution ───────────────────────────────────
  // `cluster_id` is NOT stable across corpus changes (groups are recomputed
  // whenever the approved corpus changes; a URL carrying it is a session
  // reference, not a bookmark —
  // see topic_analysis.py notes). Resolve it against the currently-loaded
  // `data.clusters` on every render rather than trusting it blindly; a
  // stale/unknown value simply fails to resolve and the overview renders
  // with a brief notice instead of crashing or showing wrong data.
  const clusterParam = reviewed ? searchParams.get('subject') : searchParams.get('cluster');
  const resolvedClusterIndex = useMemo(() => {
    if (clusterParam === null || !data?.clusters) return -1;
    return data.clusters.findIndex((c) => String(c.cluster_id) === clusterParam);
  }, [clusterParam, data]);
  const resolvedCluster = resolvedClusterIndex >= 0 ? data.clusters[resolvedClusterIndex] : null;
  const clusterIdStale = clusterParam !== null && !!data?.clusters && resolvedClusterIndex === -1;
  const hasDetailParam = searchParams.has('subject') || searchParams.has('cluster');
  const showOverviewChrome = !hasDetailParam || (!loading && !error && Boolean(data) && !resolvedCluster);

  return (
    <LazyMotion features={domAnimation}>
    <div className={`min-h-screen bg-canvas`}>
      <AppNavbar activePage="trends" />

      <PageShell>
        {/* ── Header ──────────────────────────────────────────────── */}
        <PageHeader title="Topic Trend Analysis">
          {showOverviewChrome && (
            <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              {reviewed ? 'Group-reviewed research subjects across approved theses.' : 'Explore groups of theses with similar meaning. Group names come from reviewed subjects; tags show the technologies each thesis uses.'}
            </p>
          )}
        </PageHeader>

        {reviewedEnabled && showOverviewChrome && (
          <nav aria-label="Topic analysis views" className="flex flex-wrap gap-2 mb-8">
            <Link to="/trend-analysis" aria-current={reviewed ? 'page' : undefined}
              className={`rounded-lg px-4 py-2 text-sm font-semibold border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${reviewed ? 'bg-blue-600 border-blue-600 text-white' : isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'}`}>
              Reviewed subjects
            </Link>
            <Link to="/trend-analysis?view=clusters" aria-current={!reviewed ? 'page' : undefined}
              className={`rounded-lg px-4 py-2 text-sm font-semibold border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${!reviewed ? 'bg-blue-600 border-blue-600 text-white' : isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'}`}>
              Explore text clusters
            </Link>
          </nav>
        )}

        {showOverviewChrome && <TopicCheck isDark={isDark} />}

        {/* ── Loading / Error ─────────────────────────────────────── */}
        {loading ? (
          <div className="space-y-6">
            <p className={`text-xs mb-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              {subjectLoading ? 'Loading trend analysis…' : reviewed ? 'Loading reviewed subjects…' : 'Loading text clusters…'}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-6">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="thesys-panel p-4">
                  <div className="thesys-skeleton h-3 w-20 mb-3" />
                  <div className="thesys-skeleton h-8 w-12 mb-2" />
                  <div className="thesys-skeleton h-3 w-16" />
                </div>
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {[0, 1].map((i) => (
                <div key={i} className={`thesys-panel p-5 ${i === 1 ? 'lg:col-span-2' : ''}`}>
                  <div className="thesys-skeleton h-3 w-24 mb-5" />
                  <div className="space-y-2.5">
                    {Array.from({ length: 5 }).map((_, j) => (
                      <div key={j} className="thesys-skeleton h-3 w-full" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : error ? (
          <div className={`rounded-xl p-8 text-center ${isDark ? 'bg-rose-500/10 text-rose-300' : 'bg-rose-50 text-rose-700'}`}>
            {error}
          </div>
        ) : data && data.status === 'empty' ? (
          <div className="thesys-empty">
            <BarChart3 className="w-10 h-10 text-primary" aria-hidden="true" />
            <p className={`font-semibold ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
              {reviewed ? 'No reviewed subjects yet.' : 'Not enough approved theses yet.'}
            </p>
            <p className={`text-sm max-w-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              {reviewed ? 'Approved theses remain in the repository while faculty or administrators review their subjects.' : 'Add more theses to generate meaningful topic clusters. At least a few approved theses are needed for clustering to work.'}
            </p>
          </div>
        ) : data && resolvedCluster ? (
          /* ── Cluster drill-down — replaces the overview entirely ──── */
          <ClusterDetailView
            cluster={resolvedCluster}
            isDark={isDark}
            paletteColor={colourFor(resolvedClusterIndex)}
            reviewed={reviewed}
            fromThesisDetail={Boolean(location.state?.fromThesisDetail && location.state?.thesisId)}
          />
        ) : data ? (
          <>
            {clusterIdStale && (
              <div className={`rounded-lg px-4 py-3 mb-6 text-sm ${
                isDark ? 'bg-amber-500/10 text-amber-300 border border-amber-500/25' : 'bg-amber-50 text-amber-700 border border-amber-200'
              }`}>
                {reviewed
                  ? 'That reviewed subject is no longer available. Showing the current overview.'
                  : 'That topic cluster is no longer available — clusters are recomputed as the repository changes. Showing the current overview instead.'}
              </div>
            )}

            {/* ── Stat metrics — open, de-boxed ────────────────────── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-8 gap-y-6 mb-12">
              {reviewed ? (
                <>
                  <StatCard label="Approved" value={subjectData.approved_count} sublabel="Published theses" isDark={isDark} />
                  <StatCard label="Reviewed" value={subjectData.reviewed_count} sublabel="In subject charts" isDark={isDark} />
                  <StatCard label="Awaiting review" value={subjectData.awaiting_review_count} sublabel="Still in repository" isDark={isDark} />
                  <StatCard label="Subjects" value={data.total_topics} sublabel="Group-approved definitions" isDark={isDark} />
                </>
              ) : (
                <>
                  <StatCard label="Total Theses" value={data.total_theses} sublabel="Approved corpus" isDark={isDark} />
                  <StatCard label="Total Topics" value={data.total_topics} sublabel="Groups by meaning" isDark={isDark} />
                  <StatCard label="Saturated" value={data.saturated_count} sublabel="High relative volume" isDark={isDark} accent={isDark ? '#f87171' : '#e11d48'} />
                  <StatCard label="Underexplored" value={data.underexplored_count} sublabel="Low relative volume" isDark={isDark} accent={isDark ? '#34d399' : '#059669'} />
                </>
              )}
            </div>

            {/* ── Charts row — open on canvas ──────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-x-10 gap-y-12 mb-12">
              <section>
                <h2 className={`text-sm font-semibold pb-2 mb-5 border-b border-[var(--color-border-subtle)] ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                  {reviewed ? 'Subject distribution' : 'Topic Distribution'}
                </h2>
                <DoughnutChart segments={doughnutSegments} isDark={isDark} />
                <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1.5 justify-center">
                  {doughnutSegments.map((s) => (
                    <div key={s.id} className="flex items-center gap-1.5">
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: s.color }}
                        aria-hidden="true"
                      />
                      <span
                        className={`text-xs truncate max-w-[8rem] ${isDark ? 'text-gray-400' : 'text-gray-600'}`}
                        title={s.topic}
                      >
                        {s.topic}
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="lg:col-span-2">
                <h2 className={`text-sm font-semibold pb-2 mb-5 border-b border-[var(--color-border-subtle)] ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                  {reviewed ? 'Theses per subject' : 'Theses per Topic'}
                </h2>
                <CountsBarChart clusters={data.clusters} isDark={isDark} />
              </section>
            </div>

            {/* ── Cluster cards ────────────────────────────────────── */}
            <div className="mb-6">
              <h2
                className={`text-sm font-semibold uppercase tracking-wider mb-3 ${
                  isDark ? 'text-gray-400' : 'text-gray-600'
                }`}
              >
                {reviewed ? 'Reviewed subjects' : 'Topic Clusters'} ({data.clusters.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.clusters.map((c, idx) => (
                  <ClusterCard
                    key={c.cluster_id}
                    cluster={c}
                    isDark={isDark}
                    paletteColor={colourFor(idx)}
                    reviewed={reviewed}
                  />
                ))}
              </div>
            </div>

            {/* ── How this works ───────────────────────────────────── */}
            <section>
              <h3 className={`text-sm font-semibold pb-2 mb-4 border-b border-[var(--color-border-subtle)] ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                How this works
              </h3>
              <p className={`text-sm leading-relaxed mb-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                {reviewed
                  ? 'Faculty and administrators confirm one primary research subject for each thesis. Only approved theses with a confirmed subject appear in these charts. Theses awaiting subject review remain published in the repository.'
                  : 'Exploratory groups put approved theses with similar meaning together, using Sentence-BERT vectors of their titles, keywords and abstracts. Each group is named after its members’ confirmed research subjects; technology tags such as IoT or AI appear only when a thesis actually uses that technology. Groups may change as the corpus changes.'}
              </p>
              <ul className={`text-xs space-y-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                <li><strong>Saturated</strong> — at least 1.5 times the average {reviewed ? 'subject' : 'cluster'} count.</li>
                <li><strong>Emerging</strong> — between the high- and low-count thresholds.</li>
                <li><strong>Underexplored</strong> — at most half the average {reviewed ? 'subject' : 'cluster'} count.</li>
              </ul>
              <p className={`text-xs italic mt-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                These labels compare relative thesis counts. They do not measure growth over time.
              </p>
            </section>
          </>
        ) : null}
      </PageShell>
    </div>
    </LazyMotion>
  );
}
