/**
 * PdfPreviewPage — /theses/:id/preview
 *
 * Dedicated, full-screen watermarked PDF viewer. Opened in a new browser
 * tab from ThesisDetailPage's "Preview Document" button — deliberately
 * has no AppNavbar/PageShell chrome so the document gets the whole
 * viewport. Raw file download is never exposed here.
 */

import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { X, TriangleAlert } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import ThesysLogo from '../components/brand/ThesysLogo';

/**
 * Translate a failed preview fetch into a message that says what actually
 * went wrong. The backend distinguishes "no such thesis" from "the thesis
 * exists but its source document can't be served" (DOCUMENT_NOT_AVAILABLE),
 * and the viewer must not blur the two — a reader needs to know whether
 * they're looking at the wrong record or a repository gap.
 */
function describePreviewError(err) {
  const status = err?.response?.status;
  const code = err?.response?.data?.error?.code;

  if (code === 'DOCUMENT_NOT_AVAILABLE') {
    return 'This thesis record exists, but its source document is not available in the repository, so there is nothing to preview. Please contact the repository administrator.';
  }
  if (status === 404) return 'Thesis not found.';
  if (status === 401 || status === 403) {
    return 'You are not authorized to preview this document. Try signing in again.';
  }
  return 'The document preview could not be loaded. Please try again.';
}

export default function PdfPreviewPage() {
  const { id } = useParams();
  const { theme } = useTheme();
  const { isAuthenticated } = useAuth();
  const isDark = theme === 'dark';

  const [title, setTitle] = useState('');
  const [pdfUrl, setPdfUrl] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isAuthenticated || !id) return;
    let cancelled = false;
    client.get(`/theses/${id}/`)
      .then((res) => { if (!cancelled) setTitle(res.data?.title || 'Thesis Preview'); })
      .catch(() => { /* title is cosmetic — the PDF fetch below surfaces real errors */ });
    return () => { cancelled = true; };
  }, [isAuthenticated, id]);

  // Fetch the PDF bytes with the authenticated client — a plain <iframe src>
  // can't carry the Authorization header, so we load the blob and hand the
  // iframe an object URL instead.
  useEffect(() => {
    if (!isAuthenticated || !id) return;
    let cancelled = false;
    let objectUrl = '';
    setPdfUrl('');
    setError('');
    (async () => {
      try {
        const res = await client.get(`/theses/${id}/download/`, { responseType: 'blob' });
        if (cancelled) return;
        const blob = new Blob([res.data], { type: 'application/pdf' });
        objectUrl = window.URL.createObjectURL(blob);
        setPdfUrl(`${objectUrl}#toolbar=0&navpanes=0&statusbar=0`);
      } catch (err) {
        if (!cancelled) setError(describePreviewError(err));
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) window.URL.revokeObjectURL(objectUrl);
    };
  }, [isAuthenticated, id]);

  const handleClose = () => {
    // window.close() only works on tabs opened via window.open (which is
    // how this page is always reached); fall back silently otherwise.
    window.close();
  };

  return (
    <div className={`h-screen w-screen flex flex-col ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      {/* Clean header — no app navbar, this is a distraction-free viewer */}
      <header className={`flex items-center justify-between gap-4 px-4 sm:px-6 py-3 border-b flex-shrink-0 ${
        isDark ? 'border-white/10 bg-black/20' : 'border-gray-200 bg-white'
      }`}>
        <div className="flex items-center gap-3 min-w-0">
          <ThesysLogo variant="symbol" size={24} />
          <h1 className={`text-sm font-semibold truncate ${isDark ? 'text-white' : 'text-gray-900'}`}>
            {title || 'Loading…'}
          </h1>
        </div>
        <button
          type="button"
          onClick={handleClose}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-semibold border transition-colors flex-shrink-0 ${
            isDark
              ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]'
              : 'border-gray-200 text-gray-700 hover:bg-gray-50'
          }`}
        >
          <X className="w-4 h-4" aria-hidden="true" />
          Close Preview
        </button>
      </header>

      {/* PDF surface — fills remaining viewport. overflow-y-auto lets the
          container scroll if the embedded viewer ever reports a taller
          intrinsic size than the viewport. The watermark is now burned into
          the PDF bytes themselves (backend theses/services/watermark_pdf.py),
          so it scrolls with each page and marks only the paper — no DOM
          overlay layered on top of the iframe. */}
      <div className="relative flex-1 min-h-0 h-full w-full overflow-y-auto">
        {error ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 px-4 text-center">
            <TriangleAlert className="w-8 h-8 text-rose-500" aria-hidden="true" />
            <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{error}</p>
          </div>
        ) : pdfUrl ? (
          <iframe
            src={pdfUrl}
            title={`${title || 'Thesis'} — preview`}
            className="w-full h-full min-h-full border-0"
          />
        ) : (
          <div className="flex justify-center items-center h-full"><Spinner /></div>
        )}
      </div>
    </div>
  );
}
