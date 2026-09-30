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

import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LazyMotion, domAnimation, m, AnimatePresence } from 'framer-motion';
import { ChevronDown, Info, Lightbulb, ShieldCheck } from 'lucide-react';
import client from '../api/client';
import { waitForJob } from '../api/jobs';
import Spinner from '../components/ui/Spinner';
import AppNavbar from '../components/layout/AppNavbar';
import PageShell from '../components/layout/PageShell';
import PageHeader from '../components/layout/PageHeader';
import { useToast } from '../hooks/useToast';
import FileDropzone from '../components/ui/FileDropzone';
import { MAX_UPLOAD_MB } from '../lib/upload';
import { useMotionVariants, DURATION, EASE_OUT } from '../lib/motion';

const CLASS_HIGH = 'HIGHLY_SIMILAR';
const CLASS_MODERATE = 'MODERATELY_SIMILAR';
const CLASS_LOW = 'LOW_SIMILARITY';

// Mirrors theses/services/title_similarity.py THRESHOLD_HIGH / THRESHOLD_MODERATE
// / THRESHOLD_MEANINGFUL (0.85 / 0.60 / 0.35). Not imported — the frontend has no shared module for backend
// constants — but centralised HERE so the legend text is generated from one
// place instead of a second hand-typed copy of the manuscript's cut-offs.
const THRESHOLD_HIGH = 0.85;
const THRESHOLD_MODERATE = 0.60;
// Relevance floor — the backend drops matches below this and reports
// has_meaningful_match: false when none remain. Legend text only; the
// no-match decision itself always comes from the API flag.
const THRESHOLD_MEANINGFUL = 0.35;
const HIGH_PCT = Math.round(THRESHOLD_HIGH * 100);
const MODERATE_PCT = Math.round(THRESHOLD_MODERATE * 100);
const MEANINGFUL_PCT = Math.round(THRESHOLD_MEANINGFUL * 100);

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

// History state is written only by this page, but a stale shape from an
// older build must not crash the render — anything unexpected is ignored.
function readSavedCheck(state) {
  const saved = state?.titleCheck;
  if (!saved || typeof saved.title !== 'string' || !saved.result || typeof saved.result !== 'object') {
    return null;
  }
  return {
    mode: saved.mode === 'upload' ? 'upload' : 'manual',
    title: saved.title,
    result: saved.result,
  };
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
const TONE_DOT = { danger: 'bg-danger', warning: 'bg-warning', success: 'bg-success', neutral: 'bg-gray-400' };

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
function MatchCard({ match }) {
  const pct = ((match.similarity ?? 0) * 100).toFixed(1);
  return (
    <Link
      to={`/repository/${match.id}`}
      className="thesys-card thesys-card-lift p-4 block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className={`font-semibold text-sm leading-snug line-clamp-2 text-ink`}>
          {match.title}
        </h3>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {match.title_match && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border whitespace-nowrap bg-warning-bg text-warning-text border-warning-border">
              Title/name match
            </span>
          )}
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border whitespace-nowrap bg-info-bg text-info-text border-info-border">
            {pct}% match
          </span>
        </div>
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
  const { toast } = useToast();
  const { reduceMotion, fadeUp } = useMotionVariants();

  const location = useLocation();
  const navigate = useNavigate();
  // The last completed check, saved on this page's history entry (see
  // handleSubmit). Back from a matched thesis — which unmounts this page —
  // and a refresh restore it; a fresh navbar visit has no saved state.
  const saved = readSavedCheck(location.state);

  // Segmented control — 'manual' | 'upload'. Both panels write to the SAME
  // `title` state below, which is what lets the submit gate work from
  // either panel and lets a detected title survive a tab switch.
  const [mode, setMode] = useState(saved?.mode ?? 'manual');
  const manualTabRef = useRef(null);
  const uploadTabRef = useRef(null);

  // Shared validation state
  const [title, setTitle] = useState(saved?.title ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(saved?.result ?? null);

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
  const similarityAbortRef = useRef(null);
  const titleEditedRef = useRef(false);

  const cancelExtraction = () => {
    extractAbortRef.current?.abort();
    extractAbortRef.current = null;
  };

  const cancelSimilarityCheck = () => {
    similarityAbortRef.current?.abort();
    similarityAbortRef.current = null;
  };

  useEffect(() => () => {
    extractAbortRef.current?.abort();
    similarityAbortRef.current?.abort();
  }, []);

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
    cancelSimilarityCheck();
    const controller = new AbortController();
    similarityAbortRef.current = controller;
    setError(''); setSubmitting(true); setResult(null);
    try {
      const res = await client.post('/theses/validate-title/', { title: trimmed }, {
        signal: controller.signal,
      });
      if (similarityAbortRef.current !== controller) return;
      setResult(res.data);
      // Replace, not push: this entry now carries the result, so Back from a
      // matched thesis lands here with it instead of an empty form. The
      // uploaded file itself is not kept — only the title that was checked.
      navigate(location.pathname, {
        replace: true,
        state: { titleCheck: { mode, title: trimmed, result: res.data } },
      });
    } catch (err) {
      if (similarityAbortRef.current !== controller) return;
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return;
      const code = err?.response?.data?.error?.code;
      const msg = err?.response?.data?.error?.message;
      if (code === 'TITLE_TOO_SHORT') setError('Title must be at least 5 characters.');
      else if (code === 'TITLE_TOO_LONG') setError('Title must not exceed 500 characters.');
      else {
        setError(msg || 'Validation failed. Please try again.');
        toast.error(msg || 'Title validation failed. Please try again.');
      }
    } finally {
      if (similarityAbortRef.current === controller) {
        similarityAbortRef.current = null;
        setSubmitting(false);
      }
    }
  };

  // Editing stays available during a similarity check so it can cancel stale work.
  const handleTitleChange = (value) => {
    titleEditedRef.current = true;
    cancelSimilarityCheck();
    setSubmitting(false);
    setTitle(value);
    setResult(null);
    setError('');
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

      const extraction = res.data?.job_id
        ? await waitForJob(res.data.job_id, controller.signal)
        : res.data;
      if (extractAbortRef.current !== controller) return;
      const { detected_title, confidence } = extraction;
      if (detected_title && !titleEditedRef.current) {
        setTitle(detected_title);
        setExtractConf(confidence || '');
        setAutoDetected(true);
        setError('');
      }
    } catch (err) {
      if (extractAbortRef.current !== controller) return;
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError' || err?.name === 'AbortError') return;

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
    cancelSimilarityCheck();
    titleEditedRef.current = false;
    setUploadFile(selected);
    setTitle('');
    setResult(null);
    setError('');
    setSubmitting(false);
    setExtracting(false);
    setExtractConf('');
    setUploadError('');
    setAutoDetected(false); // this file hasn't produced a title yet
    setDocumentRejected(false); // a new file gets a clean verdict
    runExtraction(selected);
  };

  const handleFileRemove = () => {
    cancelExtraction();
    cancelSimilarityCheck();
    titleEditedRef.current = false;
    setExtracting(false);
    setSubmitting(false);
    setUploadFile(null);
    setTitle('');
    setResult(null);
    setError('');
    setExtractConf('');
    setUploadError('');
    setAutoDetected(false);
    setDocumentRejected(false);
  };

  // No thesis title reached the relevance floor. Treated as its own neutral
  // outcome, not as Low Similarity: no score, no risk colour, no matches.
  const noMeaningfulMatch = result?.has_meaningful_match === false;
  const visuals = result && !noMeaningfulMatch ? statusVisuals(result.classification) : null;
  const tone = visuals ? TONE_CLASSES[visuals.tone] : null;
  // One decimal place so the displayed score matches threshold filtering behaviour.
  const pct = result ? ((result.similarity_score ?? 0) * 100).toFixed(1) : '0.0';
  const { common: commonTerms, distinctive: distinctiveTerms } =
    visuals ? splitTerms(result.query || title, result.matches || []) : { common: [], distinctive: [] };

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

  // Panel enter: fade + small horizontal offset, gated by reduced motion.
  // DURATION.normal (150ms) — comfortably under the ~180ms ceiling for this
  // class of transition (tokens.css --duration-enter is the 200ms hard cap).
  const panelVariants = reduceMotion
    ? {
        initial: { opacity: 1, transform: 'translateX(0px)' },
        animate: { opacity: 1, transform: 'translateX(0px)', transition: { duration: 0 } },
        exit:    { opacity: 1, transform: 'translateX(0px)', transition: { duration: 0 } },
      }
    : {
        initial: { opacity: 0, transform: 'translateX(8px)' },
        animate: { opacity: 1, transform: 'translateX(0px)', transition: { duration: DURATION.normal, ease: EASE_OUT } },
        // Outgoing panel leaves instantly: with mode="wait" an animated exit
        // would hold the new panel back and double the switch time.
        exit:    { opacity: 0, transition: { duration: 0 } },
      };

  const titleInputCls = `w-full px-4 py-3 rounded-lg border text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary ${
    'thesys-input'
  }`;

  return (
    <LazyMotion features={domAnimation}>
      <div className={`min-h-screen bg-canvas`}>
        <AppNavbar activePage="similarity" />

        <PageShell>

          {/* ── Header ────────────────────────────────────────────────── */}
          <PageHeader title="Title Similarity Validation">
            <p className={`text-sm text-body`}>
              Validate proposed thesis titles using AI-assisted semantic comparison.
            </p>
          </PageHeader>

          {/* Two-column layout: form (left) + methodology rail (right) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* LEFT — form + results */}
            <div className="lg:col-span-2">

              <form onSubmit={handleSubmit} className="space-y-5 mb-6">

                {/* ── Segmented control ──────────────────────────────── */}
                <div
                  role="tablist"
                  aria-label="Title input method"
                  className={`inline-flex items-center gap-1 rounded-full border p-1 border-border-default bg-surface-secondary`}
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
                        className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                          selected
                            ? 'bg-primary-solid text-white'
                            : 'text-muted hover:text-ink'
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
                          className={`block text-sm font-semibold mb-1 text-ink`}
                        >
                          Proposed title
                        </label>
                        <input
                          id="proposed-title"
                          type="text"
                          value={title}
                          onChange={(e) => handleTitleChange(e.target.value)}
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
                        <div className="mb-1 flex items-center gap-1.5">
                          <label
                            htmlFor="upload-proposal-file"
                            className={`text-sm font-semibold text-ink`}
                          >
                            Proposal document
                          </label>
                          <details className="relative">
                            <summary className={`flex h-6 w-6 cursor-pointer list-none items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary [&::-webkit-details-marker]:hidden text-muted hover:text-ink`}>
                              <Info className="h-4 w-4" aria-hidden="true" />
                              <span className="sr-only">About automatic title extraction</span>
                            </summary>
                            <div className={`absolute left-0 top-full z-30 mt-1 w-[min(18rem,calc(100vw-4rem))] rounded-lg border border-[var(--color-border)] bg-surface-elevated p-3 text-xs leading-relaxed shadow-lg text-body`}>
                              The title is detected from your document’s text. Unusual formatting or unreadable text may produce an incomplete or incorrect title. Review and edit it before checking similarity.
                            </div>
                          </details>
                        </div>

                        <FileDropzone
                          inputId="upload-proposal-file"
                          file={uploadFile}
                          onFileSelect={handleFileSelect}
                          onRemove={handleFileRemove}
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
                              className={`text-xs font-semibold mb-1.5 block text-muted`}
                            >
                              {autoDetected ? (
                                <>
                                  Detected title
                                  <span className={`ml-2 text-[11px] font-medium normal-case text-info-text`}>
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
                              onChange={(e) => handleTitleChange(e.target.value)}
                              minLength={5}
                              maxLength={500}
                              className={titleInputCls.replace('py-3', 'py-2.5')}
                            />
                            {autoDetected && (
                              <p className={`text-xs mt-1 text-subtle`}>
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
                <div className={`pt-2 border-t border-border-subtle`}>
                  <div className="flex items-center gap-2">
                    <button
                      type="submit"
                      disabled={submitting || trimmedLen < 5 || blockedByRejectedDocument}
                      className="px-5 py-2.5 rounded-lg bg-primary-solid text-white text-sm font-semibold hover:bg-primary-solid-hover disabled:opacity-50 transition-colors flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    >
                      {submitting ? <><Spinner /> Checking similarity…</> : 'Validate Title'}
                    </button>
                  </div>
                </div>
              </form>

            </div>{/* end left column */}

            {/* RIGHT — stacked sidebar: legend (top) + Risk Level (below) */}
            <aside className="lg:col-span-1 flex flex-col gap-4 lg:sticky lg:top-20 lg:self-start">
              {/* Collapsible legend — native <details>, collapsed by default */}
              <details className="thesys-card p-4 group">
                <summary className="flex items-center justify-between cursor-pointer list-none [&::-webkit-details-marker]:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-md">
                  <span className={`text-sm font-semibold flex items-center gap-2 text-ink`}>
                    <Lightbulb className="w-4 h-4 flex-shrink-0 text-primary" aria-hidden="true" />
                    How scoring works
                  </span>
                  <ChevronDown
                    className={`w-4 h-4 flex-shrink-0 transition-transform duration-150 group-open:rotate-180 text-muted`}
                    aria-hidden="true"
                  />
                </summary>

                <div className="mt-3">
                  <p className={`text-xs leading-relaxed mb-3 text-body`}>
                    Title validation compares your proposed title with existing thesis records using SBERT semantic similarity. Higher scores may indicate topic overlap with existing studies.
                  </p>
                  <p className={`text-xs leading-relaxed mb-3 text-body`}>
                    Studies scoring at least {MEANINGFUL_PCT}% are listed as potentially related. A score alone does not mean the topics overlap, so review each study yourself.
                  </p>
                  <ul className={`text-xs space-y-1.5 text-body`}>
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
                      <span><strong>Low Similarity</strong> — {MEANINGFUL_PCT}–{MODERATE_PCT - 1}%</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <RiskDot tone="neutral" />
                      <span><strong>No meaningful match</strong> — &lt; {MEANINGFUL_PCT}%</span>
                    </li>
                  </ul>
                  <p className={`mt-3 pt-3 border-t text-[11px] flex items-center gap-1.5 border-border-subtle text-muted`}>
                    <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                    </svg>
                    Powered by SBERT semantic comparison
                  </p>
                </div>
              </details>

              {/* Risk Level — announced when a result lands, not visual-only */}
              {noMeaningfulMatch ? (
                <div
                  role="status"
                  aria-live="polite"
                  className="rounded-xl border border-[var(--color-border)] bg-surface-elevated p-5"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <RiskDot tone="neutral" className="w-3 h-3" />
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wider mb-0.5 text-muted">Result</p>
                      <h2 className={`text-lg font-bold leading-none text-ink`}>No meaningful match found</h2>
                    </div>
                  </div>
                  <div className={`pt-3 border-t border-border-subtle`}>
                    <p className={`text-sm leading-relaxed text-body`}>{result.recommendation}</p>
                  </div>
                </div>
              ) : result && visuals && tone ? (
                <div
                  role="status"
                  aria-live="polite"
                  className={`rounded-xl border p-5 ${tone.card}`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <RiskDot tone={visuals.tone} className="w-3 h-3" />
                    <div>
                      <p className={`text-[11px] font-semibold uppercase tracking-wider mb-0.5 ${tone.text} opacity-70`}>Risk level</p>
                      <h2 className={`text-lg font-bold leading-none text-ink`}>{visuals.label}</h2>
                    </div>
                    <div className="ml-auto">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${tone.chip}`}>
                        {pct}%
                      </span>
                    </div>
                  </div>
                  <div className={`pt-3 border-t border-border-subtle`}>
                    <div className={`text-[11px] font-semibold uppercase tracking-wider mb-1 ${tone.text} opacity-70`}>Recommendation</div>
                    <p className={`text-sm leading-relaxed ${tone.text}`}>{result.recommendation}</p>
                  </div>
                </div>
              ) : (
                <div className={`rounded-xl border border-dashed p-6 flex flex-col items-center text-center gap-2 border-border-strong bg-surface`}>
                  <ShieldCheck className={`w-7 h-7 text-subtle`} aria-hidden="true" />
                  <p className={`text-xs font-semibold text-muted`}>Awaiting validation</p>
                  <p className={`text-xs leading-relaxed text-subtle`}>
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
              <p className={`text-sm text-muted`}>
                Comparing title embeddings against the thesis corpus…
              </p>
            </div>
          )}

          {/* ── Full-width results detail (below the two-column grid) ──── */}
          {result && visuals && (
            <div className="mt-6 space-y-6">
              {/* Potentially related studies — only matches at or above the
                  relevance floor arrive here; all rendered, no expander */}
              {result.matches?.length > 0 && (
                <div>
                  <h3 className={`text-sm font-semibold uppercase tracking-wider mb-1 text-body`}>
                    Potentially Related Studies
                  </h3>
                  <p className={`text-xs mb-3 text-muted`}>
                    {result.matches.length} thes{result.matches.length === 1 ? 'is' : 'es'} {result.matches.some((m) => m.title_match) ? `scored at least ${MEANINGFUL_PCT}% similar or share your exact title` : `scored at least ${MEANINGFUL_PCT}% similar`}. Check whether their topics actually overlap with yours.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {result.matches.map((m) => <MatchCard key={m.id} match={m} />)}
                  </div>
                </div>
              )}

              {/* Term analysis — two labelled columns of pills */}
              {(commonTerms.length > 0 || distinctiveTerms.length > 0) && (
                <div className={`rounded-xl border p-5 bg-surface border-border-default`}>
                  <h3 className={`text-sm font-semibold uppercase tracking-wider mb-2 text-body`}>
                    Term Analysis
                  </h3>
                  <p className={`text-xs mb-3 text-muted`}>
                    Terms shared with similar theses vs. terms unique to your proposed title.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {commonTerms.length > 0 && (
                      <div>
                        <p className={`text-[11px] font-semibold uppercase tracking-wider mb-1.5 text-muted`}>
                          Shared terms
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {commonTerms.map((t) => (
                            <span key={t} className={`text-[11px] px-2 py-0.5 rounded-md bg-warning-bg text-warning-text border border-warning-border`}>{t}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {distinctiveTerms.length > 0 && (
                      <div>
                        <p className={`text-[11px] font-semibold uppercase tracking-wider mb-1.5 text-muted`}>
                          Distinctive terms
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {distinctiveTerms.map((t) => (
                            <span key={t} className={`text-[11px] px-2 py-0.5 rounded-md bg-info-bg text-info-text border border-info-border`}>{t}</span>
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
