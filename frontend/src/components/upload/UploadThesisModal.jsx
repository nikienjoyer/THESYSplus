/**
 * UploadThesisModal — globally accessible thesis upload overlay.
 *
 * Replaces the old standalone /upload page. Triggered from any "Upload Thesis"
 * button via the useUploadModal() context. Renders an Impeccable dimmed
 * overlay (backdrop-blur-sm bg-canvas/80) with a centered max-w-2xl elevated
 * surface — no nested card-ception, strict space-y-5 form rhythm, uppercase
 * muted labels.
 *
 * Submits multipart/form-data to /api/v1/theses/upload/. Students land in
 * pending_review; faculty/admin land in approved (handled server-side).
 */

import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, Clock, Sparkles, X } from 'lucide-react';
import client from '../../api/client';
import { clearAllCaches } from '../../utils/appCaches';
import { parseAuthorInput } from '../../utils/formatters';
import { useAuth } from '../../hooks/useAuth';
import { useTheme } from '../../context/ThemeContext';
import { useToast } from '../../hooks/useToast';
import { useUploadModal } from '../../hooks/useUploadModal';
import useFocusTrap from '../../hooks/useFocusTrap';
import useBodyScrollLock from '../../hooks/useBodyScrollLock';
import Spinner from '../ui/Spinner';
import FileDropzone from '../ui/FileDropzone';
import { MAX_UPLOAD_MB } from '../../lib/upload';

const PROGRAMS = [
  'BS Information System',
  'BS Information Technology',
  'BS Computer Science',
  'Associate in Computer Technology',
];

// Simulated frontend progress stages (purely visual — no backend changes)
//
// KNOWN INCONSISTENCY (flagged, deliberately not changed here): "Reading
// document…" and "Processing thesis content…" are timed animations that run
// AFTER submit, but the document is now actually read much earlier — on file
// attach, by the auto-fill extraction below. The labels therefore narrate work
// that has already finished. Rewording them is a copy decision that belongs
// with the progress indicator, not with this task's wiring.
const UPLOAD_STAGES = [
  { label: 'Preparing upload…',              duration: 800  },
  { label: 'Reading document…',              duration: 1200 },
  { label: 'Processing thesis content…',     duration: 1000 },
  { label: 'Preparing semantic indexing…',   duration: 600  },
  { label: 'Submission complete.',           duration: 0    },
];

// Ceiling for the auto-fill request. The backend reads only the first
// METADATA_PAGES pages, so a normal response is fast; this exists so a stalled
// request cannot leave the submit button disabled indefinitely.
const EXTRACTION_TIMEOUT_MS = 30_000;

// Per-field confidence returned by /theses/extract-metadata/, rendered as a
// call to ACTION rather than an OCR/ML confidence label — the user should not
// have to interpret what "medium confidence" means for their own document.
//
// High confidence has no entry on purpose: a high-confidence field is assumed
// correct and rendered with no indicator at all, so the form only asks for
// attention where attention is actually warranted.
//
// Low uses orange, not red/rose. Low confidence means the extractor is
// uncertain, not that the value is invalid — red/danger stays reserved for
// actual validation errors (see fieldErrors below), so it isn't confused with
// "something is wrong here." Orange is a deliberately small step up from
// medium's amber, not a full jump to a danger hue.
const CONFIDENCE_UI = {
  medium: { tone: 'text-amber-600 dark:text-amber-400',   label: 'Please verify' },
  low:    { tone: 'text-orange-600 dark:text-orange-400', label: 'Needs review' },
};

// ---------------------------------------------------------------------------
// Confidence hint — quiet, inline with the field label, secondary to it
// ---------------------------------------------------------------------------
function ConfidenceHint({ confidence }) {
  const ui = CONFIDENCE_UI[confidence];
  if (!ui) return null; // high confidence, or nothing was extracted for this field

  return (
    <span className={`ml-2 text-[11px] font-medium normal-case tracking-normal ${ui.tone}`}>
      {ui.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Upload progress indicator
// ---------------------------------------------------------------------------
function UploadProgress({ stageIndex, progress, isDark }) {
  const current = UPLOAD_STAGES[Math.min(stageIndex, UPLOAD_STAGES.length - 1)];
  const pct = Math.max(0, Math.min(100, Math.round(progress)));
  const done = pct === 100;

  return (
    <div className="rounded-lg border border-[var(--color-border)] px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-4">
        <p
          aria-live="polite"
          className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}
        >
          {current.label}
        </p>
        <span className={`shrink-0 text-sm font-semibold tabular-nums ${done ? 'text-emerald-500' : 'text-blue-500'}`}>
          {pct}%
        </span>
      </div>
      <div
        aria-label="Upload progress"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={pct}
        role="progressbar"
        className={`h-2 overflow-hidden rounded-full ${isDark ? 'bg-white/[0.08]' : 'bg-gray-100'}`}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-300 ease-out ${done ? 'bg-emerald-500' : 'bg-blue-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------
export default function UploadThesisModal() {
  const { isOpen, close } = useUploadModal();
  const { theme } = useTheme();
  const { user } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const isDark = theme === 'dark';

  const [title, setTitle]       = useState('');
  const [abstract, setAbstract] = useState('');
  const [authors, setAuthors]   = useState('');
  const [keywords, setKeywords] = useState('');
  const [program, setProgram]   = useState(PROGRAMS[0]);
  const [year, setYear]         = useState(new Date().getFullYear());
  const [adviser, setAdviser]   = useState('');
  const [file, setFile]         = useState(null);

  const [submitting, setSubmitting]         = useState(false);
  const [stageIndex, setStageIndex]         = useState(-1); // -1 = not started
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError]                   = useState('');
  const [fieldErrors, setFieldErrors]       = useState({});
  const [success, setSuccess]               = useState(null);

  // Confirmation step between pressing "Upload Thesis" and the actual POST.
  const [confirmOpen, setConfirmOpen]       = useState(false);

  // ── Auto-fill from the attached document ──────────────────────────────
  const [extracting, setExtracting]         = useState(false);
  const [autoFilled, setAutoFilled]         = useState({});   // field -> confidence
  const [extractionNote, setExtractionNote] = useState(null); // { text, tone }

  // Hard block: set when the backend gate has rejected the attached document
  // (either from auto-fill's own probe, or from a submit that reached the
  // upload endpoint before auto-fill could score it). A string, not a
  // boolean, because handleSubmit() calls setError('') on every submit and
  // would otherwise wipe a message stored in `error` instead of here.
  const [rejectedReason, setRejectedReason] = useState(null);

  // Which fields the user has interacted with. A ref, not state: it must be
  // readable at its CURRENT value from inside an in-flight extraction's
  // callback. A state closure would hold whatever was true when the file was
  // attached, and would happily overwrite something typed while the request
  // was still running.
  const touchedRef = useRef(new Set());

  const progressFrameRef = useRef(null);
  const extractAbortRef = useRef(null);
  const panelRef = useFocusTrap(isOpen);
  const backdropRef = useBodyScrollLock(isOpen);

  const markTouched = (field) => { touchedRef.current.add(field); };

  const cancelExtraction = () => {
    extractAbortRef.current?.abort();
    extractAbortRef.current = null;
  };

  const resetForm = () => {
    // Aborted inline rather than via cancelExtraction(). resetForm is called
    // from an effect, and react-hooks/exhaustive-deps can only stay quiet
    // about it while its body touches nothing but refs and state setters —
    // calling another component-scope function makes the rule treat resetForm
    // as reactive and demand it in the dependency array.
    extractAbortRef.current?.abort();
    extractAbortRef.current = null;
    touchedRef.current = new Set();
    setTitle(''); setAbstract(''); setAuthors(''); setKeywords('');
    setProgram(PROGRAMS[0]); setYear(new Date().getFullYear()); setAdviser('');
    setFile(null); setError(''); setFieldErrors({});
    setStageIndex(-1); setUploadProgress(0); setSuccess(null);
    setExtracting(false); setAutoFilled({}); setExtractionNote(null);
    setRejectedReason(null);
    setConfirmOpen(false);
  };

  // Reset everything whenever the modal is dismissed so it reopens fresh
  useEffect(() => {
    if (!isOpen) resetForm();
  }, [isOpen]);

  // Animate visual progress while the server receives and processes the upload.
  // Keep the simulated value below 100% until the server confirms success.
  useEffect(() => {
    if (!submitting) return undefined;

    const totalDuration = UPLOAD_STAGES.slice(0, -1)
      .reduce((total, stage) => total + stage.duration, 0);
    const startedAt = performance.now();

    const updateProgress = (now) => {
      const elapsed = Math.min(now - startedAt, totalDuration);
      setUploadProgress((elapsed / totalDuration) * 90);

      let accumulatedDuration = 0;
      let nextStage = 0;
      for (let index = 0; index < UPLOAD_STAGES.length - 1; index += 1) {
        accumulatedDuration += UPLOAD_STAGES[index].duration;
        if (elapsed < accumulatedDuration) break;
        nextStage = Math.min(index + 1, UPLOAD_STAGES.length - 2);
      }
      setStageIndex(nextStage);

      if (elapsed < totalDuration) {
        progressFrameRef.current = requestAnimationFrame(updateProgress);
      }
    };

    progressFrameRef.current = requestAnimationFrame(updateProgress);
    return () => cancelAnimationFrame(progressFrameRef.current);
  }, [submitting]);

  const requestClose = () => {
    if (submitting) return; // don't allow closing mid-upload
    // While the confirmation is up it is the innermost layer, so a dismiss
    // gesture belongs to it — backing out of the prompt must not also discard
    // the filled-in form.
    if (confirmOpen) { setConfirmOpen(false); return; }
    close();
  };

  // Escape dismisses the innermost layer: the confirmation if it is open,
  // otherwise the modal itself.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => { if (e.key === 'Escape') requestClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, submitting, confirmOpen]);

  // NOTE: client-side file type/size validation lives entirely in
  // FileDropzone, which rejects invalid files (with a toast) before they
  // ever reach onFileSelect. A local validateFile() used to exist here but
  // was unreachable — it could only ever run on files FileDropzone had
  // already approved. Server-side file errors still surface via
  // fieldErrors.file and the FILE_TOO_LARGE / FILE_TYPE_* branches below.

  // ── Auto-fill ─────────────────────────────────────────────────────────

  /**
   * Copy extracted values into the form, filling ONLY fields the user has not
   * supplied. Two different emptiness tests are needed:
   *
   *   * Text fields (title, abstract, authors, keywords) start empty, so
   *     "still empty AND untouched" is the condition. Untouched matters on its
   *     own: a user who typed and then cleared a field chose to leave it
   *     blank, and that choice is respected.
   *   * Program and year always hold a value — the select defaults to
   *     PROGRAMS[0] and year to the current year — so emptiness is not a
   *     meaningful test for them. Untouched is the equivalent condition.
   */
  const applyExtractedMetadata = (data) => {
    const fields = data?.fields || {};
    const touched = touchedRef.current;
    const filled = {};

    const confidenceOf = (key) => fields[key]?.confidence || 'low';

    const fillText = (key, current, setter) => {
      const raw = fields[key]?.value;
      const value = typeof raw === 'string' ? raw.trim() : '';
      if (!value || touched.has(key) || current.trim() !== '') return;
      setter(value);
      filled[key] = confidenceOf(key);
    };

    fillText('title', title, setTitle);
    fillText('abstract', abstract, setAbstract);

    // Joined with '; ' and NOT ', ' on purpose: every extracted name already
    // contains a comma ("Dela Cruz, Juan M."), so a comma join would make
    // parseAuthorInput read one author as two.
    const authorList = fields.authors?.value;
    if (Array.isArray(authorList) && authorList.length > 0
        && !touched.has('authors') && authors.trim() === '') {
      setAuthors(authorList.join('; '));
      filled.authors = confidenceOf('authors');
    }

    const keywordList = fields.keywords?.value;
    if (Array.isArray(keywordList) && keywordList.length > 0
        && !touched.has('keywords') && keywords.trim() === '') {
      setKeywords(keywordList.join(', '));
      filled.keywords = confidenceOf('keywords');
    }

    // PROGRAMS.includes is a second gate on top of the server's enum check.
    // A value outside the list has no matching <option>, which would leave the
    // select visually blank and then fail submit with a VALIDATION_ERROR.
    const extractedProgram = fields.program?.value;
    if (typeof extractedProgram === 'string' && PROGRAMS.includes(extractedProgram)
        && !touched.has('program')) {
      setProgram(extractedProgram);
      filled.program = confidenceOf('program');
    }

    const extractedYear = fields.year?.value;
    if (Number.isInteger(extractedYear) && !touched.has('year')) {
      setYear(extractedYear);
      filled.year = confidenceOf('year');
    }

    setAutoFilled(filled);

    const count = Object.keys(filled).length;
    if (count > 0) {
      // needsReview mirrors CONFIDENCE_UI exactly: any confidence with an
      // entry there (medium/low) is a field the per-label hint already
      // flagged. Keeping this list in sync with CONFIDENCE_UI, rather than
      // hardcoding ['medium', 'low'] a second time, means the two can't
      // silently disagree about what counts as "needs attention".
      const needsReview = Object.values(filled)
        .filter((confidence) => CONFIDENCE_UI[confidence]).length;

      setExtractionNote({
        tone: 'info',
        text: needsReview > 0
          ? `Auto-filled ${count} field${count === 1 ? '' : 's'} from the document. `
            + `${needsReview} field${needsReview === 1 ? '' : 's'} need${needsReview === 1 ? 's' : ''} your review.`
          : `Auto-filled ${count} field${count === 1 ? '' : 's'} from the document. `
            + 'Please review the values before uploading.',
      });
    } else if ((data?.filled_fields || []).length > 0) {
      setExtractionNote({
        tone: 'info',
        text: 'Details were found in the document, but your existing entries were kept.',
      });
    } else {
      setExtractionNote({
        tone: 'warn',
        text: 'No details could be read from this document. Please enter them manually.',
      });
    }
  };

  /**
   * Read metadata from the attached file.
   *
   * Failure is always non-blocking: every error path leaves the form fully
   * editable and the file still attached, so a manual upload proceeds exactly
   * as it did before this feature existed. Nothing here can prevent an upload.
   */
  const runExtraction = async (selected) => {
    cancelExtraction();
    const controller = new AbortController();
    extractAbortRef.current = controller;

    setExtracting(true);
    setAutoFilled({});
    setExtractionNote(null);
    setRejectedReason(null);

    try {
      const fd = new FormData();
      fd.append('file', selected);

      const res = await client.post('/theses/extract-metadata/', fd, {
        headers: { 'Content-Type': undefined },
        timeout: EXTRACTION_TIMEOUT_MS,
        signal: controller.signal,
      });

      // A superseded request (file replaced or removed mid-flight) must not
      // write into the form.
      if (extractAbortRef.current !== controller) return;
      applyExtractedMetadata(res.data);
    } catch (err) {
      if (extractAbortRef.current !== controller) return;
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return;

      const code = err?.response?.data?.error?.code;

      // A refused document is NOT an auto-fill failure, and must not be
      // reported as one. "Please enter the details manually" reads as
      // permission to proceed, which would walk the user into typing a
      // Certificate of Registration's details in by hand and submitting it —
      // only for the upload itself to be refused at the end. Surface the real
      // reason prominently instead, in the same error region a failed submit
      // uses.
      if (code === 'NOT_A_THESIS_DOCUMENT') {
        setRejectedReason(
          err?.response?.data?.error?.message
          || 'This document does not appear to be a thesis. Please attach the '
             + 'thesis manuscript itself.',
        );
        setExtractionNote(null);
        return;
      }

      const timedOut = err?.code === 'ECONNABORTED' || err?.code === 'ETIMEDOUT';
      setExtractionNote({
        tone: 'warn',
        text: timedOut
          ? 'Auto-fill timed out. Please enter the details manually — you can still upload.'
          : 'Auto-fill is unavailable for this document. Please enter the details '
            + 'manually — you can still upload.',
      });
    } finally {
      if (extractAbortRef.current === controller) {
        extractAbortRef.current = null;
        setExtracting(false);
      }
    }
  };

  const handleFileSelect = (selected) => {
    setFile(selected);
    runExtraction(selected);
  };

  const handleFileRemove = () => {
    cancelExtraction();
    setExtracting(false);
    setFile(null);
    // Values that were auto-filled are KEPT. Silently clearing fields the user
    // is looking at would be worse than dropping the provenance badges, and
    // those values may be exactly what they want to submit. Only the markers
    // and the note go, since they refer to a document no longer attached.
    setAutoFilled({});
    setExtractionNote(null);
    setRejectedReason(null);
  };

  /**
   * Validate, then ask for confirmation. This does NOT upload.
   *
   * Validation runs before the confirmation on purpose: being asked "are you
   * sure?" and then told the keywords were empty would waste the interaction.
   * The user only sees the prompt once the submission is actually viable.
   */
  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    // Hard block — a document the gate already rejected must never reach the
    // confirmation dialog, even via implicit form submission on Enter.
    if (rejectedReason) return;

    if (!file) { setError('Please attach a PDF or DOCX file.'); return; }
    if (parseAuthorInput(authors).length === 0) {
      setError('At least one author is required.');
      return;
    }
    if (keywords.split(',').map((k) => k.trim()).filter(Boolean).length === 0) {
      setError('At least one keyword is required.');
      return;
    }

    setConfirmOpen(true);
  };

  const performUpload = async () => {
    setConfirmOpen(false);
    setError('');
    setFieldErrors({});

    const authorsList  = parseAuthorInput(authors);
    const keywordsList = keywords.split(',').map((k) => k.trim()).filter(Boolean);

    setStageIndex(0);
    setUploadProgress(0);
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append('title', title.trim());
      fd.append('abstract', abstract.trim());
      fd.append('authors', JSON.stringify(authorsList));
      fd.append('keywords', JSON.stringify(keywordsList));
      fd.append('program', program);
      fd.append('year', String(year));
      fd.append('adviser', adviser.trim());
      fd.append('file', file);

      const res = await client.post('/theses/upload/', fd, {
        headers: { 'Content-Type': undefined },
      });

      cancelAnimationFrame(progressFrameRef.current);
      setStageIndex(UPLOAD_STAGES.length - 1);
      setUploadProgress(100);
      clearAllCaches();
      await new Promise((resolve) => setTimeout(resolve, 500));
      setSuccess(res.data);
    } catch (err) {
      cancelAnimationFrame(progressFrameRef.current);
      setStageIndex(-1);
      setUploadProgress(0);
      const code = err?.response?.data?.error?.code;
      const msg  = err?.response?.data?.error?.message;
      const details = err?.response?.data?.error?.details;

      if (code === 'NOT_A_THESIS_DOCUMENT') {
        // Hard block on the backend for every role — the message names what
        // was missing, so it is surfaced verbatim rather than genericised.
        // Also raises rejectedReason: this catch runs when auto-fill never
        // got the chance to score the document (timed out, or was cancelled
        // before it resolved), so submit is the first time the gate is seen.
        const reason = msg
          || 'This document does not appear to be a thesis. Please attach the '
             + 'thesis manuscript itself.';
        setError(reason);
        setRejectedReason(reason);
      } else if (code === 'DUPLICATE_FILE') {
        setError('This file has already been uploaded.');
      } else if (code === 'FILE_TOO_LARGE') {
        setError(`File size must be less than ${MAX_UPLOAD_MB} MB.`);
      } else if (code === 'FILE_TYPE_NOT_ALLOWED' || code === 'FILE_TYPE_MISMATCH') {
        setError('Only PDF and DOCX files are allowed.');
      } else if (code === 'VALIDATION_ERROR' && details && typeof details === 'object') {
        const fieldErrs = {};
        let hasFieldErrors = false;
        Object.keys(details).forEach((fieldKey) => {
          const messages = details[fieldKey];
          if (Array.isArray(messages) && messages.length > 0) {
            fieldErrs[fieldKey] = messages[0];
            hasFieldErrors = true;
          }
        });
        if (hasFieldErrors) {
          setFieldErrors(fieldErrs);
          setError('Please correct the errors below.');
        } else {
          setError(msg || 'Please check that all fields are filled correctly.');
        }
      } else if (code === 'VALIDATION_ERROR') {
        setError(msg || 'Please check that all fields are filled correctly.');
      } else {
        setError(msg || 'Upload failed. Please try again.');
        toast.error(msg || 'Upload failed. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const goAndClose = (path) => { close(); navigate(path); };

  if (!isOpen) return null;

  const inputCls = `w-full px-3 py-2.5 rounded-lg border text-sm outline-none transition-colors ${
    isDark
      ? 'bg-white/[0.04] border-white/10 text-gray-200 placeholder-gray-500 focus:border-blue-500/40'
      : 'bg-white border-gray-200 text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100'
  }`;
  const labelCls = `block text-xs font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`;

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 overflow-hidden"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      {/* Backdrop — dimmed, blurred app context */}
      <div
        ref={backdropRef}
        className="absolute inset-0 bg-canvas/80 backdrop-blur-sm thesys-overlay-enter"
        onClick={requestClose}
        aria-hidden="true"
      />

      {/* Surface — clean elevated panel, no nested cards */}
      <div
        ref={panelRef}
        className="relative w-full max-w-2xl rounded-2xl border border-[var(--color-border)] bg-surface-elevated shadow-2xl thesys-modal-enter"
      >
        {success ? (
          /* ── Success state ── */
          <div className="p-6 sm:p-8 text-center">
            <button
              type="button"
              onClick={requestClose}
              aria-label="Close"
              className="absolute right-4 top-4 p-1.5 flex items-center justify-center rounded-md text-slate-500 dark:text-slate-300 hover:text-ink hover:bg-surface-elevated transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            >
              <X className="w-5 h-5" />
            </button>
            <div className={`w-16 h-16 flex items-center justify-center rounded-full mx-auto mb-3 ${
              success.status === 'approved' ? (isDark ? 'bg-emerald-500/20' : 'bg-emerald-50') : (isDark ? 'bg-amber-500/20' : 'bg-amber-50')
            }`}>
              {success.status === 'approved'
                ? <CheckCircle2 className="w-8 h-8 text-emerald-500" aria-hidden="true" />
                : <Clock className="w-8 h-8 text-amber-500" aria-hidden="true" />}
            </div>
            <h2 id="upload-modal-title" className={`text-2xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
              {success.status === 'approved' ? 'Thesis Approved & Published' : 'Submitted for Review'}
            </h2>
            <p className={`text-sm mb-6 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              {success.status === 'approved'
                ? 'Your thesis is now live in the repository.'
                : 'Your thesis has been submitted and is awaiting faculty review.'}
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                type="button"
                onClick={() => goAndClose(`/repository/${success.id}`)}
                className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors"
              >
                View Thesis
              </button>
              <button
                type="button"
                onClick={() => goAndClose('/repository')}
                className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                  isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                }`}
              >
                View Repository
              </button>
              <button
                type="button"
                onClick={resetForm}
                className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                  isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Upload Another Thesis
              </button>
            </div>
          </div>
        ) : (
          /* ── Form state ── */
          <div className="custom-modal-scroll max-h-[88vh] overflow-y-auto p-6 sm:p-8">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 mb-1">
              <h2 id="upload-modal-title" className="text-2xl font-bold text-ink">Upload Thesis</h2>
              <button
                type="button"
                onClick={requestClose}
                disabled={submitting}
                aria-label="Close"
                className="flex-shrink-0 -mr-1 -mt-1 p-1.5 flex items-center justify-center rounded-md text-slate-500 dark:text-slate-300 hover:text-ink hover:bg-surface-elevated transition-colors disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className={`mb-6 text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              {user?.role === 'student'
                ? 'Your submission will be reviewed by a faculty member before being published.'
                : 'Your thesis will be published immediately upon upload.'}
            </p>

            {/* Upload progress — shown while submitting */}
            {submitting && stageIndex >= 0 && (
              <div className="mb-4">
                <UploadProgress stageIndex={stageIndex} progress={uploadProgress} isDark={isDark} />
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className={labelCls}>
                  Title
                  <ConfidenceHint confidence={autoFilled.title} />
                </label>
                <input type="text" value={title}
                  onChange={(e) => { markTouched('title'); setTitle(e.target.value); }}
                  required minLength={5} maxLength={500} disabled={submitting} className={inputCls} />
                {fieldErrors.title && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.title}</p>}
              </div>

              <div>
                <label className={labelCls}>
                  Abstract
                  <ConfidenceHint confidence={autoFilled.abstract} />
                </label>
                <textarea value={abstract}
                  onChange={(e) => { markTouched('abstract'); setAbstract(e.target.value); }}
                  required minLength={20} rows={5} disabled={submitting} className={inputCls} />
                {fieldErrors.abstract && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.abstract}</p>}
              </div>

              <div>
                <label className={labelCls}>
                  Authors (separate multiple authors with semicolons or commas)
                  <ConfidenceHint confidence={autoFilled.authors} />
                </label>
                <input type="text" value={authors}
                  onChange={(e) => { markTouched('authors'); setAuthors(e.target.value); }}
                  placeholder="Dela Cruz, Juan M.; Santos, Maria A." required disabled={submitting} className={inputCls} />
                <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                </p>
                {fieldErrors.authors && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.authors}</p>}
              </div>

              <div>
                <label className={labelCls}>
                  Keywords (comma-separated)
                  <ConfidenceHint confidence={autoFilled.keywords} />
                </label>
                <input type="text" value={keywords}
                  onChange={(e) => { markTouched('keywords'); setKeywords(e.target.value); }}
                  placeholder="AI, OCR, web system" required disabled={submitting} className={inputCls} />
                {fieldErrors.keywords && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.keywords}</p>}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>
                    Program
                    <ConfidenceHint confidence={autoFilled.program} />
                  </label>
                  <select value={program}
                    onChange={(e) => { markTouched('program'); setProgram(e.target.value); }}
                    disabled={submitting} className={inputCls}>
                    {PROGRAMS.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                  {fieldErrors.program && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.program}</p>}
                </div>
                <div>
                  <label className={labelCls}>
                    Year
                    <ConfidenceHint confidence={autoFilled.year} />
                  </label>
                  <input type="number" min={1980} max={2100} value={year}
                    onChange={(e) => { markTouched('year'); setYear(Number(e.target.value)); }}
                    required disabled={submitting} className={inputCls} />
                  {fieldErrors.year && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.year}</p>}
                </div>
              </div>

              <div>
                <label className={labelCls}>Adviser (optional)</label>
                <input type="text" value={adviser}
                  onChange={(e) => { markTouched('adviser'); setAdviser(e.target.value); }}
                  disabled={submitting} className={inputCls} />
                {fieldErrors.adviser && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.adviser}</p>}
              </div>

              <div>
                <label className={labelCls}>Thesis Document</label>
                <p className={`text-xs mb-2 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  Accepted formats: <strong>PDF</strong> or <strong>DOCX</strong> (max {MAX_UPLOAD_MB} MB).
                  Attaching a file fills in any details it can read from the title page —
                  empty fields only, and you can edit everything afterwards.
                </p>
                <FileDropzone
                  file={file}
                  onFileSelect={handleFileSelect}
                  onRemove={handleFileRemove}
                  disabled={submitting}
                  idleTitle="Drag & drop your thesis"
                />
                {fieldErrors.file && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.file}</p>}

                {/* Auto-fill status — advisory only, never blocks the form */}
                <div aria-live="polite" role="status">
                  {extracting && (
                    <p className={`mt-2 flex items-center gap-2 text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                      <Spinner />
                      Reading the document to fill in what it can…
                    </p>
                  )}
                  {!extracting && extractionNote && (
                    <p className={`mt-2 flex items-start gap-1.5 text-xs ${
                      extractionNote.tone === 'warn'
                        ? (isDark ? 'text-amber-400' : 'text-amber-700')
                        : (isDark ? 'text-gray-400' : 'text-gray-600')
                    }`}>
                      {extractionNote.tone === 'warn'
                        ? <AlertTriangle className="w-3.5 h-3.5 mt-px flex-shrink-0" aria-hidden="true" />
                        : <Sparkles className="w-3.5 h-3.5 mt-px flex-shrink-0" aria-hidden="true" />}
                      <span>{extractionNote.text}</span>
                    </p>
                  )}
                </div>
              </div>

              {rejectedReason && (
                <div
                  id="upload-blocked-reason"
                  role="alert"
                  className={`rounded-lg p-3 text-sm ${
                    isDark ? 'bg-rose-500/10 text-rose-300 border border-rose-500/30' : 'bg-rose-50 text-rose-700 border border-rose-200'
                  }`}
                >
                  <p>{rejectedReason}</p>
                  <p className="mt-1 text-xs opacity-80">
                    Uploading is disabled for this document.
                  </p>
                </div>
              )}

              {error && (
                <div className={`rounded-lg p-3 text-sm ${
                  isDark ? 'bg-rose-500/10 text-rose-300 border border-rose-500/30' : 'bg-rose-50 text-rose-700 border border-rose-200'
                }`}>
                  {error}
                </div>
              )}

              {/* Footer controls */}
              <div className="flex items-center justify-end gap-3 pt-1">
                <button
                  type="button"
                  onClick={requestClose}
                  disabled={submitting}
                  className={`px-4 py-2.5 rounded-lg text-sm font-semibold border transition-colors disabled:opacity-50 ${
                    isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || extracting || !file || !!rejectedReason}
                  aria-describedby={rejectedReason ? 'upload-blocked-reason' : undefined}
                  className="px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  {submitting
                    ? <><Spinner /> Uploading…</>
                    : extracting ? <><Spinner /> Reading document…</> : 'Upload Thesis'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/*
          Confirmation step. Rendered INSIDE panelRef so the existing
          useFocusTrap(isOpen) already covers it — a separate portal would put
          these buttons outside the trap and let Tab escape to the page behind.
          Positioned absolutely over the panel rather than replacing it, so the
          form is never unmounted and nothing typed can be lost.
        */}
        {confirmOpen && (
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="upload-confirm-title"
            aria-describedby="upload-confirm-body"
            className="absolute inset-0 z-10 flex items-center justify-center rounded-2xl bg-canvas/85 backdrop-blur-sm p-4 sm:p-6"
          >
            <div className="w-full max-w-md rounded-xl border border-[var(--color-border)] bg-surface-elevated p-5 sm:p-6 shadow-2xl">
              <h3 id="upload-confirm-title" className="text-lg font-bold text-ink">
                Upload this thesis?
              </h3>

              <div id="upload-confirm-body" className="mt-3 space-y-3">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-wider ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    Title
                  </p>
                  <p className={`text-sm ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                    {title.trim()}
                  </p>
                </div>
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-wider ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    File
                  </p>
                  <p
                    className={`text-sm break-all ${isDark ? 'text-gray-200' : 'text-gray-800'}`}
                    title={file?.name}
                  >
                    {file?.name}
                  </p>
                </div>
                <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                  {user?.role === 'student'
                    ? 'It will be submitted for faculty review.'
                    : 'It will be published to the repository immediately.'}
                </p>
              </div>

              <div className="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setConfirmOpen(false)}
                  className={`px-4 py-2.5 rounded-lg text-sm font-semibold border transition-colors ${
                    isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Back
                </button>
                <button
                  type="button"
                  autoFocus
                  onClick={performUpload}
                  className="px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors"
                >
                  Upload
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
