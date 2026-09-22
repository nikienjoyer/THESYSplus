/**
 * SetPasswordForm — the "set your password" step of account activation.
 *
 * Extracted verbatim from VerifyEmailPage so BOTH surfaces can host it:
 *   - RequestAccessPage, once its claim poll reports `verified`
 *   - VerifyEmailPage, once the emailed link is consumed
 *
 * VerifyEmailPage still carries its own inline copy for now; a later commit
 * deletes that and imports this instead. Extracting rather than duplicating
 * is what makes that commit a deletion rather than a second migration.
 *
 * The setup token is a PROP, never storage. It is short-lived and single-use,
 * so it lives in the caller's component state and dies with the tab.
 *
 * Props:
 *   setupToken  — plaintext password-setup token from the server
 *   onSuccess   — called after POST /auth/setup-password/ succeeds; the caller
 *                 owns the "Account Ready" state and any storage cleanup
 *   isDark      — theme flag, matching the convention on the auth pages
 *   idPrefix    — prefix for input ids, so two instances can never collide
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, TriangleAlert } from 'lucide-react';
import client from '../../api/client';
import Spinner from '../ui/Spinner';

/** 12+ characters, at least one letter, at least one digit.
 *
 * Kept module-local (not exported) so this file exports only its component —
 * `react-refresh/only-export-components` flags a mixed export surface, and the
 * form is the only consumer anyway. */
function validateStrength(pw) {
  if (pw.length < 12)        return 'Password must be at least 12 characters.';
  if (!/[a-zA-Z]/.test(pw))  return 'Password must include at least one letter.';
  if (!/[0-9]/.test(pw))     return 'Password must include at least one digit.';
  return '';
}

function EyeIcon({ off }) {
  return off ? (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"/>
    </svg>
  ) : (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
    </svg>
  );
}

export default function SetPasswordForm({
  setupToken,
  onSuccess,
  isDark = false,
  idPrefix = 'sp',
}) {
  const [newPw, setNewPw]               = useState('');
  const [confirmPw, setConfirmPw]       = useState('');
  const [showNew, setShowNew]           = useState(false);
  const [showConfirm, setShowConfirm]   = useState(false);
  const [newErr, setNewErr]             = useState('');
  const [confirmErr, setConfirmErr]     = useState('');
  const [serverErr, setServerErr]       = useState('');
  const [tokenInvalid, setTokenInvalid] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const strengthErr = validateStrength(newPw);
    if (strengthErr) { setNewErr(strengthErr); return; }
    if (newPw !== confirmPw) { setConfirmErr('Passwords do not match.'); return; }
    setIsSubmitting(true);
    setServerErr('');
    try {
      await client.post('/auth/setup-password/', { token: setupToken, new_password: newPw });
      onSuccess?.();
    } catch (err) {
      const code = err?.response?.data?.error?.code;
      const msg  = err?.response?.data?.error?.message;
      if (code === 'INVALID_RESET_TOKEN') {
        setTokenInvalid(true);
      } else if (code === 'WEAK_PASSWORD') {
        setServerErr('Password must be at least 12 characters and include both letters and digits.');
      } else if (code === 'RATE_LIMITED_IP' || code === 'RATE_LIMITED_RESET_PASSWORD') {
        setServerErr('Too many requests. Please try again later.');
      } else {
        setServerErr(msg || 'An error occurred. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputCls = (hasErr) => `w-full px-4 py-2.5 rounded-lg border text-sm outline-none transition-colors pr-11 ${
    isDark
      ? `bg-white/[0.04] text-gray-200 placeholder-gray-500 focus:border-blue-500/40 ${hasErr ? 'border-rose-500/50' : 'border-white/10'}`
      : `bg-white text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 ${hasErr ? 'border-rose-400' : 'border-gray-200'}`
  }`;
  const eyeCls = `absolute right-3 top-1/2 -translate-y-1/2 transition-colors focus:outline-none ${
    isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'
  }`;
  const labelCls = `block text-sm font-medium mb-1.5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`;
  const errCls   = `text-xs mt-1 ${isDark ? 'text-rose-400' : 'text-rose-600'}`;
  const hintCls  = `text-xs mt-1 ${isDark ? 'text-gray-600' : 'text-gray-400'}`;

  // INVALID_RESET_TOKEN means the setup token was consumed or aged out between
  // being issued and being submitted. The email address is already verified at
  // this point, so the recovery route is forgot-password — NOT resubmitting the
  // access request, which would mean re-uploading an ID document for nothing.
  if (tokenInvalid) {
    return (
      <div className="text-center">
        <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
          isDark ? 'bg-rose-500/15' : 'bg-rose-50'
        }`}>
          <TriangleAlert className="w-7 h-7 text-rose-500" aria-hidden="true" />
        </div>
        <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
          Setup link expired
        </h2>
        <p className={`text-sm mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
          This account setup link is invalid or has expired.
        </p>
        <p className={`text-xs mb-6 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
          Your email is already verified — use &quot;Forgot your password?&quot; on the
          sign-in page to request a new setup link.
        </p>
        <Link to="/forgot-password"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
          Request New Link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="flex items-center gap-2 mb-1">
        <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" aria-hidden="true" />
        <h2 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
          Email Verified
        </h2>
      </div>
      <p className={`text-sm mb-5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
        Set a password below to activate your THESYS+ account.
      </p>

      {/* New password */}
      <div className="mb-4">
        <label htmlFor={`${idPrefix}-new`} className={labelCls}>New Password</label>
        <div className="relative">
          <input id={`${idPrefix}-new`}
            type={showNew ? 'text' : 'password'}
            value={newPw}
            onChange={e => { setNewPw(e.target.value); if (newErr) setNewErr(''); }}
            onBlur={() => { if (newPw) setNewErr(validateStrength(newPw)); }}
            placeholder="Enter new password"
            disabled={isSubmitting} required aria-invalid={!!newErr}
            className={inputCls(!!newErr)}
          />
          <button type="button" tabIndex={-1} onClick={() => setShowNew(v => !v)}
            className={eyeCls} aria-label={showNew ? 'Hide password' : 'Show password'}>
            <EyeIcon off={showNew} />
          </button>
        </div>
        {newErr
          ? <p className={errCls}>{newErr}</p>
          : <p className={hintCls}>At least 12 characters, including letters and digits.</p>
        }
      </div>

      {/* Confirm password */}
      <div className="mb-5">
        <label htmlFor={`${idPrefix}-confirm`} className={labelCls}>Confirm Password</label>
        <div className="relative">
          <input id={`${idPrefix}-confirm`}
            type={showConfirm ? 'text' : 'password'}
            value={confirmPw}
            onChange={e => { setConfirmPw(e.target.value); if (confirmErr) setConfirmErr(''); }}
            onBlur={() => { if (confirmPw && confirmPw !== newPw) setConfirmErr('Passwords do not match.'); }}
            placeholder="Confirm new password"
            disabled={isSubmitting} required aria-invalid={!!confirmErr}
            className={inputCls(!!confirmErr)}
          />
          <button type="button" tabIndex={-1} onClick={() => setShowConfirm(v => !v)}
            className={eyeCls} aria-label={showConfirm ? 'Hide password' : 'Show password'}>
            <EyeIcon off={showConfirm} />
          </button>
        </div>
        {confirmErr && <p className={errCls}>{confirmErr}</p>}
      </div>

      {serverErr && (
        <div className={`rounded-lg border px-4 py-3 text-sm mb-4 ${
          isDark ? 'bg-rose-500/10 border-rose-500/30 text-rose-300' : 'bg-rose-50 border-rose-200 text-rose-700'
        }`}>
          {serverErr}
        </div>
      )}

      <button type="submit"
        disabled={isSubmitting || !!newErr || !!confirmErr || !newPw || !confirmPw}
        className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
        {isSubmitting ? <><Spinner size="sm" /> Activating…</> : 'Set Up Password'}
      </button>
    </form>
  );
}
