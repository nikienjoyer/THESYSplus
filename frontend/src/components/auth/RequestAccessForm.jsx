/**
 * RequestAccessForm — Document upload access request form.
 *
 * Matches the THESYS+ auth design language (same as SignInCard):
 * blue accent, consistent input/button styling, light/dark mode.
 *
 * Validation:
 *   - Email: studentnumber@pampangastateu.edu.ph (digits-only local part)
 *   - Document: PNG / JPG / PDF, max 10 MB
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4, 7.8, 14.1
 */

import { useState } from 'react';
import { Search } from 'lucide-react';
import Spinner from '../ui/Spinner';

// Must match backend: digits-only local part, apex domain only.
const STUDENT_EMAIL_RE = /^[0-9]+@pampangastateu\.edu\.ph$/i;

function isStudentEmail(v) {
  return STUDENT_EMAIL_RE.test((v || '').trim());
}

function fmtBytes(b) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFile(file) {
  if (!file) return '';
  const allowed = ['image/png', 'image/jpeg', 'image/jpg', 'application/pdf'];
  const ext = file.name.toLowerCase();
  if (!allowed.includes(file.type) && !ext.match(/\.(png|jpe?g|pdf)$/))
    return 'Please upload a PNG, JPG, or PDF file.';
  if (file.size > 10 * 1024 * 1024)
    return 'File size must be less than 10 MB.';
  return '';
}

export default function RequestAccessForm({ onSubmit, error, isLoading, isDark, onOpenLegal }) {
  const [firstName, setFirstName]     = useState('');
  const [lastName, setLastName]       = useState('');
  const [email, setEmail]             = useState('');
  const [role, setRole]               = useState('student');
  const [doc, setDoc]                 = useState(null);
  const [agreed, setAgreed]           = useState(false);
  const [emailErr, setEmailErr]       = useState('');
  const [docErr, setDocErr]           = useState('');
  const [agreedErr, setAgreedErr]     = useState('');

  const onEmailBlur = () => {
    if (email && !isStudentEmail(email))
      setEmailErr('Use the format: 2023123456@pampangastateu.edu.ph');
    else
      setEmailErr('');
  };

  const onFileChange = (e) => {
    const f = e.target.files?.[0] || null;
    if (!f) { setDoc(null); setDocErr(''); return; }
    const err = validateFile(f);
    if (err) { setDocErr(err); setDoc(null); e.target.value = ''; return; }
    setDoc(f); setDocErr('');
  };

  const removeFile = () => {
    setDoc(null); setDocErr('');
    const inp = document.getElementById('req-doc');
    if (inp) inp.value = '';
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!isStudentEmail(email)) {
      setEmailErr('Use the format: 2023123456@pampangastateu.edu.ph');
      return;
    }
    if (!doc) { setDocErr('Please upload your PampangaStateU Student ID or COR.'); return; }
    if (!firstName || !lastName) return;
    if (!agreed) {
      setAgreedErr('Please agree to the Terms and Privacy Policy before submitting your request.');
      return;
    }

    const fd = new FormData();
    fd.append('first_name', firstName.trim());
    fd.append('last_name', lastName.trim());
    fd.append('email', email.trim().toLowerCase());
    fd.append('requested_role', role);
    fd.append('document', doc);
    onSubmit(fd);
  };

  // Shared input class
  const inputCls = `w-full px-4 py-2.5 rounded-lg border text-sm outline-none transition-colors ${
    isDark
      ? 'bg-white/[0.04] border-white/10 text-gray-200 placeholder-gray-500 focus:border-blue-500/40'
      : 'bg-white border-gray-200 text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100'
  }`;
  const labelCls = `block text-sm font-medium mb-1.5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`;
  const errCls   = `text-xs mt-1 ${isDark ? 'text-rose-400' : 'text-rose-600'}`;

  const canSubmit = firstName && lastName && email && !emailErr && doc && !docErr && agreed && !isLoading;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">

      {/* Validation info card */}
      <div className={`rounded-xl border p-4 flex gap-3 ${
        isDark ? 'bg-blue-500/[0.07] border-blue-500/20' : 'bg-blue-50 border-blue-100'
      }`}>
        <Search className="w-5 h-5 flex-shrink-0 mt-0.5 text-primary" aria-hidden="true" />
        <p className={`text-xs leading-relaxed ${isDark ? 'text-blue-300' : 'text-blue-700'}`}>
          THESYS+ verifies your <strong>PampangaStateU email</strong>, <strong>university identity</strong>,
          and <strong>CCS/program eligibility</strong> from your uploaded document before account activation.
        </p>
      </div>

      {/* Name row */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="req-first" className={labelCls}>First Name</label>
          <input
            id="req-first" type="text" value={firstName} required
            onChange={e => setFirstName(e.target.value)}
            placeholder="Juan" disabled={isLoading}
            className={inputCls}
          />
        </div>
        <div>
          <label htmlFor="req-last" className={labelCls}>Last Name</label>
          <input
            id="req-last" type="text" value={lastName} required
            onChange={e => setLastName(e.target.value)}
            placeholder="Dela Cruz" disabled={isLoading}
            className={inputCls}
          />
        </div>
      </div>

      {/* Email */}
      <div>
        <label htmlFor="req-email" className={labelCls}>PampangaStateU Institutional Email</label>
        <input
          id="req-email" type="email" value={email} required
          onChange={e => { setEmail(e.target.value); if (emailErr) setEmailErr(''); }}
          onBlur={onEmailBlur}
          placeholder="2023123456@pampangastateu.edu.ph"
          disabled={isLoading}
          aria-invalid={!!emailErr}
          className={`${inputCls} ${emailErr ? (isDark ? 'border-rose-500/50' : 'border-rose-400') : ''}`}
        />
        {emailErr
          ? <p className={errCls}>{emailErr}</p>
          : <p className={`text-xs mt-1 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
              Use your PampangaStateU student number: studentnumber@pampangastateu.edu.ph
            </p>
        }
      </div>

      {/* Role */}
      <div>
        <span className={labelCls}>Requested Role</span>
        <div className="flex gap-5 mt-1">
          {['student', 'faculty'].map(r => (
            <label key={r} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio" name="req-role" value={r}
                checked={role === r}
                onChange={() => setRole(r)}
                disabled={isLoading}
                className="accent-blue-600"
              />
              <span className={`text-sm capitalize ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{r}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Document upload */}
      <div>
        <label className={labelCls}>
          Student ID or Certificate of Registration
        </label>
        <p className={`text-xs mb-2 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
          Upload a clear PampangaStateU Student ID or Certificate of Registration.
          Accepted: PNG · JPG · PDF · max 10 MB
        </p>

        {!doc ? (
          <label
            htmlFor="req-doc"
            className={`flex items-center gap-3 px-4 py-3 rounded-lg border border-dashed cursor-pointer transition-colors ${
              isDark
                ? 'border-white/20 hover:border-blue-500/40 hover:bg-blue-500/[0.06]'
                : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50/50'
            }`}
          >
            <svg className={`w-5 h-5 flex-shrink-0 ${isDark ? 'text-gray-400' : 'text-gray-500'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
            </svg>
            <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              Click to upload document
            </span>
            <input
              id="req-doc" type="file"
              accept=".png,.jpg,.jpeg,.pdf,image/png,image/jpeg,application/pdf"
              onChange={onFileChange}
              disabled={isLoading}
              className="sr-only"
            />
          </label>
        ) : (
          <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${
            isDark ? 'border-white/10 bg-white/[0.03]' : 'border-gray-200 bg-gray-50'
          }`}>
            <svg className={`w-5 h-5 flex-shrink-0 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>
            </svg>
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium truncate ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>{doc.name}</p>
              <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>{fmtBytes(doc.size)}</p>
            </div>
            <button type="button" onClick={removeFile} disabled={isLoading}
              className={`flex-shrink-0 transition-colors ${isDark ? 'text-gray-600 hover:text-rose-400' : 'text-gray-400 hover:text-rose-500'}`}
              aria-label="Remove file">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
        )}

        {docErr && <p className={errCls}>{docErr}</p>}
      </div>

      {/* Agreement checkbox */}
      <div>
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => {
              setAgreed(e.target.checked);
              if (e.target.checked) setAgreedErr('');
            }}
            disabled={isLoading}
            className="mt-0.5 accent-blue-600 cursor-pointer"
          />
          <span className={`text-sm leading-relaxed ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
            I confirm that the information I provided is accurate, and I agree to the{' '}
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                onOpenLegal('terms');
              }}
              className={`font-medium underline hover:no-underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}
            >
              Terms
            </button>
            {' '}and{' '}
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                onOpenLegal('privacy');
              }}
              className={`font-medium underline hover:no-underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}
            >
              Privacy Policy
            </button>
            {' '}of THESYS+.
          </span>
        </label>
        {agreedErr ? (
          <p className={errCls}>{agreedErr}</p>
        ) : (
          <p className={`text-xs mt-2 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
            Your PampangaStateU institutional email and uploaded document will be used only for account verification and eligibility review.
          </p>
        )}
      </div>

      {/* Server error */}
      {error && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${
          isDark
            ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            : 'bg-rose-50 border-rose-200 text-rose-700'
        }`}>
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? <><Spinner size="sm" /> Submitting…</> : 'Submit Access Request'}
      </button>
    </form>
  );
}
