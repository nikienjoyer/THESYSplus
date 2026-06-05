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
import { Link } from 'react-router-dom';
import { BarChart3 } from 'lucide-react';
import client from '../api/client';
import { registerCacheClearer } from '../utils/appCaches';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import AppNavbar from '../components/layout/AppNavbar';
import { Badge } from '../components/shadcn/badge';
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


// ---------------------------------------------------------------------------
// Doughnut — topic distribution
// ---------------------------------------------------------------------------

function DoughnutChart({ clusters, isDark }) {
  const total = clusters.reduce((sum, c) => sum + c.thesis_count, 0);
  if (total === 0) return null;

  const radius = 60;
  const stroke = 22;
  const circumference = 2 * Math.PI * radius;
  let cumulative = 0;

  return (
    <div className="flex items-center justify-center">
      <svg
        viewBox="0 0 160 160"
        className="w-44 h-44 -rotate-90"
        aria-label="Topic distribution"
      >
        {/* Background ring */}
        <circle
          cx="80" cy="80" r={radius}
          fill="none" stroke={isDark ? '#1e293b' : '#e5e7eb'}
          strokeWidth={stroke}
        />
        {clusters.map((c, idx) => {
          const fraction = c.thesis_count / total;
          const dash = fraction * circumference;
          const offset = -((cumulative / total) * circumference);
          cumulative += c.thesis_count;
          return (
            <circle
              key={c.cluster_id}
              cx="80" cy="80" r={radius}
              fill="none"
              stroke={CLUSTER_PALETTE[idx % CLUSTER_PALETTE.length]}
              strokeWidth={stroke}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={offset}
              strokeLinecap="butt"
            >
              <title>{`${c.topic} — ${c.thesis_count} thes${c.thesis_count === 1 ? 'is' : 'es'}`}</title>
            </circle>
          );
        })}
        {/* Center label */}
        <g transform="rotate(90, 80, 80)">
          <text
            x="80" y="74" textAnchor="middle"
            className={`font-bold ${isDark ? 'fill-white' : 'fill-gray-900'}`}
            style={{ fontSize: '22px' }}
          >
            {total}
          </text>
          <text
            x="80" y="92" textAnchor="middle"
            className={isDark ? 'fill-gray-400' : 'fill-gray-500'}
            style={{ fontSize: '10px', letterSpacing: '0.1em' }}
          >
            THESES
          </text>
        </g>
      </svg>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Bar — thesis count per topic
// ---------------------------------------------------------------------------

function CountsBarChart({ clusters, isDark }) {
  if (clusters.length === 0) return null;
  const max = Math.max(...clusters.map((c) => c.thesis_count), 1);

  return (
    <div className="space-y-2">
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
              <div
                className="h-full transition-all duration-300"
                style={{ width: `${pct}%`, backgroundColor: color }}
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
    </div>
  );
}


// ---------------------------------------------------------------------------
// Stat card — shadcn Card
// ---------------------------------------------------------------------------

function StatCard({ label, value, sublabel, isDark, accent }) {
  return (
    <div className="thesys-panel">
      <div className={`text-xs font-semibold uppercase tracking-wider mb-2 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
        {label}
      </div>
      <div
        className={`text-2xl sm:text-3xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
      {sublabel && (
        <div className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
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
  const styles = trendStyles(cluster.trend, isDark);
  return (
    <article className="thesys-panel thesys-card-lift">
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
            <div className={`text-xs font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
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
            <div className={`text-xs font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
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
    </article>
  );
}


// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TrendAnalysisPage() {
  const { theme } = useTheme();
  const { isAuthenticated, isInitializing } = useAuth();
  const isDark = theme === 'dark';

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

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      <AppNavbar activePage="trends" breadcrumb="Trend Analysis" />

      <main className="max-w-6xl mx-auto px-5 sm:px-10 py-8">
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="mb-6">
          <h1 className={`text-2xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
            Topic Trend Analysis
          </h1>
          <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
            AI-powered topic clustering and trend identification using TF-IDF + K-Means.
          </p>
        </div>

        {/* ── Loading / Error ─────────────────────────────────────── */}
        {loading ? (
          <div className="space-y-6">
            <p className={`text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
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
            <p className={`text-sm max-w-sm ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              Add more theses to generate meaningful topic clusters. At least a few approved theses are needed for clustering to work.
            </p>
          </div>
        ) : data ? (
          <>
            {/* ── Stat cards ───────────────────────────────────────── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-6">
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
                sublabel="≥ 5 studies"
                isDark={isDark}
                accent={isDark ? '#f87171' : '#e11d48'}
              />
              <StatCard
                label="Underexplored"
                value={data.underexplored_count}
                sublabel="Single study"
                isDark={isDark}
                accent={isDark ? '#34d399' : '#059669'}
              />
            </div>

            {/* ── Charts row ───────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
              <div className="thesys-panel">
                <div className={`text-xs font-semibold uppercase tracking-wider mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  Topic Distribution
                </div>
                <DoughnutChart clusters={data.clusters} isDark={isDark} />
                <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1.5 justify-center">
                  {data.clusters.map((c, idx) => (
                    <div key={c.cluster_id} className="flex items-center gap-1.5">
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: colourFor(idx) }}
                        aria-hidden="true"
                      />
                      <span
                        className={`text-xs truncate max-w-[8rem] ${isDark ? 'text-gray-400' : 'text-gray-600'}`}
                        title={c.topic}
                      >
                        {c.topic}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="thesys-panel lg:col-span-2">
                <div className={`text-xs font-semibold uppercase tracking-wider mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  Theses per Topic
                </div>
                <CountsBarChart clusters={data.clusters} isDark={isDark} />
              </div>
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
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.clusters.map((c, idx) => (
                  <ClusterCard
                    key={c.cluster_id}
                    cluster={c}
                    isDark={isDark}
                    paletteColor={colourFor(idx)}
                  />
                ))}
              </div>
            </div>

            {/* ── How this works ───────────────────────────────────── */}
            <div className="thesys-panel">
              <h3 className={`text-sm font-semibold uppercase tracking-wider mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
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
              <ul className={`text-xs space-y-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                <li>🔴 <strong>Saturated</strong> — 5 or more studies in a cluster (well-explored research area)</li>
                <li>🟡 <strong>Emerging</strong> — 2–4 studies (active but not yet saturated)</li>
                <li>🟢 <strong>Underexplored</strong> — single study (potential research gap)</li>
              </ul>
            </div>
          </>
        ) : null}
      </main>
    </div>
  );
}
