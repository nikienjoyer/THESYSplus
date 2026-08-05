/**
 * VerifyEmailPage — /verify-email?token=<plaintext>
 *
 * Body content only — background, header, and theme toggle
 * are provided by AuthLayout (parent route wrapper).
 *
 * Single-email flow: the token in the link both verifies the address AND
 * (on success) unlocks the inline "Set Password" form on this same page —
 * the backend issues a setup-password token but never emails it, so no
 * second email is ever sent. Submitting the form advances the stepper to
 * "Account Ready".
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, TriangleAlert } from 'lucide-react';
import client from '../api/client';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import AuthBranding from '../components/brand/AuthBranding';

// Reuse the same stepper from RequestAccessPage — inline here to keep files self-contained
function ProgressStepper({ activeStep, isDark }) {
  // activeStep: 0-based index of the currently active step
  const STEPS = ['Submit Request', 'Verify Email', 'Set Password', 'Account Ready'];
  return (
    <div className="mb-6">
      <div className="flex items-center gap-0">
        {STEPS.map((label, i) => {
          const isComplete = i < activeStep;
          const isActive   = i === activeStep;
          return (
            <div key={label} className="flex items-center flex-1 min-w-0">
              <div className="flex flex-col items-center flex-shrink-0">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors ${
                  isComplete
                    ? 'bg-emerald-500 border-emerald-500 text-white'
                    : isActive
                    ? isDark ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white' : 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white'
                    : isDark ? 'bg-transparent border-white/20 text-gray-600' : 'bg-transparent border-gray-200 text-gray-400'
                }`}>
                  {isComplete ? (
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                    </svg>
                  ) : i + 1}
                </div>
                <span className={`text-[9px] mt-1 text-center leading-tight max-w-[52px] ${
                  isComplete
                    ? isDark ? 'text-emerald-400' : 'text-emerald-600'
                    : isActive
                    ? 'text-primary font-semibold'
                    : isDark ? 'text-gray-600' : 'text-gray-400'
                }`}>{label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-1 mb-4 rounded-full transition-colors ${
                  i < activeStep
                    ? 'bg-emerald-500'
                    : isDark ? 'bg-white/10' : 'bg-gray-200'
                }`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function validateStrength(pw) {
  if (pw.length < 12)         return 'Password must be at least 12 characters.';
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

export default function VerifyEmailPage() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  // loading -> set_password -> success, or error at any point before set_password
  const [state, setState]         = useState('loading');
  const [errorMsg, setErrorMsg]   = useState('');
  const [setupToken, setSetupToken] = useState('');

  // Password form state
  const [newPw, setNewPw]             = useState('');
  const [confirmPw, setConfirmPw]     = useState('');
  const [showNew, setShowNew]         = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [newErr, setNewErr]           = useState('');
  const [confirmErr, setConfirmErr]   = useState('');
  const [serverErr, setServerErr]     = useState('');
  const [linkExpired, setLinkExpired] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!token) {
      setState('error');
      setErrorMsg('No verification token found in the link. Please use the link from your email.');
      return;
    }

    let cancelled = false;
    client
      .get(`/auth/verify-email/?token=${encodeURIComponent(token)}`)
      .then((res) => {
        if (cancelled) return;
        setSetupToken(res.data?.setup_token || '');
        setState('set_password');
      })
      .catch((err) => {
        if (cancelled) return;
        const code = err?.response?.data?.error?.code;
        const msg  = err?.response?.data?.error?.message;
        const map = {
          TOKEN_EXPIRED:      'This verification link has expired. Please submit a new access request.',
          TOKEN_ALREADY_USED: 'This verification link has already been used. If you already set your password, you can sign in.',
          TOKEN_INVALID:      'This verification link is invalid or has already been used.',
        };
        setErrorMsg(map[code] || msg || 'An error occurred. Please try again.');
        setState('error');
      });

    return () => { cancelled = true; };
  }, [token]);

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    const strengthErr = validateStrength(newPw);
    if (strengthErr) { setNewErr(strengthErr); return; }
    if (newPw !== confirmPw) { setConfirmErr('Passwords do not match.'); return; }
    setIsSubmitting(true);
    setServerErr('');
    try {
      await client.post('/auth/setup-password/', { token: setupToken, new_password: newPw });
      setState('success');
    } catch (err) {
      const code = err?.response?.data?.error?.code;
      const msg  = err?.response?.data?.error?.message;
      if (code === 'INVALID_RESET_TOKEN') {
        setLinkExpired(true);
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

  const cardBg = isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-slate-200 shadow-card';
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

  // activeStep for the stepper: Set Password active while filling the form,
  // Account Ready active once the password has been set.
  const activeStep = state === 'success' ? 3 : 2;

  return (
    <div className="relative z-10 flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Branding */}
        <AuthBranding subtitle="Email Verification" isDark={isDark} />

        {/* Progress stepper — shown once the email is verified */}
        {(state === 'set_password' || state === 'success') && (
          <ProgressStepper activeStep={activeStep} isDark={isDark} />
        )}

        <div className={`rounded-2xl border p-7 sm:p-9 ${cardBg}`}>

          {state === 'loading' && (
            <div className="flex flex-col items-center gap-3 py-4">
              <svg className="animate-spin h-8 w-8 text-primary" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" className="opacity-15"/>
                <path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
              <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Verifying your email…
              </p>
              {/* Trust cue */}
              <p className={`text-xs text-center max-w-xs ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                Your PampangaStateU institutional email is used to verify account ownership.
              </p>
            </div>
          )}

          {state === 'set_password' && (
            linkExpired ? (
              <div className="text-center">
                <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                  isDark ? 'bg-rose-500/15' : 'bg-rose-50'
                }`}>
                  <TriangleAlert className="w-7 h-7 text-rose-500" aria-hidden="true" />
                </div>
                <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                  Link expired
                </h2>
                <p className={`text-sm mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                  This account setup link is invalid or has expired.
                </p>
                <p className={`text-xs mb-6 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  Your email is already verified — use "Forgot your password?" on the sign-in
                  page to request a new setup link.
                </p>
                <Link to="/forgot-password"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
                  Request New Link
                </Link>
              </div>
            ) : (
              <form onSubmit={handlePasswordSubmit} noValidate>
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
                  <label htmlFor="ve-new" className={labelCls}>New Password</label>
                  <div className="relative">
                    <input id="ve-new"
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
                  <label htmlFor="ve-confirm" className={labelCls}>Confirm Password</label>
                  <div className="relative">
                    <input id="ve-confirm"
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
            )
          )}

          {state === 'success' && (
            <div className="text-center">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'
              }`}>
                <CheckCircle2 className="w-7 h-7 text-emerald-500" aria-hidden="true" />
              </div>
              <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Account Ready
              </h2>
              <p className={`text-sm mb-5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Your password has been set and your THESYS+ account is now active.
              </p>
              <button
                type="button"
                onClick={() => navigate('/sign-in?reason=account_setup')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
                Go to Sign In
              </button>
            </div>
          )}

          {state === 'error' && (
            <div className="text-center">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                isDark ? 'bg-rose-500/15' : 'bg-rose-50'
              }`}>
                <TriangleAlert className="w-7 h-7 text-rose-500" aria-hidden="true" />
              </div>
              <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Verification Failed
              </h2>
              <p className={`text-sm mb-5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                {errorMsg}
              </p>
              <div className="flex flex-col items-center gap-2">
                <Link to="/request-access"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
                  Submit a New Request
                </Link>
                <Link to="/sign-in"
                  className={`text-sm ${isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-500 hover:text-gray-700'}`}>
                  Return to Sign In
                </Link>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
