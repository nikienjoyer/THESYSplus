import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';

// NOTE: StrictMode is intentionally omitted.
// React StrictMode double-invokes useEffect in development, which causes
// AuthContext.attemptSilentRefresh() to fire twice with the same HttpOnly
// refresh cookie. The backend's token-rotation reuse detection sees the
// second request as a replayed token, revokes the entire session family,
// and returns REFRESH_TOKEN_REUSE_DETECTED — which triggers a forced
// redirect to /sign-in on every page load.
// StrictMode is already a no-op in production builds, so this change only
// affects the development experience.
createRoot(document.getElementById('root')).render(
  <ThemeProvider>
    <AuthProvider>
      <App />
    </AuthProvider>
  </ThemeProvider>,
);
