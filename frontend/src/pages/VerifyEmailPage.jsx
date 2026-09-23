/**
 * VerifyEmailPage — /verify-email?token=<plaintext>
 *
 * Body content only — background, header, and theme toggle
 * are provided by AuthLayout (parent route wrapper).
 *
 * A CONFIRMATION RECEIPT. This page no longer sets passwords.
 *
 * Clicking the emailed link verifies the address and provisions the account,
 * and that is all it does here. The password is set elsewhere:
 *
 *   - The tab that SUBMITTED the access request polls
 *     GET /auth/request-access/status/, and when that reports `verified` it
 *     receives a freshly minted setup token and hosts the password form. The
 *     user finishes in the tab they started in, where the progress stepper
 *     lives — which is why there is no stepper on this page.
 *
 *   - Anyone without that tab (different device, closed window, claim window
 *     elapsed) uses /forgot-password, which issues a working setup link for a
 *     verified user whose password is still unset. Every state below offers
 *     that route; it is the only way forward for those users, so do not
 *     remove it.
 *
 * The route and query parameter are unchanged — email_verification.py builds
 * this URL from FRONTEND_BASE_URL and links already sitting in inboxes must
 * keep working.
 */

import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle2, TriangleAlert } from 'lucide-react';
import client from '../api/client';
import { useTheme } from '../context/ThemeContext';
import AuthBranding from '../components/brand/AuthBranding';

export default function VerifyEmailPage() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  // 'loading' | 'verified' | 'already_verified' | 'error'
  const [state, setState]       = useState('loading');
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
      .then(() => {
        if (cancelled) return;
        setState('verified');
      })
      .catch((err) => {
        if (cancelled) return;
        const code = err?.response?.data?.error?.code;
        const msg  = err?.response?.data?.error?.message;

        // TOKEN_ALREADY_USED is NOT a failure. It is what a reload of this page
        // produces, and what a second click on the same link produces — in both
        // cases verification already succeeded. Treating it as an error was
        // actively harmful: it pushed the user toward resubmitting their access
        // request, which means re-uploading an ID document, burning one of their
        // 3/day submissions, and most likely hitting DUPLICATE_REQUEST_PENDING
        // or EMAIL_ALREADY_REGISTERED because their User row already exists.
        if (code === 'TOKEN_ALREADY_USED') {
          setState('already_verified');
          return;
        }

        const map = {
          TOKEN_EXPIRED: 'This verification link has expired. Please submit a new access request.',
          TOKEN_INVALID: 'This verification link is invalid or has already been used.',
        };
        setErrorMsg(map[code] || msg || 'An error occurred. Please try again.');
        setState('error');
      });

    return () => { cancelled = true; };
  }, [token]);

  const cardBg = isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-slate-200 shadow-card';
  const primaryBtn = 'inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400';
  const quietLink = `text-sm ${isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-500 hover:text-gray-700'}`;

  return (
    <div className="relative z-10 flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Branding */}
        <AuthBranding subtitle="Email Verification" isDark={isDark} />

        {/* No ProgressStepper here — the stepper belongs to the tab that is
            actually progressing through the flow. */}

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

          {state === 'verified' && (
            <div className="text-center">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'
              }`}>
                <CheckCircle2 className="w-7 h-7 text-emerald-500" aria-hidden="true" />
              </div>
              <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Your email has been verified.
              </h2>
              <p className={`text-sm mb-5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                You can now return to the tab where you started and close this one.
              </p>
              {/* Escape hatch — the only route forward for anyone whose original
                  tab is gone. Quieter than the primary message, never absent. */}
              <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                Don&apos;t have that tab open?{' '}
                <Link to="/forgot-password" className="font-medium hover:underline text-primary">
                  Request a password setup link
                </Link>
              </p>
            </div>
          )}

          {state === 'already_verified' && (
            <div className="text-center">
              {/* Deliberately the same positive treatment as `verified` — no
                  rose, no TriangleAlert. Nothing has gone wrong here. */}
              <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 ${
                isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'
              }`}>
                <CheckCircle2 className="w-7 h-7 text-emerald-500" aria-hidden="true" />
              </div>
              <h2 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                Your email is already verified
              </h2>
              <p className={`text-sm mb-5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                Verification is complete, so there is nothing more to do on this page.
                If you haven&apos;t set a password yet, you can request a setup link below.
              </p>
              {/* Both actions are offered rather than choosing between them.
                  Picking one would require the backend to disclose whether a
                  password exists — an unnecessary leak to whoever holds a used
                  link — and both are harmless for either user. */}
              <div className="flex flex-col items-center gap-3">
                <Link to="/forgot-password" className={primaryBtn}>
                  Request a password setup link
                </Link>
                <Link to="/sign-in" className={quietLink}>
                  Sign In
                </Link>
              </div>
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
              {/* Retained for this state only. Past 24 hours the link really is
                  dead and resubmitting really is the right action. */}
              <div className="flex flex-col items-center gap-2">
                <Link to="/request-access" className={primaryBtn}>
                  Submit a New Request
                </Link>
                <Link to="/sign-in" className={quietLink}>
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
