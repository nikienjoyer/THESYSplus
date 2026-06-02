/**
 * App — Route definitions.
 *
 * / (LandingPage) renders outside MainLayout — it owns its own navbar.
 * All auth routes remain nested under MainLayout unchanged.
 *
 * ProtectedRoute wraps every authenticated page. It renders a full-screen
 * spinner while AuthContext is still initialising (silent token refresh
 * in flight), then redirects to /sign-in?reason=session_expired if the
 * user is not authenticated. This centralises auth-guarding in one place
 * so individual pages do not need their own useEffect + navigate guards.
 *
 * Requirements: 12 (Landing page), 25 (folder structure).
 */

import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, Outlet, Link } from 'react-router-dom';
import { TooltipProvider } from './components/shadcn/tooltip';
import { useAuth } from './hooks/useAuth';
import { useTheme } from './context/ThemeContext';
import Spinner from './components/ui/Spinner';
import AuthLayout from './components/layout/AuthLayout';
import LandingPage from './pages/LandingPage';
import SignInPage from './pages/SignInPage';
import RequestAccessPage from './pages/RequestAccessPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import RepositoryPage from './pages/RepositoryPage';
import ThesisDetailPage from './pages/ThesisDetailPage';
import UploadThesisPage from './pages/UploadThesisPage';
import TitleSimilarityPage from './pages/TitleSimilarityPage';
import TrendAnalysisPage from './pages/TrendAnalysisPage';
import ProfilePage from './pages/ProfilePage';
import SettingsPage from './pages/SettingsPage';
import AnalyticsDashboardPage from './pages/AnalyticsDashboardPage';
import VerifyEmailPage from './pages/VerifyEmailPage';

// ---------------------------------------------------------------------------
// NotFound — minimal 404 page for unmatched routes
// ---------------------------------------------------------------------------
function NotFound() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div
      className={`min-h-screen flex flex-col items-center justify-center px-4 text-center transition-colors duration-300 ${
        isDark ? 'bg-[#080d24]' : 'bg-slate-50'
      }`}
    >
      <div
        className={`w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mb-6 ${
          isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
        }`}
      >
        🎓
      </div>
      <h1
        className={`text-6xl font-extrabold tracking-tighter mb-3 ${
          isDark ? 'text-white' : 'text-gray-900'
        }`}
      >
        404
      </h1>
      <p className={`text-lg font-semibold mb-2 ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
        Page not found
      </p>
      <p className={`text-sm mb-8 max-w-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/"
        className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 active:bg-blue-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
      >
        Back to Home
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProtectedRoute — single auth gate for all authenticated pages
// ---------------------------------------------------------------------------
function ProtectedRoute() {
  const { isAuthenticated, isInitializing } = useAuth();
  const { theme } = useTheme();
  const navigate = useNavigate();
  const isDark = theme === 'dark';

  useEffect(() => {
    if (!isInitializing && !isAuthenticated) {
      navigate('/sign-in?reason=session_expired', { replace: true });
    }
  }, [isInitializing, isAuthenticated, navigate]);

  // While the silent refresh is in flight, show a neutral full-screen spinner.
  // This prevents the brief blank screen / flash of the page before the redirect.
  if (isInitializing || !isAuthenticated) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
        <Spinner />
      </div>
    );
  }

  // Auth confirmed — render the matched child route
  return <Outlet />;
}

export default function App() {
  return (
    <BrowserRouter>
      <TooltipProvider delayDuration={300}>
        <Routes>
          {/* Public landing */}
          <Route path="/" element={<LandingPage />} />

          {/* All auth/public pages share AuthLayout (one header, one background) */}
          <Route element={<AuthLayout />}>
            <Route path="/sign-in"        element={<SignInPage />} />
            <Route path="/request-access" element={<RequestAccessPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email"   element={<VerifyEmailPage />} />
          </Route>

          {/* Protected pages — ProtectedRoute handles auth gate for all children */}
          <Route element={<ProtectedRoute />}>
            <Route path="/repository" element={<RepositoryPage />} />
            <Route path="/repository/:id" element={<ThesisDetailPage />} />
            <Route path="/upload" element={<UploadThesisPage />} />
            <Route path="/title-similarity" element={<TitleSimilarityPage />} />
            <Route path="/trend-analysis" element={<TrendAnalysisPage />} />
            <Route path="/analytics" element={<AnalyticsDashboardPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          {/* Catch-all — redirect unknown paths to home */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </TooltipProvider>
    </BrowserRouter>
  );
}
