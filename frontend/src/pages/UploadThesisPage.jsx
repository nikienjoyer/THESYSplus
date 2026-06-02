/**
 * UploadThesisPage — Phase 1 thesis upload form.
 *
 * Authenticated route. Submits a multipart/form-data POST to
 * /api/v1/theses/upload/. Students land in pending_review; faculty/admin
 * land in approved (handled server-side).
 *
 * Phase 2 additions:
 *   - Simulated frontend upload progress stages during submission
 *   - Trust cue: "Uploaded theses are reviewed before publication."
 *   - File guidance helper text
 */

import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import AppNavbar from '../components/layout/AppNavbar';

const PROGRAMS = [
  'BS Information System',
  'BS Information Technology',
  'BS Computer Science',
  'Associate in Computer Technology',
];

const MAX_FILE_BYTES = 25 * 1024 * 1024;

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
    <div className="thesys-card p-5">
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
          <Spinner size="sm" className={isDark ? 'text-blue-400' : 'text-blue-600'} />
        )}
        <p className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
          {current.label}
        </p>
      </div>

      {/* Progress bar */}
      <div className={`h-1.5 rounded-full overflow-hidden ${isDark ? 'bg-white/[0.08]' : 'bg-gray-100'}`}>
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            done ? 'bg-emerald-500' : 'bg-blue-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Stage dots */}
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

      {/* Helper text */}
      {!done && (
        <p className={`text-xs mt-2 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
          Progress shown is an estimated guide while the system processes your submission.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function UploadThesisPage() {
  const { theme } = useTheme();
  const { isAuthenticated, user } = useAuth();
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
      // Stage UPLOAD_STAGES.length - 1 ("Submission complete") is set when API resolves
    };

    stageTimerRef.current = setTimeout(advance, UPLOAD_STAGES[0].duration);
    return () => clearTimeout(stageTimerRef.current);
  }, [submitting]);

  const validateFile = (f) => {
    if (!f) return '';
    const ext = f.name.toLowerCase().split('.').pop();
    if (ext !== 'pdf' && ext !== 'docx') return 'Only PDF and DOCX files are allowed.';
    if (f.size > MAX_FILE_BYTES) return `File size must be less than 25 MB (selected: ${fmtBytes(f.size)}).`;
    return '';
  };

  const handleFileChange = (e) => {
    const f = e.target.files?.[0] || null;
    if (!f) { setFile(null); setFileError(''); return; }
    
    // Immediate file type validation
    const ext = f.name.toLowerCase().split('.').pop();
    if (ext !== 'pdf' && ext !== 'docx') {
      setFileError('Only PDF and DOCX files are allowed.');
      setFile(null);
      e.target.value = '';
      return;
    }
    
    const err = validateFile(f);
    if (err) { setFileError(err); setFile(null); e.target.value = ''; }
    else { setFileError(''); setFile(f); }
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
        headers: {
          'Content-Type': undefined, // Let browser set multipart/form-data with boundary
        },
      });

      // Show "Submission complete" stage briefly before showing success
      clearTimeout(stageTimerRef.current);
      setStageIndex(UPLOAD_STAGES.length - 1);
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
        setError('File size must be less than 25 MB.');
      } else if (code === 'FILE_TYPE_NOT_ALLOWED' || code === 'FILE_TYPE_MISMATCH') {
        setError('Only PDF and DOCX files are allowed.');
      } else if (code === 'VALIDATION_ERROR' && details && typeof details === 'object') {
        // Backend returned field-level validation errors
        const fieldErrs = {};
        let hasFieldErrors = false;

        // Map backend field names to frontend-friendly messages
        Object.keys(details).forEach((field) => {
          const messages = details[field];
          if (Array.isArray(messages) && messages.length > 0) {
            fieldErrs[field] = messages[0]; // Take first error message
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
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Success state
  if (success) {
    return (
      <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
        <AppNavbar activePage="upload" breadcrumb="Upload" />
        <main className="max-w-2xl mx-auto px-5 py-12">
          <div className={`rounded-xl border p-8 text-center ${
            success.status === 'approved'
              ? isDark ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-emerald-50 border-emerald-200'
              : isDark ? 'bg-amber-500/10 border-amber-500/30' : 'bg-amber-50 border-amber-200'
          }`}>
            <div className="text-4xl mb-3">{success.status === 'approved' ? '✅' : '⏳'}</div>
            <h1 className={`text-2xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
              {success.status === 'approved' ? 'Thesis Approved & Published' : 'Submitted for Review'}
            </h1>
            <p className={`text-sm mb-6 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              {success.status === 'approved'
                ? 'Your thesis is now live in the repository.'
                : 'Your thesis has been submitted and is awaiting faculty review.'}
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link to={`/repository/${success.id}`}
                className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors">
                View Thesis
              </Link>
              <Link to="/repository"
                className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                  isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                }`}>
                View Repository
              </Link>
              <button
                type="button"
                onClick={() => {
                  setSuccess(null);
                  setTitle('');
                  setAbstract('');
                  setAuthors('');
                  setKeywords('');
                  setProgram(PROGRAMS[0]);
                  setYear(new Date().getFullYear());
                  setAdviser('');
                  setFile(null);
                  setFileError('');
                  setError('');
                  setFieldErrors({});
                  setStageIndex(-1);
                }}
                className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                  isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Upload Another Thesis
              </button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  const inputCls = `w-full px-3 py-2.5 rounded-lg border text-sm outline-none transition-colors ${
    isDark
      ? 'bg-white/[0.04] border-white/10 text-gray-200 placeholder-gray-500 focus:border-blue-500/40'
      : 'bg-white border-gray-200 text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100'
  }`;
  const labelCls = `block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`;

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      <AppNavbar activePage="upload" breadcrumb="Upload" />

      <main className="max-w-2xl mx-auto px-5 py-8">
        <h1 className={`text-2xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
          Upload Thesis
        </h1>
        <p className={`text-sm mb-1 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
          {user?.role === 'student'
            ? 'Your submission will be reviewed by a faculty member before being published.'
            : 'Your thesis will be published immediately upon upload.'}
        </p>
        {/* Trust cue */}
        <p className={`text-xs mb-6 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
          🔒 Uploaded theses are reviewed before publication.
        </p>

        {/* Upload progress — shown while submitting */}
        {submitting && stageIndex >= 0 && (
          <div className="mb-5">
            <UploadProgress stageIndex={stageIndex} isDark={isDark} />
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="thesys-card p-6"
        >
          <div className="space-y-4">
            <div>
              <label className={labelCls}>Title</label>
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
                required minLength={5} maxLength={500} disabled={submitting} className={inputCls} />
              {fieldErrors.title && (
                <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>
                  {fieldErrors.title}
                </p>
              )}
            </div>

            <div>
              <label className={labelCls}>Abstract</label>
              <textarea value={abstract} onChange={(e) => setAbstract(e.target.value)}
                required minLength={20} rows={5} disabled={submitting} className={inputCls} />
              {fieldErrors.abstract && (
                <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>
                  {fieldErrors.abstract}
                </p>
              )}
            </div>

            <div>
              <label className={labelCls}>Authors (comma-separated)</label>
              <input type="text" value={authors} onChange={(e) => setAuthors(e.target.value)}
                placeholder="Dela Cruz, Juan; Santos, Maria" required disabled={submitting} className={inputCls} />
              {fieldErrors.authors && (
                <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>
                  {fieldErrors.authors}
                </p>
              )}
            </div>

            <div>
              <label className={labelCls}>Keywords (comma-separated)</label>
              <input type="text" value={keywords} onChange={(e) => setKeywords(e.target.value)}
                placeholder="AI, OCR, web system" required disabled={submitting} className={inputCls} />
              {fieldErrors.keywords && (
                <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>
                  {fieldErrors.keywords}
                </p>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Program</label>
                <select value={program} onChange={(e) => setProgram(e.target.value)}
                  disabled={submitting} className={inputCls}>
                  {PROGRAMS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                {fieldErrors.program && (
                  <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>
                    {fieldErrors.program}
                  </p>
                )}
              </div>
              <div>
                <label className={labelCls}>Year</label>
                <input type="number" min={1980} max={2100} value={year}
                  onChange={(e) => setYear(Number(e.target.value))} required disabled={submitting} className={inputCls} />
                {fieldErrors.year && (
                  <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>
                    {fieldErrors.year}
                  </p>
                )}
              </div>
            </div>

            <div>
              <label className={labelCls}>Adviser (optional)</label>
              <input type="text" value={adviser} onChange={(e) => setAdviser(e.target.value)}
                disabled={submitting} className={inputCls} />
              {fieldErrors.adviser && (
                <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>
                  {fieldErrors.adviser}
                </p>
              )}
            </div>

            <div>
              <label className={labelCls}>Thesis Document</label>
              {/* File guidance */}
              <p className={`text-xs mb-2 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                Accepted formats: <strong>PDF</strong> or <strong>DOCX</strong> (max 25 MB).
                Machine-readable documents use direct extraction; scanned files may use OCR.
              </p>
              <input
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={handleFileChange}
                required
                disabled={submitting}
                className={`block w-full text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}
                  file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium
                  file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100
                  dark:file:bg-blue-900/20 dark:file:text-blue-400 dark:hover:file:bg-blue-900/30
                  cursor-pointer`}
              />
              {file && !fileError && (
                <p className={`mt-1 text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                  Selected: {file.name} ({fmtBytes(file.size)})
                </p>
              )}
              {fileError && <p className="mt-1 text-xs text-rose-500">{fileError}</p>}
              {fieldErrors.file && (
                <p className={`mt-1 text-xs ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>
                  {fieldErrors.file}
                </p>
              )}
            </div>

            {error && (
              <div className={`rounded-lg p-3 text-sm ${
                isDark ? 'bg-rose-500/10 text-rose-300 border border-rose-500/30' : 'bg-rose-50 text-rose-700 border border-rose-200'
              }`}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting || !file}
              className="w-full px-4 py-3 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
            >
              {submitting ? <><Spinner /> Uploading…</> : 'Upload Thesis'}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
