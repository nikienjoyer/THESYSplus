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
import { Link, useSearchParams } from 'react-router-dom';
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

function ClusterCard({ cluster, isDark, paletteColor }) {
  const { fadeUp } = useMotionVariants();
  const styles = trendStyles(cluster.trend, isDark);
  return (
    // The whole card is a Link (not an onClick on the <article>) so the
    // drill-down gets keyboard focus, Enter activation, and middle-click
    // "open in new tab" for free. Nothing inside the card is interactive
    // (badges are plain spans/divs), so nesting them inside the <a> is
    // safe — no interactive-in-interactive violation.
    <Link to={`?cluster=${cluster.cluster_id}`} className="block">
      <article className="thesys-panel thesys-card-lift">
        {/* Entrance animation lives on this inner wrapper, not the <article>
            itself — the outer element owns the CSS hover lift (transform)
            and its own reduced-motion suppression via .thesys-card-lift in
            index.css. Animating `transform` on both the outer element (CSS
            hover) and an inner Framer Motion wrapper would fight each other;
            keeping them on separate elements avoids that entirely. */}
        <m.div variants={fadeUp}>
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
          thes{cluster.thesis_count === 1 ? 'is' : 'es'} in this cluster
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

        {cluster.sample_titles && cluster.sample_titles.length > 0 && (
          <div>
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
      </m.div>
      </article>
    </Link>
  );
}


// ---------------------------------------------------------------------------
// Cluster drill-down — one panel of thesis rows for a single cluster
// ---------------------------------------------------------------------------

/**
 * ClusterThesisRow — one row: title (line 1) + program · year (line 2).
 * Deliberately excludes status (every thesis here is APPROVED — see
 * get_topic_trends_queryset — so a badge would be redundant), authors,
 * keyword chips, and abstract. This is a purpose-built simpler layout,
 * not RepositoryPage's ThesisCard.
 */
function ClusterThesisRow({ thesis, isDark }) {
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
function ClusterDetailView({ cluster, isDark, paletteColor }) {
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
        <Link
          to="/trend-analysis"
          className={`inline-flex items-center gap-1.5 mb-4 text-sm font-medium transition-colors ${
            isDark ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Trend Analysis
        </Link>

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
          {cluster.thesis_count} thes{cluster.thesis_count === 1 ? 'is' : 'es'} in this cluster
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
          Failed to load theses for this cluster. Please try again.
        </div>
      ) : rows && rows.length === 0 ? (
        <div className="thesys-empty">
          <p className={`font-semibold ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
            No theses found for this cluster.
          </p>
        </div>
      ) : rows ? (
        <div className="thesys-panel divide-y divide-[var(--color-border-subtle)] overflow-hidden">
          {rows.map((thesis) => (
            <ClusterThesisRow key={thesis.id} thesis={thesis} isDark={isDark} />
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
  const { staggerContainer } = useMotionVariants();
  const [searchParams] = useSearchParams();

  // Seed state from cache immediately — avoids blank flash on revisit
  const [data, setData] = useState(() => getTrendsCached());
  const [loading, setLoading] = useState(() => !getTrendsCached());
  const [error, setError] = useState('');

  useEffect(() => {
    // Wait for auth initialization to complete before fetching.
    // This prevents a request firing with no token (causing an unnecessary
    // 401 → refresh → retry round-trip that extends the skeleton duration).
    if (isInitializing || !isAuthenticated) return;
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
  }, [isAuthenticated, isInitializing]);

  // Memoise palette mapping so cluster colours stay stable across re-renders
  const colourFor = useMemo(() => {
    if (!data?.clusters) return () => CHART_PALETTE[0];
    return (idx) => CLUSTER_PALETTE[idx % CLUSTER_PALETTE.length];
  }, [data]);

  // Doughnut segments — caps slices at MAX_DOUGHNUT_SLICES, grouping the tail
  // into "Other" so the ring and its legend stay readable at high cluster counts.
  const doughnutSegments = useMemo(
    () => (data?.clusters ? buildDoughnutSegments(data.clusters, isDark) : []),
    [data, isDark]
  );

  // ── Cluster drill-down resolution ───────────────────────────────────
  // `cluster_id` is NOT stable across corpus changes (K-Means reruns per
  // request; a URL carrying it is a session reference, not a bookmark —
  // see topic_analysis.py notes). Resolve it against the currently-loaded
  // `data.clusters` on every render rather than trusting it blindly; a
  // stale/unknown value simply fails to resolve and the overview renders
  // with a brief notice instead of crashing or showing wrong data.
  const clusterParam = searchParams.get('cluster');
  const resolvedClusterIndex = useMemo(() => {
    if (clusterParam === null || !data?.clusters) return -1;
    return data.clusters.findIndex((c) => String(c.cluster_id) === clusterParam);
  }, [clusterParam, data]);
  const resolvedCluster = resolvedClusterIndex >= 0 ? data.clusters[resolvedClusterIndex] : null;
  const clusterIdStale = clusterParam !== null && !!data?.clusters && resolvedClusterIndex === -1;

  return (
    <LazyMotion features={domAnimation}>
    <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      <AppNavbar activePage="trends" />

      <PageShell>
        {/* ── Header ──────────────────────────────────────────────── */}
        <PageHeader title="Topic Trend Analysis">
          <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
            AI-assisted topic clustering and trend identification using TF-IDF + K-Means.
          </p>
        </PageHeader>

        {/* ── Loading / Error ─────────────────────────────────────── */}
        {loading ? (
          <div className="space-y-6">
            <p className={`text-xs mb-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              Clustering research topics…
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
              Not enough approved theses yet.
            </p>
            <p className={`text-sm max-w-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              Add more theses to generate meaningful topic clusters. At least a few approved theses are needed for clustering to work.
            </p>
          </div>
        ) : data && resolvedCluster ? (
          /* ── Cluster drill-down — replaces the overview entirely ──── */
          <ClusterDetailView
            cluster={resolvedCluster}
            isDark={isDark}
            paletteColor={colourFor(resolvedClusterIndex)}
          />
        ) : data ? (
          <>
            {clusterIdStale && (
              <div className={`rounded-lg px-4 py-3 mb-6 text-sm ${
                isDark ? 'bg-amber-500/10 text-amber-300 border border-amber-500/25' : 'bg-amber-50 text-amber-700 border border-amber-200'
              }`}>
                That topic cluster is no longer available — clusters are
                recomputed as the repository changes. Showing the current
                overview instead.
              </div>
            )}

            {/* ── Stat metrics — open, de-boxed ────────────────────── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-8 gap-y-6 mb-12">
              <StatCard
                label="Total Theses"
                value={data.total_theses}
                sublabel="Approved corpus"
                isDark={isDark}
              />
              <StatCard
                label="Total Topics"
                value={data.total_topics}
                sublabel="K-Means clusters"
                isDark={isDark}
              />
              <StatCard
                label="Saturated"
                value={data.saturated_count}
                sublabel="High relative volume"
                isDark={isDark}
                accent={isDark ? '#f87171' : '#e11d48'}
              />
              <StatCard
                label="Underexplored"
                value={data.underexplored_count}
                sublabel="Low relative volume"
                isDark={isDark}
                accent={isDark ? '#34d399' : '#059669'}
              />
            </div>

            {/* ── Charts row — open on canvas ──────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-x-10 gap-y-12 mb-12">
              <section>
                <h2 className={`text-sm font-semibold pb-2 mb-5 border-b border-[var(--color-border-subtle)] ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                  Topic Distribution
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
                  Theses per Topic
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
                Topic Clusters ({data.clusters.length})
              </h2>
              <m.div
                className="grid grid-cols-1 md:grid-cols-2 gap-4"
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: '-80px' }}
                variants={staggerContainer}
              >
                {data.clusters.map((c, idx) => (
                  <ClusterCard
                    key={c.cluster_id}
                    cluster={c}
                    isDark={isDark}
                    paletteColor={colourFor(idx)}
                  />
                ))}
              </m.div>
            </div>

            {/* ── How this works ───────────────────────────────────── */}
            <section>
              <h3 className={`text-sm font-semibold pb-2 mb-4 border-b border-[var(--color-border-subtle)] ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                How this works
              </h3>
              <p className={`text-sm leading-relaxed mb-3 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                Topic trend analysis follows the THESYS+ research methodology:
                each approved thesis is converted into a TF-IDF vector built from
                its title, abstract, extracted text, and keywords. K-Means
                clustering groups vectors with similar vocabulary into topic
                clusters, and the highest-weight TF-IDF terms in each cluster's
                centroid become the surfaced keywords.
              </p>
              <ul className={`text-xs space-y-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                <li>🔴 <strong>Saturated</strong> — High volume (≥ 1.5x average cluster size; well-explored research area)</li>
                <li>🟡 <strong>Emerging</strong> — Active volume (near average cluster size; growing area)</li>
                <li>🟢 <strong>Underexplored</strong> — Low volume (≤ 0.5x average cluster size; potential research gap)</li>
              </ul>
              <p className={`text-xs italic mt-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                Note: Thresholds scale dynamically based on the total repository volume.
              </p>
            </section>
          </>
        ) : null}
      </PageShell>
    </div>
    </LazyMotion>
  );
}
