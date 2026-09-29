/** Authenticated, one-page-at-a-time watermarked manuscript viewer. */

import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, TriangleAlert, X } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import ThesysLogo from '../components/brand/ThesysLogo';

function describePreviewError(err) {
  const status = err?.response?.status;
  const code = err?.response?.data?.error?.code;
  if (code === 'DOCUMENT_NOT_AVAILABLE') {
    return 'This thesis record exists, but its source document is not available in the repository. Please contact the repository administrator.';
  }
  if (status === 401 || status === 403) return 'You are not authorized to preview this document. Try signing in again.';
  if (status === 404) return 'Thesis or page not found.';
  return 'The document page could not be loaded. Please try again.';
}

export default function PdfPreviewPage() {
  const { id } = useParams();
  return <PreviewDocument key={id} id={id} />;
}

function PreviewDocument({ id }) {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const { isAuthenticated } = useAuth();
  const isDark = theme === 'dark';

  const [title, setTitle] = useState('Thesis Preview');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [imageUrl, setImageUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const [takingLonger, setTakingLonger] = useState(false);
  const [error, setError] = useState('');
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    if (!isAuthenticated || !id) return;
    let active = true;
    client.get(`/theses/${id}/`)
      .then((res) => { if (active) setTitle(res.data?.title || 'Thesis Preview'); })
      .catch(() => {});
    return () => { active = false; };
  }, [isAuthenticated, id]);

  useEffect(() => {
    if (!isAuthenticated || !id) return;
    const controller = new AbortController();
    let objectUrl = '';
    const slowTimer = window.setTimeout(() => setTakingLonger(true), 3000);

    client.get(`/theses/${id}/preview/pages/${page}/`, {
      responseType: 'blob', signal: controller.signal,
    }).then((res) => {
      if (controller.signal.aborted) return;
      const count = Number(res.headers['x-page-count']);
      if (Number.isInteger(count) && count > 0) setTotalPages(count);
      objectUrl = URL.createObjectURL(res.data);
      setImageUrl(objectUrl);
    }).catch((err) => {
      if (!controller.signal.aborted) setError(describePreviewError(err));
    }).finally(() => {
      if (!controller.signal.aborted) {
        setLoading(false);
        setTakingLonger(false);
      }
      window.clearTimeout(slowTimer);
    });

    return () => {
      controller.abort();
      window.clearTimeout(slowTimer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [isAuthenticated, id, page, retryKey]);

  const buttonStyle = `inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 sm:px-4 ${
    isDark ? 'border-white/15 text-gray-200 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'
  }`;

  const goToPage = (nextPage) => {
    setImageUrl('');
    setError('');
    setLoading(true);
    setTakingLonger(false);
    setPage(nextPage);
  };

  const retry = () => {
    setImageUrl('');
    setError('');
    setLoading(true);
    setTakingLonger(false);
    setRetryKey((key) => key + 1);
  };

  return (
    <div className={`flex h-dvh min-h-0 w-full flex-col bg-canvas`}>
      <header className={`flex flex-shrink-0 items-center justify-between gap-3 border-b px-4 py-2.5 sm:px-6 ${
        isDark ? 'border-white/10 bg-black/20' : 'border-gray-200 bg-white'
      }`}>
        <div className="flex min-w-0 items-center gap-3">
          <ThesysLogo variant="symbol" size={24} />
          <h1 className={`truncate text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{title}</h1>
        </div>
        <button type="button" onClick={() => navigate(`/repository/${id}`)} className={buttonStyle}>
          <X className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">Close Preview</span><span className="sm:hidden">Close</span>
        </button>
      </header>

      <main className="min-h-0 flex-1 overflow-auto px-2 py-4 sm:px-6" aria-live="polite">
        {error ? (
          <div className="flex min-h-full flex-col items-center justify-center gap-3 px-4 text-center">
            <TriangleAlert className="h-8 w-8 text-rose-500" aria-hidden="true" />
            <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{error}</p>
            <button type="button" onClick={retry} className={buttonStyle}>Try again</button>
          </div>
        ) : loading ? (
          <div className={`flex min-h-full flex-col items-center justify-center gap-3 text-center text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
            <Spinner size="lg" />
            <p>Preparing page {page}…</p>
            {takingLonger && <p className="max-w-xs text-xs opacity-75">This is taking longer than usual. The document is being prepared on the demo computer.</p>}
          </div>
        ) : imageUrl ? (
          <img src={imageUrl} alt={`Watermarked page ${page} of ${totalPages} from ${title}`} className="mx-auto block h-auto max-w-full bg-white shadow-sm" />
        ) : null}
      </main>

      <nav className={`flex flex-shrink-0 items-center justify-between gap-2 border-t px-3 py-2 sm:justify-center sm:gap-3 sm:px-6 ${
        isDark ? 'border-white/10 bg-black/20' : 'border-gray-200 bg-white'
      }`} aria-label="Preview pages">
        <button type="button" onClick={() => goToPage(page - 1)} disabled={loading || page <= 1} className={buttonStyle}>
          <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Previous
        </button>
        <span className={`whitespace-nowrap text-sm tabular-nums ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
          Page {page} of {totalPages || '…'}
        </span>
        <button type="button" onClick={() => goToPage(page + 1)} disabled={loading || !totalPages || page >= totalPages} className={buttonStyle}>
          Next <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </nav>
    </div>
  );
}
