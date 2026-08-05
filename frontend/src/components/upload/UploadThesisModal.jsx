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
import { CheckCircle2, Clock, Lock, X } from 'lucide-react';
import client from '../../api/client';
import { clearAllCaches } from '../../utils/appCaches';
import { useAuth } from '../../hooks/useAuth';
import { useTheme } from '../../context/ThemeContext';
import { useToast } from '../../hooks/useToast';
import { useUploadModal } from '../../hooks/useUploadModal';
import useFocusTrap from '../../hooks/useFocusTrap';
import Spinner from '../ui/Spinner';
import FileDropzone from '../ui/FileDropzone';

const PROGRAMS = [
  'BS Information System',
  'BS Information Technology',
  'BS Computer Science',
  'Associate in Computer Technology',
];

const MAX_FILE_BYTES = 15 * 1024 * 1024;

// Simulated frontend progress stages (purely visual — no backend changes)
const UPLOAD_STAGES = [
  { label: 'Preparing upload…',              duration: 800  },
  { label: 'Reading document…',              duration: 1200 },
  { label: 'Processing thesis content…',     duration: 1000 },
  { label: 'Preparing semantic indexing…',   duration: 600  },
  { label: 'Submission complete.',           duration: 0    },
];

function fmtBytes(b) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Upload progress indicator
// ---------------------------------------------------------------------------
function UploadProgress({ stageIndex, isDark }) {
  const current = UPLOAD_STAGES[Math.min(stageIndex, UPLOAD_STAGES.length - 1)];
  const pct = Math.round(((stageIndex + 1) / UPLOAD_STAGES.length) * 100);
  const done = stageIndex >= UPLOAD_STAGES.length - 1;

  return (
    <div className="rounded-xl border border-[var(--color-border)] p-5">
      <div className="flex items-center gap-3 mb-3">
        {done ? (
          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
            isDark ? 'bg-emerald-500/20' : 'bg-emerald-50'
          }`}>
            <svg className="w-4 h-4 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
            </svg>
          </div>
        ) : (
          <Spinner size="sm" className="text-primary" />
        )}
        <p className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
          {current.label}
        </p>
      </div>

      <div className={`h-1.5 rounded-full overflow-hidden ${isDark ? 'bg-white/[0.08]' : 'bg-gray-100'}`}>
        <div
          className={`h-full rounded-full transition-all duration-500 ${done ? 'bg-emerald-500' : 'bg-blue-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="flex items-center gap-1.5 mt-3">
        {UPLOAD_STAGES.map((s, i) => (
          <div
            key={s.label}
            className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
              i <= stageIndex
                ? done ? 'bg-emerald-500' : 'bg-blue-500'
                : isDark ? 'bg-white/[0.08]' : 'bg-gray-200'
            }`}
          />
        ))}
      </div>

      {!done && (
        <p className={`text-xs mt-2 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
          Progress shown is an estimated guide while the system processes your submission.
        </p>
      )}
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
  const [fileError, setFileError] = useState('');

  const [submitting, setSubmitting]   = useState(false);
  const [stageIndex, setStageIndex]   = useState(-1); // -1 = not started
  const [error, setError]             = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [success, setSuccess]         = useState(null);

  const stageTimerRef = useRef(null);
  const panelRef = useFocusTrap(isOpen);

  const resetForm = () => {
    setTitle(''); setAbstract(''); setAuthors(''); setKeywords('');
    setProgram(PROGRAMS[0]); setYear(new Date().getFullYear()); setAdviser('');
    setFile(null); setFileError(''); setError(''); setFieldErrors({});
    setStageIndex(-1); setSuccess(null);
  };

  // Reset everything whenever the modal is dismissed so it reopens fresh
  useEffect(() => {
    if (!isOpen) resetForm();
  }, [isOpen]);

  // Lock body scroll while open
  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [isOpen]);

  // Advance through simulated stages while submitting
  useEffect(() => {
    if (!submitting) return;
    setStageIndex(0);
    let idx = 0;
    const advance = () => {
      idx += 1;
      if (idx < UPLOAD_STAGES.length - 1) {
        setStageIndex(idx);
        stageTimerRef.current = setTimeout(advance, UPLOAD_STAGES[idx].duration);
      }
    };
    stageTimerRef.current = setTimeout(advance, UPLOAD_STAGES[0].duration);
    return () => clearTimeout(stageTimerRef.current);
  }, [submitting]);

  const requestClose = () => {
    if (submitting) return; // don't allow closing mid-upload
    close();
  };

  // Escape closes the modal
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => { if (e.key === 'Escape') requestClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, submitting]);

  const validateFile = (f) => {
    if (!f) return '';
    const ext = f.name.toLowerCase().split('.').pop();
    if (ext !== 'pdf' && ext !== 'docx') return 'Only PDF and DOCX files are allowed.';
    if (f.size > MAX_FILE_BYTES) return `File size must be less than 15 MB (selected: ${fmtBytes(f.size)}).`;
    return '';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    if (!file) { setError('Please attach a PDF or DOCX file.'); return; }
    const authorsList  = authors.split(',').map((a) => a.trim()).filter(Boolean);
    const keywordsList = keywords.split(',').map((k) => k.trim()).filter(Boolean);
    if (authorsList.length === 0)  { setError('At least one author is required.'); return; }
    if (keywordsList.length === 0) { setError('At least one keyword is required.'); return; }

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

      clearTimeout(stageTimerRef.current);
      setStageIndex(UPLOAD_STAGES.length - 1);
      clearAllCaches();
      setTimeout(() => setSuccess(res.data), 600);
    } catch (err) {
      clearTimeout(stageTimerRef.current);
      setStageIndex(-1);
      const code = err?.response?.data?.error?.code;
      const msg  = err?.response?.data?.error?.message;
      const details = err?.response?.data?.error?.details;

      if (code === 'DUPLICATE_FILE') {
        setError('This file has already been uploaded.');
      } else if (code === 'FILE_TOO_LARGE') {
        setError('File size must be less than 15 MB.');
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
      className="fixed inset-0 z-[9999] flex items-start sm:items-center justify-center p-4 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      {/* Backdrop — dimmed, blurred app context */}
      <div
        className="absolute inset-0 bg-canvas/80 backdrop-blur-sm thesys-overlay-enter"
        onClick={requestClose}
        aria-hidden="true"
      />

      {/* Surface — clean elevated panel, no nested cards */}
      <div
        ref={panelRef}
        className="relative w-full max-w-2xl my-4 rounded-2xl border border-[var(--color-border)] bg-surface-elevated shadow-2xl thesys-modal-enter"
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
          <div className="max-h-[88vh] overflow-y-auto p-6 sm:p-8">
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
            <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              {user?.role === 'student'
                ? 'Your submission will be reviewed by a faculty member before being published.'
                : 'Your thesis will be published immediately upon upload.'}
            </p>
            <p className={`text-xs flex items-center gap-1.5 mt-1 mb-6 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
              <Lock className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
              Uploaded theses are reviewed before publication.
            </p>

            {/* Upload progress — shown while submitting */}
            {submitting && stageIndex >= 0 && (
              <div className="mb-5">
                <UploadProgress stageIndex={stageIndex} isDark={isDark} />
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className={labelCls}>Title</label>
                <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
                  required minLength={5} maxLength={500} disabled={submitting} className={inputCls} />
                {fieldErrors.title && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.title}</p>}
              </div>

              <div>
                <label className={labelCls}>Abstract</label>
                <textarea value={abstract} onChange={(e) => setAbstract(e.target.value)}
                  required minLength={20} rows={5} disabled={submitting} className={inputCls} />
                {fieldErrors.abstract && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.abstract}</p>}
              </div>

              <div>
                <label className={labelCls}>Authors (comma-separated)</label>
                <input type="text" value={authors} onChange={(e) => setAuthors(e.target.value)}
                  placeholder="Dela Cruz, Juan; Santos, Maria" required disabled={submitting} className={inputCls} />
                {fieldErrors.authors && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.authors}</p>}
              </div>

              <div>
                <label className={labelCls}>Keywords (comma-separated)</label>
                <input type="text" value={keywords} onChange={(e) => setKeywords(e.target.value)}
                  placeholder="AI, OCR, web system" required disabled={submitting} className={inputCls} />
                {fieldErrors.keywords && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.keywords}</p>}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>Program</label>
                  <select value={program} onChange={(e) => setProgram(e.target.value)}
                    disabled={submitting} className={inputCls}>
                    {PROGRAMS.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                  {fieldErrors.program && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.program}</p>}
                </div>
                <div>
                  <label className={labelCls}>Year</label>
                  <input type="number" min={1980} max={2100} value={year}
                    onChange={(e) => setYear(Number(e.target.value))} required disabled={submitting} className={inputCls} />
                  {fieldErrors.year && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.year}</p>}
                </div>
              </div>

              <div>
                <label className={labelCls}>Adviser (optional)</label>
                <input type="text" value={adviser} onChange={(e) => setAdviser(e.target.value)}
                  disabled={submitting} className={inputCls} />
                {fieldErrors.adviser && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.adviser}</p>}
              </div>

              <div>
                <label className={labelCls}>Thesis Document</label>
                <p className={`text-xs mb-2 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  Accepted formats: <strong>PDF</strong> or <strong>DOCX</strong> (max 15 MB).
                  Machine-readable documents use direct extraction; scanned files may use OCR.
                </p>
                <FileDropzone
                  file={file}
                  onFileSelect={(f) => { setFile(f); setFileError(''); }}
                  onRemove={() => { setFile(null); setFileError(''); }}
                  disabled={submitting}
                  idleTitle="Drag & drop your thesis"
                />
                {fileError && <p className="mt-1 text-xs text-rose-500">{fileError}</p>}
                {fieldErrors.file && <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{fieldErrors.file}</p>}
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
                  disabled={submitting}
                  className={`px-4 py-2.5 rounded-lg text-sm font-semibold border transition-colors disabled:opacity-50 ${
                    isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !file}
                  className="px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  {submitting ? <><Spinner /> Uploading…</> : 'Upload Thesis'}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
