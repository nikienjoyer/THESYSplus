/**
 * ThesisDetailPage — thesis detail view. The PDF opens in a dedicated,
 * watermarked full-screen preview in a new tab (PdfPreviewPage) rather
 * than inline here. Raw file download is intentionally not exposed.
 *
 * Saved theses are persisted in user-scoped localStorage:
 * "thesys.savedTheses.<userId>" or "thesys.savedTheses.<email>"
 *
 * TODO: For production, saved theses should be persisted in the backend per user.
 */

import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Bookmark, Eye, TriangleAlert } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import AppNavbar from '../components/layout/AppNavbar';
import PageShell from '../components/layout/PageShell';
import { getUserData, setUserData } from '../utils/userStorage';

function isSaved(id, user) {
  const arr = getUserData('savedTheses', user, []);
  return arr.some((t) => t.id === id);
}

function toggleSaved(thesis, user) {
  const arr = getUserData('savedTheses', user, []);
  const exists = arr.some((t) => t.id === thesis.id);
  const next = exists
    ? arr.filter((t) => t.id !== thesis.id)
    : [...arr, { ...thesis, savedAt: new Date().toISOString() }];
  setUserData('savedTheses', user, next);
  return !exists;
}

export default function ThesisDetailPage() {
  const { id } = useParams();
  const { theme } = useTheme();
  const { isAuthenticated, user } = useAuth();
  const isDark = theme === 'dark';

  const [thesis, setThesis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  // Re-read saved status once user is available (user may be null during auth init)
  useEffect(() => {
    if (user && id) setSaved(isSaved(id, user));
  }, [user, id]);

  useEffect(() => {
    if (!isAuthenticated || !id) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const res = await client.get(`/theses/${id}/`);
        if (!cancelled) setThesis(res.data);
      } catch (err) {
        if (!cancelled) {
          if (err?.response?.status === 404) {
            setError('Thesis not found.');
          } else {
            setError('Failed to load thesis.');
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [isAuthenticated, id]);

  const handlePreview = () => {
    window.open(`/theses/${id}/preview`, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      <AppNavbar activePage="repository" breadcrumb="Repository" />

      <PageShell>
        <div className="max-w-3xl">
        {loading ? (
          <div className="flex justify-center py-16"><Spinner /></div>
        ) : error ? (
          <div
            className={`rounded-xl p-8 text-center ${
              isDark ? 'bg-rose-500/10 text-rose-300' : 'bg-rose-50 text-rose-700'
            }`}
          >
            {error}
          </div>
        ) : thesis ? (
          <>
            {/* Back to Repository link */}
            <Link
              to="/repository"
              className={`inline-flex items-center gap-1.5 text-sm font-medium mb-4 transition-colors ${
                isDark ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7"/>
              </svg>
              Back to Repository
            </Link>

            {/* Embedding warning — visible to faculty/admin only when semantic search won't work */}
            {user?.role !== 'student' && thesis.status === 'approved' && thesis.embedding_status !== 'ready' && (
              <div className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 mb-4 text-xs ${
                isDark
                  ? 'bg-amber-500/10 border-amber-500/25 text-amber-300'
                  : 'bg-amber-50 border-amber-200 text-amber-700'
              }`}>
                <TriangleAlert className="w-4 h-4 flex-shrink-0 mt-0.5" aria-hidden="true" />
                <span>
                  <strong>Semantic search unavailable for this thesis.</strong>
                  {' '}Embedding status: <code className="font-mono">{thesis.embedding_status}</code>.
                  This thesis will not appear in semantic search results or title similarity comparisons.
                  To fix, re-upload the thesis or regenerate its embedding from Django Admin.
                </span>
              </div>
            )}

            <article
              className="thesys-card p-6 sm:p-8"
            >
            {/* Status + program tags */}
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <span
                className={`text-xs px-2 py-0.5 rounded-md ${
                  isDark ? 'bg-blue-500/10 text-blue-300 border border-blue-500/20' : 'bg-blue-50 text-blue-700 border border-blue-100'
                }`}
              >
                {thesis.program}
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-md ${
                  isDark ? 'bg-white/[0.05] text-gray-300 border border-white/10' : 'bg-gray-100 text-gray-700 border border-gray-200'
                }`}
              >
                {thesis.year}
              </span>
              <span
                className={`text-xs uppercase tracking-wider px-2 py-0.5 rounded-full font-semibold border ${
                  thesis.status === 'approved'
                    ? isDark
                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                      : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : thesis.status === 'rejected'
                    ? isDark
                      ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                      : 'bg-rose-50 text-rose-700 border-rose-200'
                    : isDark
                    ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                    : 'bg-amber-50 text-amber-700 border-amber-200'
                }`}
              >
                {thesis.status.replace('_', ' ')}
              </span>
            </div>

            <h1 className={`text-2xl sm:text-3xl font-bold leading-tight mb-4 ${isDark ? 'text-white' : 'text-gray-900'}`}>
              {thesis.title}
            </h1>

            <div className={`text-sm mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
              <strong>Authors:</strong> {thesis.authors.join(', ')}
            </div>
            {thesis.adviser && (
              <div className={`text-sm mb-4 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                <strong>Adviser:</strong> {thesis.adviser}
              </div>
            )}

            <hr className={`my-5 ${isDark ? 'border-white/10' : 'border-gray-200'}`} />

            <h2 className={`text-sm font-semibold uppercase tracking-wider mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              Abstract
            </h2>
            {/* Reading column: 65ch measure for comfortable scholarly reading.
                font-reading = Source Serif 4 Variable (Phase 2.C-2).
                text-[1.0625rem] = 17px — within the 16-18px approved reading range. */}
            <div className="max-w-[65ch] mb-6">
              <p
                className={`font-reading text-[1.0625rem] leading-[1.65] whitespace-pre-line ${isDark ? 'text-gray-200' : 'text-gray-800'}`}
                style={{ textWrap: 'pretty' }}
              >
                {thesis.abstract}
              </p>
            </div>

            <h2 className={`text-sm font-semibold uppercase tracking-wider mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              Keywords
            </h2>
            <div className="flex flex-wrap gap-1.5 mb-6">
              {thesis.keywords && thesis.keywords.length > 0 ? (
                <>
                  {thesis.keywords.slice(0, 8).map((kw) => (
                    <span
                      key={kw}
                      className={`text-xs px-2 py-1 rounded-md ${
                        isDark
                          ? 'bg-blue-500/10 text-blue-300 border border-blue-500/20'
                          : 'bg-blue-50 text-blue-700 border border-blue-100'
                      }`}
                    >
                      {kw}
                    </span>
                  ))}
                  {thesis.keywords.length > 8 && (
                    <span
                      className={`text-xs px-2 py-1 rounded-md ${
                        isDark
                          ? 'bg-white/[0.05] text-gray-400 border border-white/10'
                          : 'bg-gray-50 text-gray-600 border border-gray-200'
                      }`}
                    >
                      +{thesis.keywords.length - 8} more
                    </span>
                  )}
                </>
              ) : (
                <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  No keywords available
                </span>
              )}
            </div>

            <hr className={`my-5 ${isDark ? 'border-white/10' : 'border-gray-200'}`} />

            <div className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              <div>
                Uploaded by <strong className={isDark ? 'text-gray-300' : 'text-gray-700'}>{thesis.uploaded_by_name}</strong>
                {' · '}
                {new Date(thesis.created_at).toLocaleDateString()}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSaved(toggleSaved(thesis, user))}
                  className={`px-3 py-2 rounded-lg text-sm font-semibold border transition-colors flex items-center gap-1.5 ${
                    saved
                      ? isDark
                        ? 'bg-blue-500/20 border-blue-500/40 text-blue-300'
                        : 'bg-blue-50 border-blue-200 text-blue-700'
                      : isDark
                      ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]'
                      : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                  title={saved ? 'Remove from saved theses' : 'Save to your profile'}
                >
                  <Bookmark className={`w-4 h-4 ${saved ? 'fill-current' : ''}`} aria-hidden="true" />
                  {saved ? 'Saved' : 'Save'}
                </button>
                <button
                  type="button"
                  onClick={handlePreview}
                  className={`px-3 py-2 rounded-lg text-sm font-semibold border transition-colors flex items-center gap-1.5 ${
                    isDark
                      ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]'
                      : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                  title="Open watermarked preview in a new tab"
                >
                  <Eye className="w-4 h-4" aria-hidden="true" />
                  Preview Document
                </button>
              </div>
            </div>
          </article>
          </>
        ) : null}
        </div>
      </PageShell>
    </div>
  );
}
