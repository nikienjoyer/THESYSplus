/**
 * VerifyEmailPage — /verify-email?token=<plaintext>
 *
 * Body content only — background, header, and theme toggle
 * are provided by AuthLayout (parent route wrapper).
 *
 * Phase 2 additions:
 *   - Progress stepper on success state (step 2 complete, step 3 active)
 *   - Trust cue: "Your PampangaStateU institutional email is used to verify account ownership."
 */

import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle2, TriangleAlert } from 'lucide-react';
import client from '../api/client';
import { useTheme } from '../context/ThemeContext';

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

export default function VerifyEmailPage() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [state, setState]       = useState('loading'); // loading | success | error
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!token) {
      setState('error');
      setErrorMsg('No verification token found in the link. Please use the link from your email.');
      return;
    }

    let cancelled = false;
    client
      .get(`/auth/verify-email/?token=${encodeURIComponent(token)}`)
      .then(() => { if (!cancelled) setState('success'); })
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

  const cardBg = isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-slate-200 shadow-card';

  return (
    <div className="relative z-10 flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Branding */}
        <div className="flex flex-col items-center mb-8 select-none">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-4 ${
            isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
          }`}>🎓</div>
          <h1 className="text-3xl font-extrabold tracking-tighter leading-none mb-1">
            <span className={isDark ? 'text-white' : 'text-gray-900'}>THE</span>
            <span className="text-primary">SYS+</span>
          </h1>
          <p className={`text-xs tracking-widest uppercase font-medium mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            Email Verification
          </p>
        </div>

        {/* Progress stepper — only on success (step 2 = Set Password is now active) */}
        {state === 'success' && <ProgressStepper activeStep={2} isDark={isDark} />}

        <div className={`rounded-2xl border p-7 sm:p-9 ${cardBg}`}>

          {state === 'loading' && (
            <div className="flex flex-col items-center gap-3 py-4">
              <svg className="animate-spin h-8 w-8 text-blue-500" viewBox="0 0 24 24" fill="none">
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

          {state === 'success' && (
            <div className="text-center">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'
              }`}>
                <CheckCircle2 className="w-7 h-7 text-emerald-500" aria-hidden="true" />
              </div>
              <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Email Verified
              </h2>
              <p className={`text-sm mb-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                Your PampangaStateU email has been verified.
              </p>
              <p className={`text-sm mb-5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Please check your inbox for a separate email with instructions to set your password.
              </p>
              <Link to="/sign-in"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors">
                Go to Sign In
              </Link>
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
