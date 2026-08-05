/**
 * TitleSimilarityPage — Phase 2B + title-detection enhancement.
 *
 * Two input modes (both available simultaneously):
 *   1. Manual title entry  (existing flow — unchanged)
 *   2. Upload a proposal PDF/DOCX → extract title → user edits → validate
 *
 * The SBERT validate-title endpoint and all threshold logic are untouched.
 * After validation a lightweight client-side term analysis panel shows
 * shared vs distinctive keywords (no extra backend call).
 */

import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Lightbulb, TriangleAlert, CheckCircle2, ShieldCheck } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import AppNavbar from '../components/layout/AppNavbar';
import PageShell from '../components/layout/PageShell';
import { useToast } from '../hooks/useToast';
import FileDropzone from '../components/ui/FileDropzone';

const CLASS_HIGH = 'HIGHLY_SIMILAR';
const CLASS_MODERATE = 'MODERATELY_SIMILAR';
const CLASS_LOW = 'LOW_SIMILARITY';
const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;


// ---------------------------------------------------------------------------
// Client-side term analysis — pure string, no backend call
// ---------------------------------------------------------------------------
function splitTerms(proposedTitle, matches = []) {
  const stop = new Set(['a','an','the','of','in','on','at','to','for',
    'with','by','and','or','is','are','was','be','its','this','that','from','into','as','it']);
  const tok = (s) =>
    s.toLowerCase().replace(/[^a-z\s]/g,' ').split(/\s+/).filter((w) => w.length >= 3 && !stop.has(w));
  const proposed = new Set(tok(proposedTitle));
  const corpus = new Set(matches.flatMap((m) => tok(m.title)));
  return {
    common: [...proposed].filter((t) => corpus.has(t)),
    distinctive: [...proposed].filter((t) => !corpus.has(t)),
  };
}


// ---------------------------------------------------------------------------
// Status card visuals
// ---------------------------------------------------------------------------
function statusVisuals(classification, isDark) {
  switch (classification) {
    case CLASS_HIGH:
      return {
        emoji: '🔴', label: 'Highly Similar',
        cardClass: isDark ? 'bg-rose-500/10 border-rose-500/30' : 'bg-rose-50 border-rose-200',
        textClass: isDark ? 'text-rose-300' : 'text-rose-700',
        chipClass: isDark ? 'bg-rose-500/20 text-rose-200 border-rose-500/40' : 'bg-rose-100 text-rose-800 border-rose-300',
      };
    case CLASS_MODERATE:
      return {
        emoji: '🟡', label: 'Moderately Similar',
        cardClass: isDark ? 'bg-amber-500/10 border-amber-500/30' : 'bg-amber-50 border-amber-200',
        textClass: isDark ? 'text-amber-300' : 'text-amber-700',
        chipClass: isDark ? 'bg-amber-500/20 text-amber-200 border-amber-500/40' : 'bg-amber-100 text-amber-800 border-amber-300',
      };
    case CLASS_LOW:
    default:
      return {
        emoji: '🟢', label: 'Low Similarity',
        cardClass: isDark ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-emerald-50 border-emerald-200',
        textClass: isDark ? 'text-emerald-300' : 'text-emerald-700',
        chipClass: isDark ? 'bg-emerald-500/20 text-emerald-200 border-emerald-500/40' : 'bg-emerald-100 text-emerald-800 border-emerald-300',
      };
  }
}


// ---------------------------------------------------------------------------
// Match card
// ---------------------------------------------------------------------------
function MatchCard({ match, isDark }) {
  const pct = ((match.similarity ?? 0) * 100).toFixed(1);
  return (
    <Link
      to={`/repository/${match.id}`}
      className="thesys-card thesys-card-lift p-4 block"
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className={`font-semibold text-sm leading-snug line-clamp-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
          {match.title}
        </h3>
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border whitespace-nowrap flex-shrink-0 ${
          isDark ? 'bg-blue-500/15 text-blue-300 border-blue-500/30' : 'bg-blue-50 text-blue-700 border-blue-200'
        }`}>
          {pct}% Match
        </span>
      </div>
      <div className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
        {match.program} · {match.year}
        {match.authors?.length > 0 && (
          <> · {match.authors.slice(0, 2).join(', ')}{match.authors.length > 2 ? '…' : ''}</>
        )}
      </div>
    </Link>
  );
}


// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function TitleSimilarityPage() {
  const { theme } = useTheme();
  const { isAuthenticated } = useAuth();
  const { toast } = useToast();
  const isDark = theme === 'dark';
  const fileInputRef = useRef(null);

  // Existing validation state — untouched
  const [title, setTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  // Upload / extraction state — new
  const [uploadFile, setUploadFile] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [extractMsg, setExtractMsg] = useState('');
  const [extractConf, setExtractConf] = useState('');
  const [uploadError, setUploadError] = useState('');

  // ── Existing validate submit (completely unchanged) ──────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (trimmed.length < 5) { setError('Please enter a title with at least 5 characters.'); return; }
    setError(''); setSubmitting(true); setResult(null);
    try {
      const res = await client.post('/theses/validate-title/', { title: trimmed });
      setResult(res.data);
    } catch (err) {
      const code = err?.response?.data?.error?.code;
      const msg = err?.response?.data?.error?.message;
      if (code === 'TITLE_TOO_SHORT') setError('Title must be at least 5 characters.');
      else if (code === 'TITLE_TOO_LONG') setError('Title must not exceed 500 characters.');
      else {
        setError(msg || 'Validation failed. Please try again.');
        toast.error(msg || 'Title validation failed. Please try again.');
      }
    } finally { setSubmitting(false); }
  };

  const handleReset = () => {
    setResult(null); setError(''); setTitle('');
    setUploadFile(null); setExtractMsg(''); setExtractConf(''); setUploadError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Upload: file selection ────────────────────────────────────────
  const handleFileChange = (e) => {
    const f = e.target.files?.[0] || null;
    setUploadError(''); setExtractMsg(''); setExtractConf('');
    if (!f) { setUploadFile(null); return; }
    const ext = f.name.toLowerCase().split('.').pop();
    if (ext !== 'pdf' && ext !== 'docx') {
      setUploadError('Only PDF and DOCX files are accepted.');
      setUploadFile(null); e.target.value = ''; return;
    }
    if (f.size > MAX_UPLOAD_BYTES) {
      setUploadError('File size must be less than 25 MB.');
      setUploadFile(null); e.target.value = ''; return;
    }
    setUploadFile(f);
  };

  // ── Upload: extract title from document ──────────────────────────
  const handleExtract = async () => {
    if (!uploadFile) return;
    setExtracting(true); setUploadError(''); setExtractMsg(''); setExtractConf('');
    try {
      const fd = new FormData();
      fd.append('file', uploadFile);
      const res = await client.post('/theses/extract-title/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const { detected_title, confidence, message } = res.data;
      setExtractMsg(message); setExtractConf(confidence);
      if (detected_title) { setTitle(detected_title); setError(''); }
    } catch (err) {
      const code = err?.response?.data?.error?.code;
      const msg = err?.response?.data?.error?.message;
      if (code === 'FILE_TYPE_NOT_ALLOWED') setUploadError('Only PDF and DOCX files are accepted.');
      else if (code === 'FILE_TOO_LARGE') setUploadError('File size must be less than 15 MB.');
      else setUploadError(msg || 'Could not extract title. Please type the title manually.');
    } finally { setExtracting(false); }
  };

  const visuals = result ? statusVisuals(result.classification, isDark) : null;
  // One decimal place so the displayed score matches threshold filtering behaviour.
  const pct = result ? ((result.similarity_score ?? 0) * 100).toFixed(1) : '0.0';
  const { common: commonTerms, distinctive: distinctiveTerms } =
    result ? splitTerms(result.query || title, result.matches || []) : { common: [], distinctive: [] };

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      <AppNavbar activePage="similarity" />

      <PageShell>

        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="mb-6">
          <h1 className={`text-2xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
            Title Similarity Validation
          </h1>
          <p className={`text-sm flex items-center gap-2 flex-wrap ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
            <span>Validate proposed thesis titles using AI-assisted semantic comparison.</span>
            <span className={isDark ? 'text-gray-600' : 'text-gray-300'}>·</span>
            <span className={`inline-flex items-center gap-1 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
              </svg>
              Powered by SBERT semantic comparison
            </span>
          </p>
        </div>

        {/* Two-column portal layout: form (left) + methodology rail (right) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          {/* LEFT — form + results */}
          <div className="lg:col-span-2">

        {/* ── Input form ──────────────────────────────────────────── */}
        <form
          onSubmit={handleSubmit}
          className="space-y-5 mb-6"
        >
          {/* Option 1: Manual title input — bare section, no card */}
          <div>
            <label
              htmlFor="proposed-title"
              className={`text-sm font-semibold mb-1 flex items-center gap-2 ${isDark ? 'text-gray-200' : 'text-gray-800'}`}
            >
              <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold flex-shrink-0 ${
                isDark ? 'bg-blue-500/20 text-blue-300' : 'bg-blue-100 text-blue-700'
              }`}>1</span>
              Enter Title Manually
            </label>
            <p className={`text-xs mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              Use this if you already know your proposed thesis title.
            </p>
            <input
              id="proposed-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={submitting}
              minLength={5}
              maxLength={500}
              placeholder="Enter your proposed thesis title..."
              className={`w-full px-4 py-3 rounded-lg border text-sm outline-none transition-colors ${
                isDark
                  ? 'bg-white/[0.04] border-white/10 text-gray-200 placeholder-gray-500 focus:border-blue-500/40'
                  : 'bg-white border-gray-200 text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100'
              }`}
              autoFocus
            />
          </div>

          {/* OR divider — the two methods are mutually exclusive choices */}
          <div className="flex items-center gap-3" aria-hidden="true">
            <span className={`flex-1 h-px ${isDark ? 'bg-white/10' : 'bg-gray-200'}`} />
            <span className={`text-[11px] font-semibold uppercase tracking-wider ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>or</span>
            <span className={`flex-1 h-px ${isDark ? 'bg-white/10' : 'bg-gray-200'}`} />
          </div>

          {/* Option 2: Upload proposal document — bare section, no card */}
          <div>
            <p className={`text-sm font-semibold mb-1 flex items-center gap-2 ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
              <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold flex-shrink-0 ${
                isDark ? 'bg-blue-500/20 text-blue-300' : 'bg-blue-100 text-blue-700'
              }`}>2</span>
              Upload Proposal Document
            </p>
            <p className={`text-xs mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              Upload a PDF or DOCX proposal to auto-detect the thesis title. Review and edit the detected title before validating.
            </p>

            <FileDropzone
              file={uploadFile}
              onFileSelect={(f) => { setUploadFile(f); setUploadError(''); setExtractMsg(''); setExtractConf(''); }}
              onRemove={() => {
                setUploadFile(null); setExtractMsg(''); setExtractConf(''); setUploadError('');
                if (fileInputRef.current) fileInputRef.current.value = '';
              }}
              disabled={submitting || extracting}
              idleTitle="Drag & drop your proposal"
            />

            {uploadFile && (
              <button
                type="button"
                onClick={handleExtract}
                disabled={extracting || submitting}
                className={`mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors disabled:opacity-50 ${
                  isDark
                    ? 'border-blue-500/40 bg-blue-500/15 text-blue-300 hover:bg-blue-500/25'
                    : 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100'
                }`}
              >
                {extracting ? <><Spinner />Extracting title from document…</> : 'Extract Title'}
              </button>
            )}

            {uploadError && (
              <p className={`text-xs mt-2 ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{uploadError}</p>
            )}
            {extractMsg && !uploadError && (
              <div className={`mt-2 rounded-lg px-3 py-2 text-xs border ${
                extractConf === 'high'
                  ? isDark
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-emerald-50 border-emerald-200 text-emerald-700'
                  : extractConf === 'medium'
                  ? isDark
                    ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                    : 'bg-amber-50 border-amber-200 text-amber-700'
                  : isDark
                  ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                  : 'bg-rose-50 border-rose-200 text-rose-700'
              }`}>
                {extractConf === 'low' ? (
                  <>
                    <p className="font-semibold mb-1 flex items-center gap-1.5"><TriangleAlert className="w-3.5 h-3.5" aria-hidden="true" /> Low Confidence Detection</p>
                    <p className="mb-0.5">This file may not contain a title page.</p>
                    <p className="mb-1">The detected text may be a chapter heading or section title.</p>
                    <p className={isDark ? 'text-rose-400' : 'text-rose-600'}>Please review and edit manually.</p>
                  </>
                ) : extractConf === 'medium' ? (
                  <>
                    <p className="font-semibold mb-0.5 flex items-center gap-1.5"><TriangleAlert className="w-3.5 h-3.5" aria-hidden="true" /> Possible title detected</p>
                    <p>Please review and edit the detected title if needed.</p>
                  </>
                ) : (
                  <>
                    <span className="inline-flex items-center gap-1 font-semibold mr-1"><CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" /></span>
                    Title detected successfully.
                  </>
                )}
              </div>
            )}
            {uploadFile && !uploadError && !extractMsg && !extracting && (
              <p className={`text-xs mt-2 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                Accepted: PDF · DOCX (max 15 MB)
              </p>
            )}
          </div>

          {/* Validation error */}
          {error && (
            <div className={`rounded-lg p-3 text-sm ${
              isDark ? 'bg-rose-500/10 text-rose-300 border border-rose-500/30' : 'bg-rose-50 text-rose-700 border border-rose-200'
            }`}>
              {error}
            </div>
          )}

          {/* Standalone action row */}
          <div className={`pt-2 border-t ${isDark ? 'border-white/[0.06]' : 'border-gray-100'}`}>
            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={submitting || title.trim().length < 5}
                className="px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {submitting ? <><Spinner /> Validating…</> : 'Validate Title'}
              </button>
              {result && (
                <button
                  type="button"
                  onClick={handleReset}
                  className={`px-3 py-2.5 rounded-lg text-sm font-medium border transition-colors ${
                    isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Clear
                </button>
              )}
            </div>

            {/* Disabled-state explanation — clarifies why the button is inactive */}
            {!submitting && title.trim().length < 5 && (
              <p className={`text-xs mt-2 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                Enter or upload a title to begin validation.
              </p>
            )}
          </div>
        </form>

        {/* Loading hint */}
        {submitting && !result && (
          <div className="flex flex-col items-center py-8 gap-3">
            <Spinner />
            <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              Comparing title embeddings against the thesis corpus…
            </p>
          </div>
        )}

        {/* Loading hint lives in the left column under the form */}
        </div>{/* end left column */}

          {/* RIGHT — stacked sidebar: How this works (top) + Risk Level (below) */}
          <aside className="lg:col-span-1 flex flex-col gap-4">
            {/* How this works — always visible */}
            <div className="thesys-card p-4">
              <p className={`text-sm font-semibold mb-2 flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                <Lightbulb className="w-4 h-4 flex-shrink-0 text-primary" aria-hidden="true" />
                How this works
              </p>
              <p className={`text-xs leading-relaxed mb-3 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Title validation compares your proposed title with existing thesis records using SBERT semantic similarity. Higher scores may indicate topic overlap with existing studies.
              </p>
              <ul className={`text-xs space-y-1.5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                <li>🔴 <strong>Highly Similar</strong> — score ≥ 85%</li>
                <li>🟡 <strong>Moderately Similar</strong> — 60–84%</li>
                <li>🟢 <strong>Low Similarity</strong> — &lt; 60%</li>
              </ul>
            </div>

            {/* Risk Level — hidden until validation completes, then sits below How this works */}
            {result && visuals ? (
              <div className={`rounded-xl border p-5 ${visuals.cardClass}`}>
                <div className="flex flex-wrap items-center gap-3 mb-3">
                  <span className="text-2xl" aria-hidden="true">{visuals.emoji}</span>
                  <div>
                    <p className={`text-[10px] font-semibold uppercase tracking-wider mb-0.5 ${visuals.textClass} opacity-70`}>Risk Level</p>
                    <h2 className={`text-lg font-bold leading-none ${isDark ? 'text-white' : 'text-gray-900'}`}>{visuals.label}</h2>
                  </div>
                  <div className="ml-auto text-right">
                    <p className={`text-[10px] font-semibold uppercase tracking-wider mb-0.5 ${visuals.textClass} opacity-70`}>Similarity Score</p>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${visuals.chipClass}`}>
                      {pct}%
                    </span>
                  </div>
                </div>
                <div className={`text-[10px] font-semibold uppercase tracking-wider mb-1 ${visuals.textClass} opacity-70`}>Recommendation</div>
                <p className={`text-sm leading-relaxed ${visuals.textClass}`}>{result.recommendation}</p>
              </div>
            ) : (
              /* Result preview placeholder — keeps the sidebar balanced before validation */
              <div className={`rounded-xl border border-dashed p-6 flex flex-col items-center text-center gap-2 ${
                isDark ? 'border-white/15 bg-white/[0.02]' : 'border-gray-300 bg-gray-50/50'
              }`}>
                <ShieldCheck className={`w-7 h-7 ${isDark ? 'text-gray-600' : 'text-gray-300'}`} aria-hidden="true" />
                <p className={`text-xs font-semibold ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Awaiting validation</p>
                <p className={`text-xs leading-relaxed ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                  Your similarity risk level and score will appear here once you validate your title.
                </p>
              </div>
            )}
          </aside>
        </div>{/* end grid */}

        {/* ── Full-width results detail (below the two-column grid) ──── */}
        {result && visuals && (
          <div className="mt-6 space-y-6">
            {/* Related Existing Studies */}
            {result.matches?.length > 0 && (
              <div>
                <h3 className={`text-sm font-semibold uppercase tracking-wider mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                  Related Existing Studies
                </h3>
                <p className={`text-xs mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  {result.matches.length} thes{result.matches.length === 1 ? 'is' : 'es'} with similar semantic content found in the repository.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {result.matches.map((m) => <MatchCard key={m.id} match={m} isDark={isDark} />)}
                </div>
              </div>
            )}

            {/* Term analysis panel (client-side TF-IDF explainability) */}
            {(commonTerms.length > 0 || distinctiveTerms.length > 0) && (
              <div className={`rounded-xl border p-5 ${isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-gray-200'}`}>
                <h3 className={`text-sm font-semibold uppercase tracking-wider mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                  Term Analysis
                </h3>
                <p className={`text-xs mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  Terms shared with similar theses vs. terms unique to your proposed title.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {commonTerms.length > 0 && (
                    <div>
                      <p className={`text-[10px] font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                        Shared terms
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {commonTerms.map((t) => (
                          <span key={t} className={`text-[11px] px-2 py-0.5 rounded-md ${
                            isDark ? 'bg-amber-500/10 text-amber-300 border border-amber-500/20' : 'bg-amber-50 text-amber-700 border border-amber-100'
                          }`}>{t}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {distinctiveTerms.length > 0 && (
                    <div>
                      <p className={`text-[10px] font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                        Distinctive terms
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {distinctiveTerms.map((t) => (
                          <span key={t} className={`text-[11px] px-2 py-0.5 rounded-md ${
                            isDark ? 'bg-blue-500/10 text-blue-300 border border-blue-500/20' : 'bg-blue-50 text-blue-700 border border-blue-100'
                          }`}>{t}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </PageShell>
    </div>
  );
}
