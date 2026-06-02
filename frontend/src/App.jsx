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
import { BrowserRouter, Routes, Route, useNavigate, Outlet } from 'react-router-dom';
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
        </Routes>
      </TooltipProvider>
    </BrowserRouter>
  );
}
