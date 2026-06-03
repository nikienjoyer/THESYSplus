/**
 * AnalyticsDashboardPage — Phase 3B repository intelligence dashboard.
 *
 * Route: /analytics
 *
 * Sections:
 *   1. Overview cards   — Total Theses · Semantic Ready · Most Active Program · Recent Uploads
 *   2. Program chart    — Horizontal bar chart: theses per program
 *   3. Growth chart     — Line/bar chart: theses per year (last 10 years)
 *   4. Top keywords     — Horizontal bar chart
 *   5. Trend summary    — Compact EMERGING / SATURATED / UNDEREXPLORED summary
 *                         (reuses results from existing analyze_topics call on the server)
 *
 * Intentional separation from /trend-analysis:
 *   Trend Analysis = AI interpretation (TF-IDF + K-Means clusters)
 *   Analytics      = Repository intelligence (counts, distributions, growth)
 *
 * Charts are inline SVG — no external chart library, consistent with TrendAnalysisPage.
 *
 * Performance:
 *   - Module-level memory cache with a 5-minute TTL.
 *   - On mount, cached data is rendered immediately (no skeleton on revisit).
 *   - A background refresh runs silently and updates state when it completes.
 *   - Full skeleton is shown only on the very first load with no cached data.
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BarChart3 } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import AppNavbar from '../components/layout/AppNavbar';
import { Tooltip, TooltipTrigger, TooltipContent } from '../components/shadcn/tooltip';


// ---------------------------------------------------------------------------
// Module-level memory cache — 5-minute TTL, single slot for analytics
// ---------------------------------------------------------------------------
const ANALYTICS_CACHE_TTL = 5 * 60 * 1000;
let analyticsCache = null; // { data, ts }

function getAnalyticsCached() {
  if (!analyticsCache) return null;
  if (Date.now() - analyticsCache.ts > ANALYTICS_CACHE_TTL) { analyticsCache = null; return null; }
  return analyticsCache.data;
}

function setAnalyticsCache(data) {
  analyticsCache = { data, ts: Date.now() };
}


// ---------------------------------------------------------------------------
// Palette — consistent with TrendAnalysisPage
// ---------------------------------------------------------------------------
const PALETTE = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b',
  '#10b981', '#06b6d4', '#ef4444', '#84cc16',
];


// ---------------------------------------------------------------------------
// Inline SVG charts
// ---------------------------------------------------------------------------

function HBarChart({ data, keyField, valueField, isDark, maxBars = 10 }) {
  if (!data || data.length === 0) return null;
  const items = data.slice(0, maxBars);
  const maxVal = Math.max(...items.map((d) => d[valueField]), 1);
  return (
    <div className="space-y-2">
      {items.map((d, idx) => {
        const pct = (d[valueField] / maxVal) * 100;
        return (
          <div key={d[keyField]} className="flex items-center gap-3">
            <span
              className={`text-xs font-medium truncate w-36 sm:w-48 flex-shrink-0 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}
              title={d[keyField]}
            >
              {d[keyField]}
            </span>
            <div className={`flex-1 h-3 rounded-full overflow-hidden ${isDark ? 'bg-white/[0.05]' : 'bg-gray-100'}`}>
              <div
                className="h-full transition-all duration-300"
                style={{ width: `${pct}%`, backgroundColor: PALETTE[idx % PALETTE.length] }}
              />
            </div>
            <span className={`text-xs tabular-nums w-6 text-right flex-shrink-0 font-semibold ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              {d[valueField]}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function YearBarChart({ data, isDark }) {
  if (!data || data.length === 0) return null;
  const maxVal = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="flex items-end gap-1 sm:gap-2 h-28 w-full">
      {data.map((d, idx) => {
        const heightPct = (d.count / maxVal) * 100;
        return (
          <div key={d.year} className="flex flex-col items-center flex-1 min-w-0">
            <span className={`text-[9px] mb-0.5 font-semibold ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              {d.count}
            </span>
            <div
              className="w-full rounded-t-sm transition-all duration-300"
              style={{ height: `${Math.max(heightPct, 4)}%`, backgroundColor: PALETTE[idx % PALETTE.length] }}
              title={`${d.year}: ${d.count}`}
            />
            <span className={`text-[9px] mt-1 truncate w-full text-center ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              {String(d.year).slice(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Stat card — uses shadcn Card
// ---------------------------------------------------------------------------
function StatCard({ label, value, sublabel, isDark, accent, tooltipText }) {
  const card = (
    <div className="thesys-panel">
      <div className={`text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
        {label}
        {tooltipText && (
          <svg className="w-3 h-3 opacity-50" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/><path strokeLinecap="round" strokeLinejoin="round" d="M12 16v-4M12 8h.01"/>
          </svg>
        )}
      </div>
      <div
        className={`text-2xl sm:text-3xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}
        style={accent ? { color: accent } : undefined}
      >
        {value ?? '—'}
      </div>
      {sublabel && (
        <div className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>{sublabel}</div>
      )}
    </div>
  );

  if (!tooltipText) return card;
  return (
    <Tooltip>
      <TooltipTrigger asChild><div>{card}</div></TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs">{tooltipText}</TooltipContent>
    </Tooltip>
  );
}


// ---------------------------------------------------------------------------
// Trend summary mini-cards
// ---------------------------------------------------------------------------
function TrendSummary({ summary, isDark }) {
  if (!summary) return null;
  const items = [
    {
      key: 'emerging',
      label: 'Emerging Topics',
      count: summary.emerging_count,
      emoji: '🟡',
      chip: isDark ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' : 'bg-amber-50 text-amber-700 border-amber-200',
    },
    {
      key: 'saturated',
      label: 'Saturated Topics',
      count: summary.saturated_count,
      emoji: '🔴',
      chip: isDark ? 'bg-rose-500/15 text-rose-300 border-rose-500/30' : 'bg-rose-50 text-rose-700 border-rose-200',
    },
    {
      key: 'underexplored',
      label: 'Underexplored Areas',
      count: summary.underexplored_count,
      emoji: '🟢',
      chip: isDark ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-emerald-50 text-emerald-700 border-emerald-200',
    },
  ];
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {items.map(({ key, label, count, emoji, chip }) => (
        <div
          key={key}
          className="thesys-card p-4 flex items-center gap-3"
        >
          <span className="text-xl flex-shrink-0" aria-hidden="true">{emoji}</span>
          <div>
            <div className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{count ?? 0}</div>
            <div className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>{label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Shorten program name for display
// ---------------------------------------------------------------------------
function shortProgram(prog) {
  const map = {
    'BS Information System': 'BSIS',
    'BS Information Technology': 'BSIT',
    'BS Computer Science': 'BSCS',
    'Associate in Computer Technology': 'ACT',
  };
  return map[prog] || prog;
}


// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AnalyticsDashboardPage() {
  const { theme } = useTheme();
  const { isAuthenticated, isInitializing } = useAuth();
  const navigate = useNavigate();
  const isDark = theme === 'dark';

  // Seed state from cache immediately — avoids blank flash on revisit
  const [data, setData] = useState(() => getAnalyticsCached());
  const [loading, setLoading] = useState(() => !getAnalyticsCached());
  const [error, setError] = useState('');

  useEffect(() => {
    // Wait for auth initialization to complete before fetching.
    // This prevents a request firing with no token (causing an unnecessary
    // 401 → refresh → retry round-trip that extends the skeleton duration).
    if (isInitializing || !isAuthenticated) return;
    let cancelled = false;

    (async () => {
      // If we already have cached data, keep it visible and refresh in background
      const cached = getAnalyticsCached();
      if (!cached) {
        setLoading(true);
        setError('');
      }

      try {
        const res = await client.get('/theses/analytics/');
        if (!cancelled) {
          setAnalyticsCache(res.data);
          setData(res.data);
        }
      } catch (err) {
        // Only show error if we have nothing to display
        if (!cancelled && !cached) setError('Failed to load analytics. Please try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [isAuthenticated, isInitializing]);

  // Shorten program names for chart labels
  const programDist = (data?.program_distribution || []).map((d) => ({
    program: shortProgram(d.program),
    count: d.count,
  }));

  const keywordData = (data?.top_keywords || []).map((k) => ({
    keyword: k.keyword,
    count: k.count,
  }));

  const sectionCls = null; // replaced by shadcn Card below
  const sectionTitle = `text-xs font-semibold uppercase tracking-wider mb-4 ${isDark ? 'text-gray-500' : 'text-gray-500'}`;

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      <AppNavbar activePage="analytics" breadcrumb="Analytics" />

      <main className="max-w-6xl mx-auto px-5 sm:px-10 py-8">

        {/* Header */}
        <div className="mb-6">
          <h1 className={`text-2xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
            Repository Analytics
          </h1>
          <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
            Repository intelligence — counts, distributions, and growth insights.
          </p>
        </div>

        {/* Loading */}
        {loading && (
          <div className="space-y-6">
            <p className={`text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              Loading repository analytics…
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="thesys-panel">
                  <div className="thesys-skeleton h-3 w-20 mb-3" />
                  <div className="thesys-skeleton h-8 w-12 mb-2" />
                  <div className="thesys-skeleton h-3 w-16" />
                </div>
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {[0, 1].map((i) => (
                <div key={i} className="thesys-panel">
                  <div className="thesys-skeleton h-3 w-24 mb-5" />
                  <div className="space-y-2.5">
                    {Array.from({ length: 4 }).map((_, j) => (
                      <div key={j} className="thesys-skeleton h-3 w-full" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div className={`rounded-xl p-8 text-center ${isDark ? 'bg-rose-500/10 text-rose-300' : 'bg-rose-50 text-rose-700'}`}>
            {error}
          </div>
        )}

        {/* Empty */}
        {!loading && !error && data && data.total_theses === 0 && (
          <div className="thesys-empty">
            <BarChart3 className="w-10 h-10 text-primary" aria-hidden="true" />
            <p className={`font-semibold ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
              No analytics data available yet.
            </p>
            <p className={`text-sm max-w-sm ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              Upload and approve thesis records to generate repository insights.
            </p>
          </div>
        )}

        {/* Dashboard content */}
        {!loading && !error && data && data.total_theses > 0 && (
          <div className="space-y-6">

            {/* ── Section 1: Overview cards ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
              <StatCard
                label="Total Theses"
                value={data.total_theses}
                sublabel="all statuses"
                isDark={isDark}
              />
              <StatCard
                label="Semantic Ready"
                value={data.semantic_ready}
                sublabel="indexed for AI search"
                isDark={isDark}
                accent={isDark ? '#60a5fa' : '#2563eb'}
                tooltipText="Theses with generated SBERT embeddings that are available for semantic retrieval. A thesis becomes Semantic Ready after its embedding vector is computed."
              />
              <StatCard
                label="Most Active Program"
                value={shortProgram(data.most_active_program) || '—'}
                sublabel={data.most_active_program || ''}
                isDark={isDark}
              />
              <StatCard
                label={`Recent Uploads`}
                value={data.recent_uploads_count}
                sublabel={`last ${data.recent_uploads_days} days`}
                isDark={isDark}
                accent={
                  data.recent_uploads_count > 0
                    ? isDark ? '#34d399' : '#059669'
                    : undefined
                }
              />
              {data.pending_review_count !== null && data.pending_review_count !== undefined && (
                <StatCard
                  label="Pending Review"
                  value={data.pending_review_count}
                  sublabel="awaiting faculty approval"
                  isDark={isDark}
                  accent={
                    data.pending_review_count > 0
                      ? isDark ? '#fbbf24' : '#d97706'
                      : undefined
                  }
                />
              )}
            </div>

            {/* ── Section 2 + 3: Charts row ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="thesys-panel">
                <p className={sectionTitle}>Research by Program</p>
                <HBarChart
                  data={programDist}
                  keyField="program"
                  valueField="count"
                  isDark={isDark}
                />
              </div>

              <div className="thesys-panel">
                <p className={sectionTitle}>Research Growth by Year</p>
                <YearBarChart data={data.thesis_growth} isDark={isDark} />
              </div>
            </div>

            {/* ── Section 4: Top keywords ── */}
            {keywordData.length > 0 && (
              <div className="thesys-panel">
                <p className={sectionTitle}>Top Keywords (from thesis metadata)</p>
                <HBarChart
                  data={keywordData}
                  keyField="keyword"
                  valueField="count"
                  isDark={isDark}
                  maxBars={10}
                />
              </div>
            )}

            {/* ── Section 5: Trend summary ── */}
            <div className="thesys-panel">
              <p className={sectionTitle}>Topic Trend Summary</p>
              <p className={`text-xs mb-4 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                Derived from TF-IDF + K-Means clustering.{' '}
                <Link
                  to="/trend-analysis"
                  className={`underline ${isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}
                >
                  View full Trend Analysis →
                </Link>
              </p>
              <TrendSummary summary={data.topic_summary} isDark={isDark} />
            </div>

          </div>
        )}
      </main>
    </div>
  );
}
