/**
 * ForgotPasswordPage — /forgot-password
 *
 * Body content only — background, header, and theme toggle
 * are provided by AuthLayout (parent route wrapper).
 *
 * Requirements: 5.1, 5.2, 15.1, 15.2
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Lock, Mail } from 'lucide-react';
import client from '../api/client';
import Spinner from '../components/ui/Spinner';
import AuthBranding from '../components/brand/AuthBranding';

const INSTITUTIONAL_EMAIL_RE = /^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)*pampangastateu\.edu\.ph$/i;

function mapError(err) {
  const code = err?.response?.data?.error?.code;
  const msg  = err?.response?.data?.error?.message;
  if (code === 'INVALID_EMAIL_DOMAIN')          return 'Please use your institutional email address.';
  if (code === 'RATE_LIMITED_FORGOT_PASSWORD')  return 'Too many requests. Please try again later.';
  return msg || 'An error occurred. Please try again.';
}

export default function ForgotPasswordPage() {

  const [email, setEmail]         = useState('');
  const [emailErr, setEmailErr]   = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState('');
  const [success, setSuccess]     = useState(false);

  const validateEmail = (v) => {
    if (v && !INSTITUTIONAL_EMAIL_RE.test(v.trim())) {
      setEmailErr('Please use your institutional email address.');
      return false;
    }
    setEmailErr('');
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateEmail(email)) return;
    setIsLoading(true);
    setError('');
    try {
      await client.post('/auth/forgot-password/', { email: email.trim().toLowerCase() });
      setSuccess(true);
    } catch (err) {
      setError(mapError(err));
    } finally {
      setIsLoading(false);
    }
  };

  const cardBg  = 'bg-surface border-border-default shadow-sm';
  const inputCls = `w-full px-4 py-2.5 rounded-lg border text-sm outline-none transition-colors ${
    'thesys-input'
  }`;

  return (
    <div className="relative z-10 flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Branding */}
        <AuthBranding subtitle={success ? 'Check your email' : 'Forgot your password?'} />

        <div className={`rounded-2xl border p-6 sm:p-8 ${cardBg}`}>
          {success ? (
            <div className="text-center">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4 bg-success-bg`}>
                <Mail className="w-7 h-7 text-emerald-500" aria-hidden="true" />
              </div>
              <h2 className={`text-xl font-bold mb-2 text-ink`}>
                Reset link sent
              </h2>
              <p className={`text-sm mb-1 text-body`}>
                If an account exists for that email, a password reset link has been sent.
              </p>
              <p className={`text-xs mb-6 text-muted`}>
                The link expires in 30 minutes. Check your spam folder if you don't see it.
              </p>
              <Link to="/sign-in"
                className="text-sm font-medium hover:underline text-primary">
                Return to Sign In
              </Link>
            </div>
          ) : (
            <>
              <p className={`text-sm mb-5 text-body`}>
                Enter your institutional email and we'll send you a link to reset your password.
              </p>
              {/* Security trust cue */}
              <p className={`text-xs mb-4 flex items-center gap-1.5 text-subtle`}>
                <Lock className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
                For security, password reset links expire after 30 minutes.
              </p>
              <form onSubmit={handleSubmit} noValidate>
                <div className="mb-4">
                  <label htmlFor="fp-email"
                    className={`block text-sm font-medium mb-1.5 text-body`}>
                    Institutional Email
                  </label>
                  <input
                    id="fp-email" type="email" required
                    value={email}
                    onChange={e => { setEmail(e.target.value); if (emailErr) setEmailErr(''); }}
                    onBlur={() => validateEmail(email)}
                    placeholder="2012345678@pampangastateu.edu.ph"
                    disabled={isLoading}
                    aria-invalid={!!emailErr}
                    className={`${inputCls} ${emailErr ? ('border-danger') : ''}`}
                  />
                  {emailErr && (
                    <p className={`text-xs mt-1 text-danger`}>{emailErr}</p>
                  )}
                </div>

                {error && (
                  <div className={`rounded-lg border px-4 py-3 text-sm mb-4 bg-danger-bg border-danger-border text-danger-text`}>
                    {error}
                  </div>
                )}

                <button type="submit" disabled={isLoading || !!emailErr || !email}
                  className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-primary-solid text-white text-sm font-semibold hover:bg-primary-solid-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                  {isLoading ? <><Spinner size="sm" /> Sending…</> : 'Send Reset Link'}
                </button>
              </form>
            </>
          )}
        </div>

        {/* Footer */}
        {!success && (
          <p className={`mt-5 text-center text-sm text-body`}>
            Remember your password?{' '}
            <Link to="/sign-in" className="font-medium hover:underline text-primary">
              Sign In
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
