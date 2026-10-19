/**
 * FacultyRequestForm — /request-access?role=faculty
 *
 * Faculty send name and email only, no document; an administrator reviews
 * the request and, once approved, the set-password link arrives by email.
 * Email rule mirrors the backend: @pampangastateu.edu.ph with a local part
 * that is NOT all digits (all-digit addresses are student numbers).
 */

import { useState } from 'react';
import Spinner from '../ui/Spinner';

const FACULTY_EMAIL_RE = /^(?![0-9]+@)[^@\s]+@pampangastateu\.edu\.ph$/i;
const STUDENT_EMAIL_RE = /^[0-9]+@pampangastateu\.edu\.ph$/i;

export const FACULTY_DOMAIN_MSG = 'Use your PampangaStateU email (e.g. firstname.lastname@pampangastateu.edu.ph).';

// 'student' | 'domain' | '' for the current address.
function emailProblem(v) {
  const e = (v || '').trim();
  if (FACULTY_EMAIL_RE.test(e)) return '';
  return STUDENT_EMAIL_RE.test(e) ? 'student' : 'domain';
}

export default function FacultyRequestForm({ onSubmit, error, isLoading, onOpenLegal, onSwitchToStudent }) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName]   = useState('');
  const [email, setEmail]         = useState('');
  const [agreed, setAgreed]       = useState(false);
  const [emailErr, setEmailErr]   = useState('');
  const [agreedErr, setAgreedErr] = useState('');

  const checkEmail = () => {
    const problem = email ? emailProblem(email) : '';
    setEmailErr(problem);
    return problem;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!email || checkEmail()) { if (!email) setEmailErr('domain'); return; }
    if (!firstName.trim() || !lastName.trim()) return;
    if (!agreed) {
      setAgreedErr('Please agree to the Terms and Privacy Policy before submitting your request.');
      return;
    }
    onSubmit({
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: email.trim().toLowerCase(),
      requested_role: 'faculty',
    });
  };

  const inputCls = 'w-full px-4 py-2.5 rounded-lg border text-sm outline-none transition-colors thesys-input';
  const labelCls = 'block text-sm font-medium mb-1.5 text-body';
  const errCls   = 'text-xs mt-1 text-danger';
  const legalBtn = 'font-medium underline hover:no-underline text-primary';

  const canSubmit = firstName && lastName && email && !emailErr && agreed && !isLoading;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="fac-first" className={labelCls}>First Name</label>
          <input id="fac-first" type="text" value={firstName} required placeholder="Maria" disabled={isLoading}
            onChange={(e) => setFirstName(e.target.value)} className={inputCls} />
        </div>
        <div>
          <label htmlFor="fac-last" className={labelCls}>Last Name</label>
          <input id="fac-last" type="text" value={lastName} required placeholder="Santos" disabled={isLoading}
            onChange={(e) => setLastName(e.target.value)} className={inputCls} />
        </div>
      </div>

      <div>
        <label htmlFor="fac-email" className={labelCls}>PampangaStateU Email</label>
        <input id="fac-email" type="email" value={email} required disabled={isLoading}
          placeholder="firstname.lastname@pampangastateu.edu.ph"
          onChange={(e) => { setEmail(e.target.value); if (emailErr) setEmailErr(''); }}
          onBlur={checkEmail}
          aria-invalid={!!emailErr}
          aria-describedby="fac-email-note"
          className={`${inputCls} ${emailErr ? 'border-danger' : ''}`} />
        <div id="fac-email-note" aria-live="polite">
          {emailErr === 'student' ? (
            <p className={errCls}>
              This looks like a student email.{' '}
              <button type="button" onClick={onSwitchToStudent}
                className="font-semibold underline underline-offset-2 text-[color:var(--color-primary)] hover:no-underline">
                Request access as a Student instead
              </button>.
            </p>
          ) : emailErr === 'domain' ? (
            <p className={errCls}>{FACULTY_DOMAIN_MSG}</p>
          ) : (
            <p className="text-xs mt-1.5 text-muted">The faculty address you use at PampangaStateU.</p>
          )}
        </div>
      </div>

      <div>
        <label className="flex items-start gap-3 cursor-pointer">
          <input type="checkbox" checked={agreed} disabled={isLoading}
            onChange={(e) => { setAgreed(e.target.checked); if (e.target.checked) setAgreedErr(''); }}
            className="mt-0.5 accent-blue-600 cursor-pointer" />
          <span className="text-sm leading-relaxed text-body">
            I confirm that the information I provided is accurate, and I agree to the{' '}
            <button type="button" onClick={(e) => { e.preventDefault(); onOpenLegal('terms'); }} className={legalBtn}>Terms</button>
            {' '}and{' '}
            <button type="button" onClick={(e) => { e.preventDefault(); onOpenLegal('privacy'); }} className={legalBtn}>Privacy Policy</button>
            {' '}of THESYS+.
          </span>
        </label>
        {agreedErr && <p className={errCls}>{agreedErr}</p>}
      </div>

      {error && (
        <div className="rounded-lg border px-4 py-3 text-sm bg-danger-bg border-danger-border text-danger-text">
          {error}
        </div>
      )}

      <button type="submit" disabled={!canSubmit}
        className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-primary-solid text-white text-sm font-semibold hover:bg-primary-solid-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
        {isLoading ? <><Spinner size="sm" /> Submitting…</> : 'Submit for Review'}
      </button>
    </form>
  );
}
