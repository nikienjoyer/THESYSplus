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
import { AlertTriangle, CheckCircle2, Clock, Info, Sparkles, X } from 'lucide-react';
import client from '../../api/client';
import { waitForJob } from '../../api/jobs';
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

const EMPTY_METADATA_FORM = Object.freeze({
  title: '',
  abstract: '',
  authors: '',
  keywords: '',
  year: '',
});

// The preview can include bounded page-level OCR for image-backed abstracts.
// Allow that work to finish while still bounding a stalled auto-fill request.
const EXTRACTION_TIMEOUT_MS = 45_000;

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

// Offer a readable version of an extracted all-caps name without changing
// the source value. Names with existing casing may contain intentional forms.
function suggestAuthorCapitalization(authorList) {
  if (!Array.isArray(authorList) || authorList.length === 0) return null;

  const source = authorList.join('; ');
  const suggested = authorList.map((name) => {
    const letters = name.match(/\p{L}/gu);
    if (!letters || !letters.every((letter) => letter === letter.toUpperCase())) {
      return name;
    }

    return name.replace(/\p{L}+/gu, (word) => {
      if (word.length === 1) return word;
      if (/^(?:II|III|IV|V|VI|VII|VIII|IX|X)$/.test(word)) return word;
      const lowered = word.toLowerCase();
      return lowered.replace(/^\p{L}/u, (letter) => letter.toUpperCase());
    });
  }).join('; ');

  return suggested === source ? null : { source, value: suggested };
}

// ---------------------------------------------------------------------------
// Upload progress indicator
// ---------------------------------------------------------------------------
function UploadProgress({ stage, canDismiss, isDark }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 rounded-lg border border-[var(--color-border)] px-4 py-3">
      <Spinner size="sm" />
      <div className={`text-sm ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
        <p className="font-medium">{stage}</p>
        <p className="text-xs opacity-70">
          {canDismiss
            ? 'You can close this window. Processing continues; keep this page open to receive the result.'
            : 'Please keep this window open while the file is being sent.'}
        </p>
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
  const [program, setProgram]   = useState('');
  const [year, setYear]         = useState('');
  const [adviser, setAdviser]   = useState('');
  const [file, setFile]         = useState(null);

  const [submitting, setSubmitting]         = useState(false);
  const [processingStage, setProcessingStage] = useState('Uploading document…');
  const [uploadAcknowledged, setUploadAcknowledged] = useState(false);
  const [error, setError]                   = useState('');
  const [fieldErrors, setFieldErrors]       = useState({});
  const [success, setSuccess]               = useState(null);

  // Confirmation step between pressing "Upload Thesis" and the actual POST.
  const [confirmOpen, setConfirmOpen]       = useState(false);

  // ── Auto-fill from the attached document ──────────────────────────────
  const [extracting, setExtracting]         = useState(false);
  const [autoFilled, setAutoFilled]         = useState({});   // field -> confidence
  const [extractionNote, setExtractionNote] = useState(null); // { text, tone }
  const [extractionFoundMetadata, setExtractionFoundMetadata] = useState(false);
  const [authorSuggestion, setAuthorSuggestion] = useState(null);

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

  const extractAbortRef = useRef(null);
  const activeSubmissionRef = useRef(null);
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
    setProgram(''); setYear(''); setAdviser('');
    setFile(null); setError(''); setFieldErrors({});
    setProcessingStage('Uploading document…'); setUploadAcknowledged(false); setSuccess(null);
    setExtracting(false); setAutoFilled({}); setExtractionNote(null);
    setExtractionFoundMetadata(false);
    setAuthorSuggestion(null);
    setRejectedReason(null);
    setConfirmOpen(false);
  };

  // Reset everything whenever the modal is dismissed so it reopens fresh
  useEffect(() => {
    if (!isOpen) resetForm();
  }, [isOpen]);

  const requestClose = () => {
    if (submitting && !uploadAcknowledged) return;
    if (submitting && uploadAcknowledged) {
      if (activeSubmissionRef.current) activeSubmissionRef.current.dismissed = true;
      activeSubmissionRef.current = null;
      setSubmitting(false);
      toast.info('Upload accepted. Processing continues in the background.');
      close();
      return;
    }
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
  }, [isOpen, submitting, uploadAcknowledged, confirmOpen]);

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
   *   * Program and year start empty. A program is filled only when extraction
   *     returns a supported value and the user has not touched the field; year
   *     also remains empty when extraction has no supported year.
   */
  const applyExtractedMetadata = (
    data,
    currentValues = { title, abstract, authors, keywords, year },
  ) => {
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

    fillText('title', currentValues.title, setTitle);
    fillText('abstract', currentValues.abstract, setAbstract);

    // Joined with '; ' and NOT ', ' on purpose: every extracted name already
    // contains a comma ("Dela Cruz, Juan M."), so a comma join would make
    // parseAuthorInput read one author as two.
    const authorList = fields.authors?.value;
    if (Array.isArray(authorList) && authorList.length > 0
        && !touched.has('authors') && currentValues.authors.trim() === '') {
      setAuthors(authorList.join('; '));
      setAuthorSuggestion(suggestAuthorCapitalization(authorList));
      filled.authors = confidenceOf('authors');
    }

    const keywordList = fields.keywords?.value;
    if (Array.isArray(keywordList) && keywordList.length > 0
        && !touched.has('keywords') && currentValues.keywords.trim() === '') {
      setKeywords(keywordList.join(', '));
      filled.keywords = confidenceOf('keywords');
    }

    // Ignore unsupported extractor values so the user must choose one of the
    // four supported programs from the placeholder.
    const extractedProgram = fields.program?.value;
    if (typeof extractedProgram === 'string' && PROGRAMS.includes(extractedProgram)
        && !touched.has('program')) {
      setProgram(extractedProgram);
      filled.program = confidenceOf('program');
    }

    const extractedYear = fields.year?.value;
    if (Number.isInteger(extractedYear) && !touched.has('year') && currentValues.year === '') {
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
    // A year auto-filled from a previously attached file is not evidence for
    // this one. Clear it before the new extraction unless the user has
    // interacted with the year field; that manually entered value is theirs
    // to keep, including when the new extraction returns unknown.
    if (autoFilled.year && !touchedRef.current.has('year')) setYear('');
    setAutoFilled({});
    setAuthorSuggestion(null);
    setExtractionNote(null);
    setExtractionFoundMetadata(false);
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
      // This request belongs to a newly selected document, whose form was
      // cleared in the same event. Use that clean snapshot because React has
      // not rendered the state updates yet; touchedRef still protects any
      // fields the user edits while this request is in flight.
      const extraction = res.data?.job_id
        ? await waitForJob(res.data.job_id, controller.signal)
        : res.data;
      if (extractAbortRef.current !== controller) return;
      applyExtractedMetadata(extraction, EMPTY_METADATA_FORM);
      setExtractionFoundMetadata(
        Array.isArray(extraction?.filled_fields) && extraction.filled_fields.length > 0,
      );
    } catch (err) {
      if (extractAbortRef.current !== controller) return;
      setExtractionFoundMetadata(false);
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError' || err?.name === 'AbortError') return;

      const code = err?.response?.data?.error?.code;

      // A refused document is NOT an auto-fill failure, and must not be
      // reported as one. "Please enter the details manually" reads as
      // permission to proceed, which would walk the user into typing a
      // Certificate of Registration's details in by hand and submitting it —
      // only for the upload itself to be refused at the end. Surface the real
      // reason prominently in the document section.
      if (code === 'NOT_A_THESIS_DOCUMENT') {
        setRejectedReason(
          err?.response?.data?.error?.message
          || 'This document does not appear to be a thesis. Please upload the '
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

  const clearDocumentForm = () => {
    touchedRef.current = new Set();
    setTitle(''); setAbstract(''); setAuthors(''); setKeywords('');
    setProgram(''); setYear(''); setAdviser('');
    setError(''); setFieldErrors({});
    setExtracting(false);
    setAutoFilled({});
    setAuthorSuggestion(null);
    setExtractionNote(null);
    setExtractionFoundMetadata(false);
    setRejectedReason(null);
  };

  const handleFileSelect = (selected) => {
    setFile(selected);
    clearDocumentForm();
    runExtraction(selected);
  };

  const handleFileRemove = () => {
    cancelExtraction();
    setFile(null);
    clearDocumentForm();
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
    if (!PROGRAMS.includes(program)) {
      setFieldErrors({ program: 'Please select a program.' });
      return;
    }
    if (!Number.isInteger(year) || year < 1980 || year > 2100) {
      setFieldErrors({year: 'Please enter a thesis year.'});
      return;
    }
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
    if (!PROGRAMS.includes(program)) {
      setConfirmOpen(false);
      setFieldErrors((current) => ({
        ...current,
        program: 'Please select a program.',
      }));
      return;
    }

    setConfirmOpen(false);
    setError('');
    setFieldErrors({});

    const authorsList  = parseAuthorInput(authors);
    const keywordsList = keywords.split(',').map((k) => k.trim()).filter(Boolean);

    const submission = { dismissed: false };
    activeSubmissionRef.current = submission;
    setProcessingStage('Uploading document…');
    setUploadAcknowledged(false);
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

      if (res.data?.job_id) setUploadAcknowledged(true);

      const completed = res.data?.job_id
        ? await waitForJob(res.data.job_id, undefined, (state) => {
          if (activeSubmissionRef.current === submission) {
            setProcessingStage(state === 'queued' ? 'Waiting to process…' : 'Checking and saving thesis…');
          }
        })
        : res.data;

      clearAllCaches();
      if (submission.dismissed) toast.success('Your thesis finished processing. Check the repository for its status.');
      else if (activeSubmissionRef.current === submission) setSuccess(completed);
    } catch (err) {
      const code = err?.response?.data?.error?.code;
      const msg  = err?.response?.data?.error?.message;
      const details = err?.response?.data?.error?.details;
      if (submission.dismissed) {
        toast.error(msg || 'Thesis processing failed. Please try again.');
        return;
      }

      if (code === 'NOT_A_THESIS_DOCUMENT') {
        // Hard block on the backend for every role. The document-section alert
        // owns this message so the same rejection is shown only once.
        // Also raises rejectedReason: this catch runs when auto-fill never
        // got the chance to score the document (timed out, or was cancelled
        // before it resolved), so submit is the first time the gate is seen.
        const reason = msg
          || 'This document does not appear to be a thesis. Please upload the '
             + 'thesis manuscript itself.';
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
      if (activeSubmissionRef.current === submission) {
        activeSubmissionRef.current = null;
        setSubmitting(false);
        setUploadAcknowledged(false);
      }
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
          <div className="custom-modal-scroll max-h-[88vh] overflow-y-auto p-4 sm:p-8">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 mb-1">
              <h2 id="upload-modal-title" className="text-2xl font-bold text-ink">Upload Thesis</h2>
              <button
                type="button"
                onClick={requestClose}
                disabled={submitting && !uploadAcknowledged}
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
            {submitting && (
              <div className="mb-4">
                <UploadProgress stage={processingStage} canDismiss={uploadAcknowledged} isDark={isDark} />
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <div className="mb-1.5 flex items-center gap-1.5">
                  <label className={`text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    Thesis Document
                  </label>
                  <details className="relative">
                    <summary className={`flex h-6 w-6 cursor-pointer list-none items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 [&::-webkit-details-marker]:hidden ${isDark ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-800'}`}>
                      <Info className="h-4 w-4" aria-hidden="true" />
                      <span className="sr-only">About automatic metadata extraction</span>
                    </summary>
                    <div className={`absolute left-0 top-full z-30 mt-1 w-[min(18rem,calc(100vw-4rem))] rounded-lg border border-[var(--color-border)] bg-surface-elevated p-3 text-xs leading-relaxed shadow-lg ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                      Auto-filled details are derived from your document. Typos, missing headings, unusual layouts, or reading errors can make fields incomplete or incorrect. Check every field before uploading.
                    </div>
                  </details>
                </div>
                <p className={`text-xs mb-2 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  Attach your thesis document to prefill the details below.
                </p>
                <FileDropzone
                  file={file}
                  onFileSelect={handleFileSelect}
                  onRemove={handleFileRemove}
                  disabled={submitting}
                  idleTitle="Drag & drop your thesis"
                  compactIdle
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
                  {!extracting && extractionNote && !extractionNote.text.startsWith('Auto-filled ') && (
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

              <div className="border-t border-[var(--color-border)]" />

              <div>
                {extractionFoundMetadata && file && (
                  <p className={`mb-2 text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Please carefully review the details below.
                  </p>
                )}
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
                  required minLength={20} rows={abstract.trim() ? 8 : 5} disabled={submitting} className={inputCls} />
                {fieldErrors.abstract && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.abstract}</p>}
              </div>

              <div>
                <label className={labelCls}>
                  Authors (separate multiple authors with semicolons or commas)
                  <ConfidenceHint confidence={autoFilled.authors} />
                </label>
                <input type="text" value={authors}
                  onChange={(e) => {
                    markTouched('authors');
                    setAuthors(e.target.value);
                    setAuthorSuggestion(null);
                  }}
                  aria-describedby={authorSuggestion ? 'author-capitalization-suggestion' : undefined}
                  placeholder="Dela Cruz, Juan M.; Santos, Maria A." required disabled={submitting} className={inputCls} />
                {authorSuggestion && authors === authorSuggestion.source && (
                  <div id="author-capitalization-suggestion" className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                    <p className={isDark ? 'text-gray-300' : 'text-gray-600'}>
                      Suggested capitalization: <span className="font-medium break-words">{authorSuggestion.value}</span>
                    </p>
                    <button type="button" disabled={submitting}
                      onClick={() => {
                        if (authors !== authorSuggestion.source) return;
                        markTouched('authors');
                        setAuthors(authorSuggestion.value);
                        setAuthorSuggestion(null);
                      }}
                      className="rounded text-sm font-medium text-blue-600 underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 disabled:opacity-50 dark:text-blue-400">
                      Use suggestion
                    </button>
                  </div>
                )}
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
                  <label htmlFor="upload-program" className={labelCls}>
                    Program
                    <ConfidenceHint confidence={autoFilled.program} />
                  </label>
                  <select
                    id="upload-program"
                    value={program}
                    onChange={(e) => {
                      const selectedProgram = e.target.value;
                      markTouched('program');
                      setProgram(selectedProgram);
                      if (PROGRAMS.includes(selectedProgram)) {
                        setFieldErrors((current) => {
                          if (!current.program) return current;
                          const next = { ...current };
                          delete next.program;
                          return next;
                        });
                      }
                    }}
                    aria-required="true"
                    aria-invalid={Boolean(fieldErrors.program)}
                    aria-describedby={fieldErrors.program ? 'upload-program-error' : undefined}
                    disabled={submitting}
                    className={inputCls}
                    style={{ color: program ? undefined : 'var(--color-text-muted)' }}
                  >
                    <option value="" disabled style={{ color: 'var(--color-text-muted)' }}>
                      Choose a program
                    </option>
                    {PROGRAMS.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                  {fieldErrors.program && (
                    <p
                      id="upload-program-error"
                      role="alert"
                      className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}
                    >
                      {fieldErrors.program}
                    </p>
                  )}
                </div>
                <div>
                  <label className={labelCls}>
                    Year
                    <ConfidenceHint confidence={autoFilled.year} />
                  </label>
                  <input type="number" min={1980} max={2100} value={year}
                    onChange={(e) => {
                      markTouched('year');
                      setYear(e.target.value === '' ? '' : Number(e.target.value));
                    }}
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
                  disabled={submitting && !uploadAcknowledged}
                  className={`px-4 py-2.5 rounded-lg text-sm font-semibold border transition-colors disabled:opacity-50 ${
                    isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {uploadAcknowledged ? 'Close' : 'Cancel'}
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
