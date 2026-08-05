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
import Spinner from './components/ui/Spinner';
import AuthLayout from './components/layout/AuthLayout';
import ThesysLogo from './components/brand/ThesysLogo';
import LandingPage from './pages/LandingPage';
import SignInPage from './pages/SignInPage';
import RequestAccessPage from './pages/RequestAccessPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import RepositoryPage from './pages/RepositoryPage';
import ThesisDetailPage from './pages/ThesisDetailPage';
import TitleSimilarityPage from './pages/TitleSimilarityPage';
import TrendAnalysisPage from './pages/TrendAnalysisPage';
import ProfilePage from './pages/ProfilePage';
import SettingsPage from './pages/SettingsPage';
import AnalyticsDashboardPage from './pages/AnalyticsDashboardPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import { UploadModalProvider } from './context/UploadModalContext';
import UploadThesisModal from './components/upload/UploadThesisModal';

// ---------------------------------------------------------------------------
// NotFound — minimal 404 page for unmatched routes
// ---------------------------------------------------------------------------
function NotFound() {
  return (
    <div className="min-h-screen bg-canvas flex flex-col items-center justify-center px-4 text-center transition-colors duration-300">
      <div className="mb-6">
        <ThesysLogo variant="symbol" size={64} />
      </div>
      <h1 className="text-6xl font-extrabold tracking-tighter mb-3 text-ink">
        404
      </h1>
      <p className="text-lg font-semibold mb-2 text-ink">
        Page not found
      </p>
      <p className="text-sm mb-8 max-w-xs text-muted">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/"
        className="px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
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
  const navigate = useNavigate();

  useEffect(() => {
    if (!isInitializing && !isAuthenticated) {
      navigate('/sign-in?reason=session_expired', { replace: true });
    }
  }, [isInitializing, isAuthenticated, navigate]);

  if (isInitializing || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return <Outlet />;
}

export default function App() {
  return (
    <BrowserRouter>
      <TooltipProvider delayDuration={300}>
        <UploadModalProvider>
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
              <Route path="/title-similarity" element={<TitleSimilarityPage />} />
              <Route path="/trend-analysis" element={<TrendAnalysisPage />} />
              <Route path="/analytics" element={<AnalyticsDashboardPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>

            {/* Catch-all — redirect unknown paths to home */}
            <Route path="*" element={<NotFound />} />
          </Routes>

          {/* Global Upload Thesis overlay — triggered from any navbar button */}
          <UploadThesisModal />
        </UploadModalProvider>
      </TooltipProvider>
    </BrowserRouter>
  );
}
