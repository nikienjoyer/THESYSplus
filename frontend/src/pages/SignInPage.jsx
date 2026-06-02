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
import { useTheme } from '../context/ThemeContext';
import { SignInCard } from '../components/auth';
import Alert from '../components/ui/Alert';

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
    default:
      return null;
  }
}

export default function SignInPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { signIn } = useAuth();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

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
      navigate('/repository');
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
        <div className="flex flex-col items-center mb-8 select-none">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-4 ${
            isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
          }`}>🎓</div>
          <h1 className="text-3xl font-extrabold tracking-tighter leading-none mb-1">
            <span className={isDark ? 'text-white' : 'text-gray-900'}>THE</span>
            <span className={isDark ? 'text-blue-400' : 'text-blue-600'}>SYS+</span>
          </h1>
          <p className={`text-xs tracking-widest uppercase font-medium mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            Sign in to continue
          </p>
        </div>

        {/* Context banner */}
        {banner && (
          <Alert className={`mb-5 ${
            banner.variant === 'success'
              ? isDark ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : isDark ? 'bg-blue-500/10 border-blue-500/30 text-blue-300' : 'bg-blue-50 border-blue-200 text-blue-800'
          }`}>
            {banner.message}
          </Alert>
        )}

        {/* Sign-in card */}
        <div className={`rounded-2xl border p-6 sm:p-8 ${
          isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-gray-200 shadow-sm'
        }`}>
          <SignInCard onSubmit={handleSubmit} error={error} isLoading={isLoading} />
        </div>

        {/* Footer — all internal links use <Link> to avoid full reloads */}
        <div className="mt-5 flex flex-col items-center gap-2">
          <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
            Don&rsquo;t have an account?{' '}
            <Link to="/request-access" className={`font-medium hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
              Request Access
            </Link>
          </p>
          <Link to="/forgot-password"
            className={`text-sm hover:underline ${isDark ? 'text-gray-500 hover:text-gray-300' : 'text-gray-500 hover:text-gray-700'}`}>
            Forgot your password?
          </Link>
        </div>

      </div>
    </div>
  );
}
