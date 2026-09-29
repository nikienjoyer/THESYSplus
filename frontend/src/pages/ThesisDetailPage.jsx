/**
 * ThesisDetailPage — thesis detail view. The document opens in a dedicated,
 * watermarked full-screen preview in this tab (PdfPreviewPage) rather
 * than inline here. A Download button is also offered, but it never
 * exposes the raw file: both paths go through GET /theses/:id/download/,
 * which serves the document with an institutional watermark burned into
 * the bytes — "Preview Only" inline, "Property of…" as an attachment.
 *
 * Saved theses are persisted in user-scoped localStorage:
 * "thesys.savedTheses.<userId>" or "thesys.savedTheses.<email>"
 *
 * TODO: For production, saved theses should be persisted in the backend per user.
 */

import { useEffect, useState } from 'react';
import { Link, useParams, useNavigate, useLocation } from 'react-router-dom';
import { Bookmark, Download, Eye, TriangleAlert } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import { useToast } from '../hooks/useToast';
import Spinner from '../components/ui/Spinner';
import AppNavbar from '../components/layout/AppNavbar';
import PageShell from '../components/layout/PageShell';
import { getUserData, setUserData } from '../utils/userStorage';
import { collapseWhitespace, formatFullAuthorList } from '../utils/formatters';

/**
 * Same distinction PdfPreviewPage's describePreviewError draws, reused here
 * for the download path so a "document unavailable" thesis gets identical
 * wording no matter which button the user pressed.
 */
function describeDownloadError(err) {
  const code = err?.response?.data?.error?.code;
  if (code === 'DOCUMENT_NOT_AVAILABLE') {
    return 'This thesis record exists, but its source document is not available in the repository, so there is nothing to download. Please contact the repository administrator.';
  }
  return 'The document could not be downloaded. Please try again.';
}

/** Best-effort filename from Content-Disposition; falls back to a safe default. */
function filenameFromDisposition(disposition, fallback) {
  if (!disposition) return fallback;
  const match = /filename="([^"]+)"/.exec(disposition);
  return match ? match[1] : fallback;
}

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
  const navigate = useNavigate();
  const location = useLocation();
  const isDark = theme === 'dark';

  const { toast } = useToast();

  const [thesis, setThesis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState('');
  // Suggestions are kept with the thesis they belong to, so moving to another
  // thesis never shows the previous thesis's chips while its request runs.
  const [suggestionState, setSuggestionState] = useState({ thesisId: null, items: [] });
  const suggestions = suggestionState.thesisId === id ? suggestionState.items : [];
  const [savingSubject, setSavingSubject] = useState(false);
  const [subjectError, setSubjectError] = useState('');
  const canReviewSubject = user?.role === 'faculty' || user?.role === 'administrator';

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
        if (!cancelled) {
          setThesis(res.data);
          setSelectedSubject(res.data.primary_subject?.code || '');
        }
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

  useEffect(() => {
    if (!isAuthenticated || !canReviewSubject) return;
    let cancelled = false;
    client.get('/theses/subjects/')
      .then((res) => { if (!cancelled) setSubjects(res.data); })
      .catch(() => { if (!cancelled) setSubjectError('Subject choices could not be loaded. Reload this page to try again.'); });
    return () => { cancelled = true; };
  }, [isAuthenticated, canReviewSubject]);

  // Top-2 suggestions for a thesis awaiting subject review. They only
  // pre-select the dropdown; the reviewer still confirms.
  const awaitingSubjectReview = thesis?.status === 'approved' && !thesis?.primary_subject;
  useEffect(() => {
    if (!isAuthenticated || !canReviewSubject || !awaitingSubjectReview) return;
    let cancelled = false;
    client.get(`/theses/${id}/subject-suggestions/`)
      .then((res) => { if (!cancelled) setSuggestionState({ thesisId: id, items: res.data?.suggestions || [] }); })
      .catch(() => { if (!cancelled) setSuggestionState({ thesisId: id, items: [] }); });
    return () => { cancelled = true; };
  }, [isAuthenticated, canReviewSubject, awaitingSubjectReview, id]);

  const saveSubject = async () => {
    if (!selectedSubject || savingSubject) return;
    setSavingSubject(true);
    setSubjectError('');
    try {
      const res = await client.put(`/theses/${id}/subject/`, { subject_code: selectedSubject });
      setThesis(res.data);
      toast.success('Research subject confirmed.');
    } catch {
      setSubjectError('The research subject could not be saved. Please try again.');
    } finally {
      setSavingSubject(false);
    }
  };

  const handlePreview = () => {
    navigate(`/theses/${id}/preview`);
  };

  /**
   * Fetch the watermarked download bytes and save them via a temporary
   * object URL. Cannot be a plain <a href>: the endpoint requires the JWT
   * Authorization header the axios client attaches, so a bare link would
   * 401. `disposition=attachment` asks the backend for the download
   * watermark ("Property of…") and the non-"_Preview" filename — the same
   * stamper PdfPreviewPage's inline fetch uses, different query param.
   */
  const handleDownload = async () => {
    if (downloading) return;
    setDownloading(true);
    setDownloadProgress(null);
    let objectUrl = '';
    try {
      const res = await client.get(`/theses/${id}/download/?disposition=attachment`, {
        responseType: 'blob',
        onDownloadProgress: (event) => {
          if (event.total) setDownloadProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
        },
      });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      objectUrl = window.URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = filenameFromDisposition(
        res.headers['content-disposition'],
        `${thesis?.title || 'thesis'}.pdf`,
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      toast.error(describeDownloadError(err));
    } finally {
      if (objectUrl) window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 60_000);
      setDownloading(false);
      setDownloadProgress(null);
    }
  };

  // "Go back" has no single stable destination — this page is reachable
  // from Repository, Title Similarity match cards, Profile uploads, and
  // cluster drill-down lists, so a hardcoded destination link is wrong
  // from most entry points. `navigate(-1)` returns to whichever of those
  // the visitor actually came from (e.g. /trend-analysis?cluster=N with
  // that cluster view still resolved, since the state lives in the URL).
  //
  // Guard against having no in-app history: React Router gives the very
  // first history entry of a session `key === 'default'` — that's a
  // direct link, bookmark, or fresh tab with nothing to go back to.
  // Without this guard, navigate(-1) there would exit the app entirely
  // (or land on about:blank / do nothing), so we fall back to a known
  // destination instead.
  const handleBack = () => {
    if (location.key !== 'default') {
      navigate(-1);
    } else {
      navigate('/repository');
    }
  };

  return (
    <div className={`min-h-screen bg-canvas`}>
      <AppNavbar activePage="repository" />

      <PageShell>
        <div className="max-w-4xl mx-auto px-4">
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
              {/* Back — an action with no stable destination, so a button
                  (not a Link with a fixed href) is the correct element.
                  See handleBack for the history-aware navigation logic. */}
              <button
                type="button"
                onClick={handleBack}
                className={`flex w-fit items-center gap-1.5 mb-4 text-left text-sm font-medium transition-colors ${
                  isDark ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7"/>
                </svg>
                Back
              </button>

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
              <strong>Authors:</strong> {formatFullAuthorList(thesis.authors)}
            </div>
            {thesis.adviser && (
              <div className={`text-sm mb-4 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                <strong>Adviser:</strong> {thesis.adviser}
              </div>
            )}

            <hr className={`my-5 ${isDark ? 'border-white/10' : 'border-gray-200'}`} />

            {/* Align the abstract with Authors and Keywords and use the card width.
                font-reading = Source Serif 4 Variable (Phase 2.C-2).
                text-[1.0625rem] = 17px — within the 16-18px approved reading range. */}
            <div className="w-full mb-6">
              <h2 className={`text-sm font-semibold uppercase tracking-wider mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                Abstract
              </h2>
              <p
                className={`font-reading text-left text-[1.0625rem] leading-[1.65] whitespace-pre-line ${isDark ? 'text-gray-200' : 'text-gray-800'}`}
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
                  {thesis.keywords.slice(0, 8).map((kw) => {
                    // Display-only whitespace trim so a stored tag such as
                    // "Solar -Powered Water Pump" reads cleanly. The RAW value
                    // is what travels in the URL — the server matches
                    // whitespace-blind, and rewriting stored spellings is a
                    // separate data-quality decision.
                    const label = collapseWhitespace(kw) || kw;
                    return (
                      <button
                        key={kw}
                        type="button"
                        onClick={() => navigate(
                          `/repository?keyword=${encodeURIComponent(kw)}`,
                        )}
                        aria-label={`View all theses tagged ${label}`}
                        title={label}
                        className={`text-xs px-2 py-1 rounded-md cursor-pointer transition-colors
                          hover:underline focus-visible:underline
                          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                          isDark
                            ? 'bg-blue-500/10 text-blue-300 border border-blue-500/20 hover:bg-blue-500/20'
                            : 'bg-blue-50 text-blue-700 border border-blue-100 hover:bg-blue-100'
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
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

            {thesis.status === 'approved' && (
              <section className="mb-6" aria-labelledby="research-subject-heading">
                <h2 id="research-subject-heading" className={`text-sm font-semibold uppercase tracking-wider mb-2 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                  Research subject
                </h2>
                <p className={`text-sm ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                  {thesis.primary_subject ? (
                    <Link
                      to={`/trend-analysis?subject=${encodeURIComponent(thesis.primary_subject.code)}`}
                      state={{ fromThesisDetail: true, thesisId: id }}
                      aria-label={`View theses in ${thesis.primary_subject.name}`}
                      className={`inline-flex items-center text-xs px-2 py-1 rounded-md transition-colors
                        hover:underline focus-visible:underline
                        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                        isDark
                          ? 'bg-blue-500/10 text-blue-300 border border-blue-500/20 hover:bg-blue-500/20'
                          : 'bg-blue-50 text-blue-700 border border-blue-100 hover:bg-blue-100'
                      }`}
                    >
                      {thesis.primary_subject.name}
                    </Link>
                  ) : 'Awaiting subject review'}
                </p>
                {canReviewSubject && (
                  <div className="mt-3 max-w-xl">
                    <label htmlFor="primary-subject" className={`block text-xs font-medium mb-1.5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                      Confirm or change primary subject
                    </label>
                    <div className="flex flex-col sm:flex-row gap-2">
                      <select id="primary-subject" value={selectedSubject} onChange={(event) => setSelectedSubject(event.target.value)}
                        style={{ colorScheme: isDark ? 'dark' : 'light' }}
                        className={`min-w-0 flex-1 rounded-lg border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${isDark ? 'bg-[#111a37] border-white/15 text-gray-100' : 'bg-white border-gray-300 text-gray-800'}`}>
                        <option value="">Choose a subject</option>
                        {subjects.map((subject) => <option key={subject.code} value={subject.code}>{subject.name}</option>)}
                      </select>
                      <button type="button" onClick={saveSubject}
                        disabled={!selectedSubject || savingSubject || selectedSubject === thesis.primary_subject?.code}
                        className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                        {savingSubject ? 'Saving…' : thesis.primary_subject ? 'Save change' : 'Confirm subject'}
                      </button>
                    </div>
                    {awaitingSubjectReview && suggestions.length > 0 && (
                      <div className="mt-2">
                        <p className={`text-xs mb-1.5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                          Suggested from similar reviewed theses. Check the thesis before confirming.
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {suggestions.map((s) => (
                            <button
                              key={s.code}
                              type="button"
                              onClick={() => setSelectedSubject(s.code)}
                              aria-pressed={selectedSubject === s.code}
                              className={`rounded-full border px-3 py-1 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                                selectedSubject === s.code
                                  ? 'bg-blue-600 border-blue-600 text-white'
                                  : isDark
                                    ? 'border-white/15 text-gray-200 hover:bg-white/[0.06]'
                                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                              }`}
                            >
                              {s.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    {thesis.subject_reviewed_at && (
                      <p className={`mt-2 text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        Reviewed by {thesis.subject_reviewed_by_name || 'a former staff member'} on {new Date(thesis.subject_reviewed_at).toLocaleDateString()}.
                      </p>
                    )}
                    {subjectError && <p role="alert" className="mt-2 text-xs text-rose-600 dark:text-rose-300">{subjectError}</p>}
                  </div>
                )}
              </section>
            )}

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
                  title="Open watermarked preview"
                >
                  <Eye className="w-4 h-4" aria-hidden="true" />
                  Preview Document
                </button>
                <button
                  type="button"
                  onClick={handleDownload}
                  disabled={downloading}
                  className={`px-3 py-2 rounded-lg text-sm font-semibold border transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed ${
                    isDark
                      ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]'
                      : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                  }`}
                  title="Download the watermarked document"
                >
                  {downloading ? <Spinner className="w-4 h-4" /> : <Download className="w-4 h-4" aria-hidden="true" />}
                  {downloading ? `Downloading${downloadProgress === null ? '…' : ` ${downloadProgress}%`}` : 'Download'}
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
