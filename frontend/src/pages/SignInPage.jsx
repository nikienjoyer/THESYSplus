/**
 * SignInPage — /sign-in
 *
 * Body content only — background, header, and theme toggle
 * are provided by AuthLayout (parent route wrapper).
 *
 * Requirements: 1.1, 1.4, 9.7, 13.1, 13.3, 13.4, 13.5
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { SignInCard } from '../components/auth';
import Alert from '../components/ui/Alert';
import AuthBranding from '../components/brand/AuthBranding';

function mapErrorMessage(error) {
  const errorCode = error?.response?.data?.error?.code;
  const errorMessage = error?.response?.data?.error?.message;
  if (errorCode === 'INVALID_CREDENTIALS')  return 'Email or password is incorrect';
  if (errorCode === 'INVALID_EMAIL_DOMAIN') return 'Please use your institutional email address.';
  return errorMessage || 'An error occurred. Please try again.';
}

function getReasonBanner(reason) {
  switch (reason) {
    case 'IDLE_TIMEOUT':
      return { message: 'Your session expired due to inactivity. Please sign in again.', variant: 'info' };
    case 'session_expired':
      return { message: 'Your session has expired. Please sign in again.', variant: 'info' };
    case 'password_set':
      return { message: 'Your password has been set successfully. You can now sign in.', variant: 'success' };
    case 'account_setup':
      return { message: 'Account activated successfully! Please sign in with your new password.', variant: 'success' };
    default:
      return null;
  }
}

export default function SignInPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { signIn } = useAuth();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const reason = searchParams.get('reason');
  const banner = getReasonBanner(reason);

  useEffect(() => {
    if (reason) {
      const timer = setTimeout(() => {
        searchParams.delete('reason');
        navigate({ search: searchParams.toString() }, { replace: true });
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [reason, searchParams, navigate]);

  const handleSubmit = async ({ email, password, rememberMe }) => {
    setIsLoading(true);
    setError('');
    try {
      await signIn(email, password, rememberMe);
      navigate('/');
    } catch (err) {
      setError(mapErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative z-10 flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">

        {/* Branding */}
        <AuthBranding subtitle="Sign in to continue" />

        {/* Context banner */}
        {banner && (
          <Alert className={`mb-5 ${
            banner.variant === 'success'
              ? 'bg-success-bg border-success-border text-success-text'
              : 'bg-info-bg border-info-border text-info-text'
          }`}>
            {banner.message}
          </Alert>
        )}

        {/* Sign-in form — flat on the auth background, no nested frame */}
        <SignInCard onSubmit={handleSubmit} error={error} isLoading={isLoading} />

        {/* Footer — all internal links use <Link> to avoid full reloads */}
        <div className="mt-5 flex flex-col items-center gap-2">
          <p className={`text-sm text-body`}>
            Don&rsquo;t have an account?{' '}
            <Link to="/request-access" className={`font-medium hover:underline text-primary`}>
              Request Access
            </Link>
          </p>
          <Link to="/forgot-password"
            className={`text-sm hover:underline text-muted hover:text-body`}>
            Forgot your password?
          </Link>
        </div>

      </div>
    </div>
  );
}
