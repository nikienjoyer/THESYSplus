/**
 * TitleSimilarityPage — Phase 2B + segmented-control redesign.
 *
 * One shared `title` field, reached through either of two panels behind a
 * segmented control:
 *   1. "Type a title"   — manual entry
 *   2. "Upload Title"   — attach a PDF/DOCX; the title is extracted
 *                          automatically (no button) and stays editable
 *                          inline, in this same panel.
 *
 * The SBERT validate-title endpoint, the classification thresholds, and
 * splitTerms() are untouched. This file only restructures presentation.
 */

import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { LazyMotion, domAnimation, m, AnimatePresence } from 'framer-motion';
import { ChevronDown, Lightbulb, ShieldCheck } from 'lucide-react';
import client from '../api/client';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import AppNavbar from '../components/layout/AppNavbar';
import PageShell from '../components/layout/PageShell';
import { useToast } from '../hooks/useToast';
import FileDropzone from '../components/ui/FileDropzone';
import { MAX_UPLOAD_MB } from '../lib/upload';
import { useMotionVariants, DURATION, EASE_OUT } from '../lib/motion';

const CLASS_HIGH = 'HIGHLY_SIMILAR';
const CLASS_MODERATE = 'MODERATELY_SIMILAR';
const CLASS_LOW = 'LOW_SIMILARITY';

// Mirrors theses/services/title_similarity.py THRESHOLD_HIGH / THRESHOLD_MODERATE
// (0.85 / 0.60). Not imported — the frontend has no shared module for backend
// constants — but centralised HERE so the legend text is generated from one
// place instead of a second hand-typed copy of the manuscript's cut-offs.
const THRESHOLD_HIGH = 0.85;
const THRESHOLD_MODERATE = 0.60;
const HIGH_PCT = Math.round(THRESHOLD_HIGH * 100);
const MODERATE_PCT = Math.round(THRESHOLD_MODERATE * 100);

const EXTRACTION_TIMEOUT_MS = 30_000;

// Per-field confidence copy — identical values to UploadThesisModal's
// CONFIDENCE_UI, so the two surfaces agree. High confidence has no entry on
// purpose: a high-confidence result renders no indicator at all. Low uses
// orange, not red/rose — low confidence means the extractor is uncertain,
// not that the title is invalid; red/danger stays reserved for actual
// validation errors (the `error` block below).
const CONFIDENCE_UI = {
  medium: { tone: 'text-amber-600 dark:text-amber-400',   label: 'Please verify' },
  low:    { tone: 'text-orange-600 dark:text-orange-400', label: 'Needs review' },
};

function ConfidenceHint({ confidence }) {
  const ui = CONFIDENCE_UI[confidence];
  if (!ui) return null; // high confidence, or nothing detected yet

  return (
    <span className={`ml-2 text-[11px] font-medium normal-case tracking-normal ${ui.tone}`}>
      {ui.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Client-side term analysis — pure string, no backend call (unchanged)
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
// Risk dot — colour maps to the existing danger/warning/success semantic
// tokens (tokens.css), never to a new variable. The text label beside it is
// mandatory at every call site — risk is never colour-only.
// ---------------------------------------------------------------------------
const TONE_DOT = { danger: 'bg-danger', warning: 'bg-warning', success: 'bg-success' };

function RiskDot({ tone, className = 'w-2.5 h-2.5' }) {
  return <span className={`inline-block rounded-full flex-shrink-0 ${TONE_DOT[tone]} ${className}`} aria-hidden="true" />;
}

const TONE_CLASSES = {
  danger:  { card: 'bg-danger-bg border-danger-border',   text: 'text-danger-text',  chip: 'bg-danger-bg text-danger-text border-danger-border' },
  warning: { card: 'bg-warning-bg border-warning-border', text: 'text-warning-text', chip: 'bg-warning-bg text-warning-text border-warning-border' },
  success: { card: 'bg-success-bg border-success-border', text: 'text-success-text', chip: 'bg-success-bg text-success-text border-success-border' },
};

function statusVisuals(classification) {
  switch (classification) {
    case CLASS_HIGH:
      return { tone: 'danger', label: 'Highly Similar' };
    case CLASS_MODERATE:
      return { tone: 'warning', label: 'Moderately Similar' };
    case CLASS_LOW:
    default:
      return { tone: 'success', label: 'Low Similarity' };
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
      className="thesys-card thesys-card-lift p-4 block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className={`font-semibold text-sm leading-snug line-clamp-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
          {match.title}
        </h3>
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border whitespace-nowrap flex-shrink-0 bg-info-bg text-info-text border-info-border">
          {pct}% match
        </span>
      </div>
      <div className="text-xs text-muted">
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
  const { toast } = useToast();
  const isDark = theme === 'dark';
  const { reduceMotion, fadeUp } = useMotionVariants();

  // Segmented control — 'manual' | 'upload'. Both panels write to the SAME
  // `title` state below, which is what lets the submit gate work from
  // either panel and lets a detected title survive a tab switch.
  const [mode, setMode] = useState('manual');
  const manualTabRef = useRef(null);
  const uploadTabRef = useRef(null);

  // Shared validation state
  const [title, setTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  // Upload / extraction state
  const [uploadFile, setUploadFile] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [extractConf, setExtractConf] = useState('');
  const [uploadError, setUploadError] = useState('');
  // True only once THIS attached file's extraction has actually produced a
  // title — drives the "Auto-detected" marker and the confidence hint.
  // Reset the instant a new file is chosen so a stale marker from the
  // previous file never lingers while the new one is still being read.
  const [autoDetected, setAutoDetected] = useState(false);
  // The attached document was refused by the backend's thesis gate (e.g. a
  // Certificate of Registration). Kept separate from uploadError because it
  // must also SUPPRESS the title field and block the similarity check — a
  // rejected document must not reach a score, since the number would be
  // meaningless and the user would act on it.
  const [documentRejected, setDocumentRejected] = useState(false);

  const extractAbortRef = useRef(null);

  const cancelExtraction = () => {
    extractAbortRef.current?.abort();
    extractAbortRef.current = null;
  };

  // ── Keyboard nav for the segmented control (ARIA tablist pattern) ──────
  const handleTabKeyDown = (e) => {
    const order = ['manual', 'upload'];
    let idx = order.indexOf(mode);
    if (e.key === 'ArrowRight') idx = (idx + 1) % order.length;
    else if (e.key === 'ArrowLeft') idx = (idx - 1 + order.length) % order.length;
    else if (e.key === 'Home') idx = 0;
    else if (e.key === 'End') idx = order.length - 1;
    else return;
    e.preventDefault();
    const next = order[idx];
    setMode(next);
    (next === 'manual' ? manualTabRef : uploadTabRef).current?.focus();
  };

  // ── Validate submit — endpoint, payload and error codes unchanged ──────
  const handleSubmit = async (e) => {
    e.preventDefault();
    // Defence in depth: the submit button is disabled for a refused document,
    // but a rejected COR must not reach a similarity score by any route.
    if (mode === 'upload' && documentRejected) {
      setError('Please remove the attached document and try a thesis file.');
      return;
    }
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
    cancelExtraction();
    setResult(null); setError(''); setTitle('');
    setUploadFile(null); setExtracting(false); setExtractConf('');
    setUploadError(''); setAutoDetected(false); setDocumentRejected(false);
  };

  // ── Upload: automatic extraction on attach — no button ─────────────────
  //
  // Ported from UploadThesisModal.runExtraction: an AbortController held in
  // a ref, superseded responses ignored, failure never blocks the flow.
  const runExtraction = async (selectedFile) => {
    cancelExtraction();
    const controller = new AbortController();
    extractAbortRef.current = controller;

    setExtracting(true);
    setExtractConf('');
    setUploadError('');
    setDocumentRejected(false);

    try {
      const fd = new FormData();
      fd.append('file', selectedFile);
      const res = await client.post('/theses/extract-title/', fd, {
        headers: { 'Content-Type': undefined },
        timeout: EXTRACTION_TIMEOUT_MS,
        signal: controller.signal,
      });

      // A file replaced (or removed) mid-read must not write a stale title.
      if (extractAbortRef.current !== controller) return;

      const { detected_title, confidence } = res.data;
      if (detected_title) {
        setTitle(detected_title);
        setExtractConf(confidence || '');
        setAutoDetected(true);
        setError('');
      }
    } catch (err) {
      if (extractAbortRef.current !== controller) return;
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return;

      const code = err?.response?.data?.error?.code;
      const msg = err?.response?.data?.error?.message;
      if (code === 'NOT_A_THESIS_DOCUMENT') {
        // Show the server's reason INSTEAD of a detected title, and refuse to
        // proceed. Falling through to "type it manually" would invite the user
        // to run a similarity check on a document that has no title at all —
        // which is exactly how a class schedule scored 38.1%.
        setDocumentRejected(true);
        // The fallback is word-for-word the backend's title-check wording.
        // It only fires if the payload arrives without a message, and the user
        // must not read two different sentences for one condition depending on
        // whether that happened. Keep these in sync with
        // _not_a_thesis_response(surface=SURFACE_TITLE_CHECK) in theses/views.py.
        setUploadError(
          msg
          || 'This document does not appear to be a thesis. Please upload a '
             + 'document containing your proposed thesis or research title.',
        );
      } else if (code === 'FILE_TYPE_NOT_ALLOWED') {
        setUploadError('Only PDF and DOCX files are accepted.');
      } else if (code === 'FILE_TOO_LARGE') {
        setUploadError(`File size must be less than ${MAX_UPLOAD_MB} MB.`);
      } else {
        setUploadError(msg || 'Could not extract a title. Please type it manually below.');
      }
    } finally {
      if (extractAbortRef.current === controller) {
        extractAbortRef.current = null;
        setExtracting(false);
      }
    }
  };

  const handleFileSelect = (selected) => {
    setUploadFile(selected);
    setUploadError('');
    setAutoDetected(false); // this file hasn't produced a title yet
    setDocumentRejected(false); // a new file gets a clean verdict
    runExtraction(selected);
  };

  const handleFileRemove = () => {
    cancelExtraction();
    setExtracting(false);
    setUploadFile(null);
    setExtractConf('');
    setUploadError('');
    setAutoDetected(false);
    setDocumentRejected(false);
    // `title` is deliberately left untouched — it may hold a value the user
    // already reviewed and wants to keep even without the file attached.
  };

  const visuals = result ? statusVisuals(result.classification) : null;
  const tone = visuals ? TONE_CLASSES[visuals.tone] : null;
  // One decimal place so the displayed score matches threshold filtering behaviour.
  const pct = result ? ((result.similarity_score ?? 0) * 100).toFixed(1) : '0.0';
  const { common: commonTerms, distinctive: distinctiveTerms } =
    result ? splitTerms(result.query || title, result.matches || []) : { common: [], distinctive: [] };

  const trimmedLen = title.trim().length;

  // Upload panel's title block is state-gated: it has nothing useful to show
  // until either a document produced a title, or the user already typed one
  // under "Type a title" and switched tabs. Hidden while a new extraction is
  // in flight regardless of any stale value, and hidden for a document the
  // backend refused — the rejection reason takes its place.
  const showTitleBlock = !extracting && !documentRejected && trimmedLen > 0;

  // A refused document must never reach a similarity score. This only blocks
  // the UPLOAD panel: a title typed by hand under "Type a title" is a separate
  // input with no document behind it, so that path stays available.
  const blockedByRejectedDocument = mode === 'upload' && documentRejected;

  // Panel crossfade + small horizontal offset, gated by reduced motion.
  // DURATION.normal (150ms) — comfortably under the ~180ms ceiling for this
  // class of transition (tokens.css --duration-enter is the 200ms hard cap).
  const panelVariants = reduceMotion
    ? {
        initial: { opacity: 1, x: 0 },
        animate: { opacity: 1, x: 0, transition: { duration: 0 } },
        exit:    { opacity: 1, x: 0, transition: { duration: 0 } },
      }
    : {
        initial: { opacity: 0, x: 8 },
        animate: { opacity: 1, x: 0, transition: { duration: DURATION.normal, ease: EASE_OUT } },
        exit:    { opacity: 0, x: -8, transition: { duration: DURATION.normal, ease: EASE_OUT } },
      };

  const titleInputCls = `w-full px-4 py-3 rounded-lg border text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-blue-400 ${
    isDark
      ? 'bg-white/[0.04] border-white/10 text-gray-200 placeholder-gray-500 focus:border-blue-500/40'
      : 'bg-white border-gray-200 text-gray-700 placeholder-gray-400 focus:border-blue-400'
  }`;

  return (
    <LazyMotion features={domAnimation}>
      <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
        <AppNavbar activePage="similarity" />

        <PageShell>

          {/* ── Header ────────────────────────────────────────────────── */}
          <div className="mb-6">
            <h1 className={`text-2xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
              Title Similarity Validation
            </h1>
            <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              Validate proposed thesis titles using AI-assisted semantic comparison.
            </p>
          </div>

          {/* Two-column layout: form (left) + methodology rail (right) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* LEFT — form + results */}
            <div className="lg:col-span-2">

              <form onSubmit={handleSubmit} className="space-y-5 mb-6">

                {/* ── Segmented control ──────────────────────────────── */}
                <div
                  role="tablist"
                  aria-label="Title input method"
                  className={`inline-flex items-center gap-1 rounded-full border p-1 ${
                    isDark ? 'border-white/10 bg-white/[0.03]' : 'border-gray-200 bg-gray-100'
                  }`}
                >
                  {[
                    { key: 'manual', label: 'Type a Title', ref: manualTabRef },
                    { key: 'upload', label: 'Upload Title', ref: uploadTabRef },
                  ].map(({ key, label, ref }) => {
                    const selected = mode === key;
                    return (
                      <button
                        key={key}
                        ref={ref}
                        type="button"
                        role="tab"
                        id={`tab-${key}`}
                        aria-selected={selected}
                        aria-controls={`panel-${key}`}
                        tabIndex={selected ? 0 : -1}
                        onClick={() => setMode(key)}
                        onKeyDown={handleTabKeyDown}
                        className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                          selected
                            ? 'bg-primary text-white'
                            : isDark ? 'text-gray-400 hover:text-gray-200' : 'text-gray-600 hover:text-gray-900'
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>

                {/* ── Animated panel swap ────────────────────────────── */}
                {/* No min-h: the card follows the active panel's natural
                    height. The crossfade uses mode="wait", so the outgoing
                    panel is already at zero opacity before any resize. */}
                <div className="relative">
                  <AnimatePresence mode="wait" initial={false}>
                    {mode === 'manual' ? (
                      <m.div
                        key="manual"
                        id="panel-manual"
                        role="tabpanel"
                        aria-labelledby="tab-manual"
                        initial="initial"
                        animate="animate"
                        exit="exit"
                        variants={panelVariants}
                      >
                        <label
                          htmlFor="proposed-title"
                          className={`block text-sm font-semibold mb-1 ${isDark ? 'text-gray-200' : 'text-gray-800'}`}
                        >
                          Proposed title
                        </label>
                        <input
                          id="proposed-title"
                          type="text"
                          value={title}
                          onChange={(e) => setTitle(e.target.value)}
                          disabled={submitting}
                          minLength={5}
                          maxLength={500}
                          placeholder="Enter your proposed thesis title…"
                          className={titleInputCls}
                          autoFocus
                        />
                      </m.div>
                    ) : (
                      <m.div
                        key="upload"
                        id="panel-upload"
                        role="tabpanel"
                        aria-labelledby="tab-upload"
                        initial="initial"
                        animate="animate"
                        exit="exit"
                        variants={panelVariants}
                      >
                        <label
                          htmlFor="upload-proposal-file"
                          className={`block text-sm font-semibold mb-1 ${isDark ? 'text-gray-200' : 'text-gray-800'}`}
                        >
                          Proposal document
                        </label>

                        <FileDropzone
                          inputId="upload-proposal-file"
                          file={uploadFile}
                          onFileSelect={handleFileSelect}
                          onRemove={handleFileRemove}
                          disabled={submitting}
                          idleTitle="Drag & drop your proposal"
                          statusLoading={extracting}
                          statusText={
                            extracting ? undefined
                              : documentRejected ? 'Not a thesis document'
                              : uploadError ? 'Could not detect a title'
                              : autoDetected ? 'Title detected'
                              : undefined
                          }
                        />

                        {uploadError && (
                          <p className="text-xs mt-2 text-danger">{uploadError}</p>
                        )}

                        {/* Title field is state-gated, not always mounted: it
                            has nothing useful to show until either a document
                            has produced a title (autoDetected) or the user
                            already typed one under "Type a title" and switched
                            tabs (hasTitleValue). fadeUp covers the entrance —
                            mounting this grows the card, so it should animate
                            in rather than pop. */}
                        {showTitleBlock && (
                          <m.div
                            className="mt-3"
                            initial="hidden"
                            animate="visible"
                            variants={fadeUp}
                          >
                            <label
                              htmlFor="detected-title"
                              className={`text-xs font-semibold mb-1.5 block ${isDark ? 'text-gray-400' : 'text-gray-500'}`}
                            >
                              {autoDetected ? (
                                <>
                                  Detected title
                                  <span className={`ml-2 text-[11px] font-medium normal-case ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>
                                    Auto-detected
                                  </span>
                                  <ConfidenceHint confidence={extractConf} />
                                </>
                              ) : 'Title'}
                            </label>
                            <input
                              id="detected-title"
                              type="text"
                              value={title}
                              onChange={(e) => setTitle(e.target.value)}
                              disabled={submitting}
                              minLength={5}
                              maxLength={500}
                              className={titleInputCls.replace('py-3', 'py-2.5')}
                            />
                            {autoDetected && (
                              <p className={`text-xs mt-1 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                                Review the detected title.
                              </p>
                            )}
                          </m.div>
                        )}
                      </m.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Validation error */}
                {error && (
                  <div className="rounded-lg p-3 text-sm bg-danger-bg text-danger-text border border-danger-border">
                    {error}
                  </div>
                )}

                {/* ── Actions row ─────────────────────────────────────── */}
                <div className={`pt-2 border-t ${isDark ? 'border-white/[0.06]' : 'border-gray-100'}`}>
                  <div className="flex items-center gap-2">
                    <button
                      type="submit"
                      disabled={submitting || trimmedLen < 5 || blockedByRejectedDocument}
                      className="px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] disabled:opacity-50 transition-colors flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    >
                      {submitting ? <><Spinner /> Checking similarity…</> : 'Validate Title'}
                    </button>
                    {/* Always rendered — a control that only materialises once
                        a result exists shifts the layout. */}
                    <button
                      type="button"
                      onClick={handleReset}
                      className={`px-3 py-2.5 rounded-lg text-sm font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                        isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      Clear
                    </button>
                  </div>
                </div>
              </form>

            </div>{/* end left column */}

            {/* RIGHT — stacked sidebar: legend (top) + Risk Level (below) */}
            <aside className="lg:col-span-1 flex flex-col gap-4 lg:sticky lg:top-20 lg:self-start">
              {/* Collapsible legend — native <details>, collapsed by default */}
              <details className="thesys-card p-4 group">
                <summary className="flex items-center justify-between cursor-pointer list-none [&::-webkit-details-marker]:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-md">
                  <span className={`text-sm font-semibold flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                    <Lightbulb className="w-4 h-4 flex-shrink-0 text-primary" aria-hidden="true" />
                    How scoring works
                  </span>
                  <ChevronDown
                    className={`w-4 h-4 flex-shrink-0 transition-transform duration-150 group-open:rotate-180 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}
                    aria-hidden="true"
                  />
                </summary>

                <div className="mt-3">
                  <p className={`text-xs leading-relaxed mb-3 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Title validation compares your proposed title with existing thesis records using SBERT semantic similarity. Higher scores may indicate topic overlap with existing studies.
                  </p>
                  <ul className={`text-xs space-y-1.5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    <li className="flex items-center gap-2">
                      <RiskDot tone="danger" />
                      <span><strong>Highly Similar</strong> — score ≥ {HIGH_PCT}%</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <RiskDot tone="warning" />
                      <span><strong>Moderately Similar</strong> — {MODERATE_PCT}–{HIGH_PCT - 1}%</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <RiskDot tone="success" />
                      <span><strong>Low Similarity</strong> — &lt; {MODERATE_PCT}%</span>
                    </li>
                  </ul>
                  <p className={`mt-3 pt-3 border-t text-[11px] flex items-center gap-1.5 ${
                    isDark ? 'border-white/10 text-gray-500' : 'border-gray-100 text-gray-500'
                  }`}>
                    <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                    </svg>
                    Powered by SBERT semantic comparison
                  </p>
                </div>
              </details>

              {/* Risk Level — announced when a result lands, not visual-only */}
              {result && visuals && tone ? (
                <div
                  role="status"
                  aria-live="polite"
                  className={`rounded-xl border p-5 ${tone.card}`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <RiskDot tone={visuals.tone} className="w-3 h-3" />
                    <div>
                      <p className={`text-[10px] font-semibold uppercase tracking-wider mb-0.5 ${tone.text} opacity-70`}>Risk level</p>
                      <h2 className={`text-lg font-bold leading-none ${isDark ? 'text-white' : 'text-gray-900'}`}>{visuals.label}</h2>
                    </div>
                    <div className="ml-auto">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${tone.chip}`}>
                        {pct}%
                      </span>
                    </div>
                  </div>
                  <div className={`pt-3 border-t ${isDark ? 'border-white/10' : 'border-black/5'}`}>
                    <div className={`text-[10px] font-semibold uppercase tracking-wider mb-1 ${tone.text} opacity-70`}>Recommendation</div>
                    <p className={`text-sm leading-relaxed ${tone.text}`}>{result.recommendation}</p>
                  </div>
                </div>
              ) : (
                <div className={`rounded-xl border border-dashed p-6 flex flex-col items-center text-center gap-2 ${
                  isDark ? 'border-white/15 bg-white/[0.02]' : 'border-gray-300 bg-gray-50/50'
                }`}>
                  <ShieldCheck className={`w-7 h-7 ${isDark ? 'text-gray-600' : 'text-gray-300'}`} aria-hidden="true" />
                  <p className={`text-xs font-semibold ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Awaiting validation</p>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                    Your similarity risk level and score will appear here once you check your title.
                  </p>
                </div>
              )}
            </aside>
          </div>{/* end grid */}

          {/* Loading hint */}
          {submitting && !result && (
            <div className="flex flex-col items-center py-8 gap-3">
              <Spinner />
              <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                Comparing title embeddings against the thesis corpus…
              </p>
            </div>
          )}

          {/* ── Full-width results detail (below the two-column grid) ──── */}
          {result && visuals && (
            <div className="mt-6 space-y-6">
              {/* Related Existing Studies — all matches rendered, no expander */}
              {result.matches?.length > 0 && (
                <div>
                  <h3 className={`text-sm font-semibold uppercase tracking-wider mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Related Existing Studies
                  </h3>
                  <p className={`text-xs mb-3 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                    {result.matches.length} thes{result.matches.length === 1 ? 'is' : 'es'} with similar semantic content found in the repository.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {result.matches.map((m) => <MatchCard key={m.id} match={m} isDark={isDark} />)}
                  </div>
                </div>
              )}

              {/* Term analysis — two labelled columns of pills */}
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
    </LazyMotion>
  );
}
