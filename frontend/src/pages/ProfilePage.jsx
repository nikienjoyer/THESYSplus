/**
 * ProfilePage — /profile
 *
 * Layout:
 *   LEFT SIDEBAR:  avatar · name · role · email · bio · quick stats
 *   MAIN (tabbed): Overview | Saved Theses
 *
 * Saved Theses are persisted in user-scoped localStorage:
 * "thesys.savedTheses.<userId>" or "thesys.savedTheses.<email>"
 * (array of thesis objects cached on save). Each entry stores id, title,
 * authors, year, program, keywords, and the timestamp saved.
 *
 * ?section=saved — deep-link directly to the Saved Theses tab.
 *
 * TODO: For production, saved theses should be persisted in the backend per user.
 */

import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Bookmark, UploadCloud } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import AppNavbar from '../components/layout/AppNavbar';
import PageShell from '../components/layout/PageShell';
import { useProfilePicture } from '../hooks/useProfilePicture';
import { useUploadModal } from '../hooks/useUploadModal';
import { Avatar, AvatarImage, AvatarFallback } from '../components/shadcn/avatar';
import { Badge } from '../components/shadcn/badge';
import { getUserData, setUserData } from '../utils/userStorage';

// Same status → color mapping as RepositoryPage's ThesisCard, so a thesis's
// status badge looks identical whether you're looking at it from the
// repository or from your own profile.
function statusVariantClass(status, isDark) {
  const map = {
    approved: isDark
      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/15'
      : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-50',
    pending_review: isDark
      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/15'
      : 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-50',
    rejected: isDark
      ? 'bg-rose-500/15 text-rose-300 border-rose-500/30 hover:bg-rose-500/15'
      : 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-50',
  };
  return map[status] || map.pending_review;
}

function loadSaved(user) {
  return getUserData('savedTheses', user, []);
}

function removeSaved(id, user) {
  const current = loadSaved(user);
  const next = current.filter((t) => t.id !== id);
  setUserData('savedTheses', user, next);
  return next;
}

function initials(user) {
  if (!user) return '?';
  const f = (user.first_name || '').charAt(0).toUpperCase();
  const l = (user.last_name || '').charAt(0).toUpperCase();
  return f + l || '?';
}

function roleLabel(role) {
  if (!role) return '';
  return role.charAt(0).toUpperCase() + role.slice(1);
}


// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
function Sidebar({ user, stats, isDark }) {
  const { dataUrl: avatarUrl } = useProfilePicture();
  return (
    <aside className="flex flex-col items-center text-center lg:border-r lg:border-[var(--color-border-subtle)] lg:pr-6">
      {/* Avatar — shadcn Avatar with image + initial fallback */}
      <Avatar className="w-20 h-20 mb-4 ring-2 ring-blue-500/30">
        {avatarUrl && <AvatarImage src={avatarUrl} alt="Profile" />}
        <AvatarFallback
          className={`text-2xl font-bold ${
            isDark ? 'bg-blue-600/25 text-blue-200' : 'bg-blue-100 text-blue-700'
          }`}
        >
          {initials(user)}
        </AvatarFallback>
      </Avatar>

      <h2 className={`text-lg font-bold mb-0.5 ${isDark ? 'text-white' : 'text-gray-900'}`}>
        {user ? `${user.first_name} ${user.last_name}`.trim() : '—'}
      </h2>
      <span
        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border mb-3 ${
          isDark ? 'bg-blue-500/15 text-blue-300 border-blue-500/30' : 'bg-blue-50 text-blue-700 border-blue-200'
        }`}
      >
        {roleLabel(user?.role)}
      </span>

      <p className={`text-xs mb-4 break-all ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
        {user?.email}
      </p>

      {/* Bio */}
      <p className={`text-sm text-center mb-5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
        {stats.bio || (
          <span className={isDark ? 'text-gray-600 italic' : 'text-gray-400 italic'}>
            No bio yet.
          </span>
        )}
      </p>

      <Link
        to="/settings"
        className={`w-full py-2 rounded-lg text-sm font-medium border transition-colors ${
          isDark
            ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]'
            : 'border-gray-200 text-gray-700 hover:bg-gray-50'
        }`}
      >
        Edit Profile
      </Link>

      {/* Quick stats */}
      <div
        className={`mt-5 w-full grid grid-cols-2 divide-x ${
          isDark ? 'divide-white/[0.08]' : 'divide-gray-200'
        }`}
      >
        {[
          { label: 'Saved', value: stats.saved },
          { label: 'Uploaded', value: stats.uploaded },
        ].map((s) => (
          <div
            key={s.label}
            className="flex flex-col items-center py-3"
          >
            <span className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
              {/* undefined = failed request or not loaded yet; a real zero
                  count is a number (0), so `?? 0` here would otherwise make
                  a failed fetch look identical to "confirmed zero uploads." */}
              {typeof s.value === 'number' ? s.value : '—'}
            </span>
            <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
              {s.label}
            </span>
          </div>
        ))}
      </div>
    </aside>
  );
}


// ---------------------------------------------------------------------------
// Saved thesis card
// ---------------------------------------------------------------------------
function SavedCard({ entry, isDark, onRemove }) {
  const savedDate = entry.savedAt
    ? new Date(entry.savedAt).toLocaleDateString()
    : '';
  return (
    <div
      className={`rounded-xl border p-4 ${
        isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-gray-200'
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <Link
          to={`/repository/${entry.id}`}
          className={`font-semibold text-sm leading-snug line-clamp-2 hover:underline ${
            isDark ? 'text-white' : 'text-gray-900'
          }`}
        >
          {entry.title}
        </Link>
        <button
          type="button"
          onClick={() => onRemove(entry.id)}
          aria-label={`Remove "${entry.title}" from saved`}
          className={`flex-shrink-0 mt-0.5 text-lg leading-none transition-colors ${
            isDark ? 'text-gray-600 hover:text-rose-400' : 'text-gray-400 hover:text-rose-500'
          }`}
          title="Remove from saved"
        >
          ×
        </button>
      </div>

      <div className={`text-xs mb-2 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
        {entry.program} · {entry.year}
        {entry.authors?.length > 0 && (
          <> · {entry.authors.slice(0, 2).join(', ')}{entry.authors.length > 2 ? ' …' : ''}</>
        )}
      </div>

      {entry.keywords?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {entry.keywords.slice(0, 4).map((kw) => (
            <span
              key={kw}
              className={`text-xs px-2 py-0.5 rounded-md ${
                isDark ? 'bg-blue-500/10 text-blue-300 border border-blue-500/20' : 'bg-blue-50 text-blue-700 border border-blue-100'
              }`}
            >
              {kw}
            </span>
          ))}
          {entry.keywords.length > 4 && (
            <span
              className={`text-xs px-2 py-0.5 rounded-md ${
                isDark ? 'bg-white/[0.05] text-gray-400 border border-white/10' : 'bg-gray-50 text-gray-600 border border-gray-200'
              }`}
            >
              +{entry.keywords.length - 4} more
            </span>
          )}
        </div>
      )}

      {savedDate && (
        <p className={`text-xs mt-2 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          Saved {savedDate}
        </p>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function ProfilePage() {
  const { theme } = useTheme();
  const { isAuthenticated, user } = useAuth();
  const { open: openUpload } = useUploadModal();
  const [searchParams] = useSearchParams();
  const isDark = theme === 'dark';

  const initialSection = searchParams.get('section') === 'saved' ? 'saved' : 'overview';
  const [activeTab, setActiveTab] = useState(initialSection);
  const [savedTheses, setSavedTheses] = useState(() => loadSaved(user));
  // myUploads: the 5 most recent theses uploaded by this user (for the list).
  // myUploadsCount: the TOTAL count of this user's uploads (for the stat) —
  // comes from the paginated response's `count`, never from
  // `myUploads.length`, since that's always <= page_size and was the root
  // cause of the count being permanently capped at 5.
  // myUploadsCount starts `null`, not 0 — a real "zero uploads" and "haven't
  // loaded / failed to load yet" must render differently, so a failed
  // request can't masquerade as a confident zero.
  const [myUploads, setMyUploads] = useState([]);
  const [myUploadsCount, setMyUploadsCount] = useState(null);
  const [uploadsLoading, setUploadsLoading] = useState(false);
  const [uploadsError, setUploadsError] = useState(false);
  const [uploadsRetryKey, setUploadsRetryKey] = useState(0);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  // Read profile extra fields from user-scoped localStorage (set by Settings page)
  const profileExtra = useMemo(() => getUserData('profile', user, {}), [user]);

  // Update active tab if ?section changes via dropdown navigation
  useEffect(() => {
    const sec = searchParams.get('section');
    if (sec === 'saved') setActiveTab('saved');
  }, [searchParams]);

  // Load this user's own uploads — one request drives both the "Uploaded"
  // stat and the recent-uploads list below it. `mine=true` scopes the
  // query server-side to the requesting user (layered on top of the
  // role-based visible queryset, so a student's own pending/rejected
  // uploads still show up). `count` is the filtered total across all
  // pages — not `results.length`, which is capped at page_size and was
  // the original bug (every account read the same repo-wide min(5, total)).
  useEffect(() => {
    if (!isAuthenticated || activeTab !== 'overview') return;
    let cancelled = false;
    (async () => {
      setUploadsLoading(true);
      setUploadsError(false);
      try {
        const res = await client.get('/theses/?mine=true&page_size=5');
        if (!cancelled) {
          setMyUploads(res.data.results || []);
          setMyUploadsCount(res.data.count ?? 0);
        }
      } catch {
        // A failed request must not render a confident 0 — leave
        // myUploadsCount at its current value (null on first load) and
        // flag the error so the UI can show a dash/retry instead of
        // silently implying "you have no uploads."
        if (!cancelled) setUploadsError(true);
      } finally {
        if (!cancelled) setUploadsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [isAuthenticated, activeTab, uploadsRetryKey]);

  const handleRemoveSaved = (id) => {
    const next = removeSaved(id, user);
    setSavedTheses(next);
  };

  const handleClearAll = () => {
    setUserData('savedTheses', user, []);
    setSavedTheses([]);
    setShowClearConfirm(false);
  };

  const stats = {
    saved: savedTheses.length,
    // null/undefined here (still loading, or the request failed) is
    // intentionally distinct from 0 (confirmed zero uploads) — see the
    // Sidebar stat tile below, which renders a dash instead of "0" for
    // the former.
    uploaded: uploadsError ? undefined : myUploadsCount,
    bio: profileExtra.bio || '',
  };

  const tabCls = (key) =>
    `pb-2 text-sm font-medium border-b-2 transition-colors focus-visible:outline-none ${
      activeTab === key
        ? isDark
          ? 'border-blue-400 text-white'
          : 'border-blue-600 text-blue-700'
        : isDark
        ? 'border-transparent text-gray-400 hover:text-gray-200'
        : 'border-transparent text-gray-500 hover:text-gray-800'
    }`;

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      <AppNavbar activePage="profile" />

      <PageShell>
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
          {/* Sidebar */}
          <Sidebar user={user} stats={stats} isDark={isDark} />

          {/* Main content */}
          <div>
            {/* Tabs */}
            <div className={`flex gap-6 mb-6 border-b ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
              <button type="button" className={tabCls('overview')} onClick={() => setActiveTab('overview')}>
                Profile Overview
              </button>
              <button type="button" className={tabCls('saved')} onClick={() => setActiveTab('saved')}>
                Saved Theses
                {savedTheses.length > 0 && (
                  <span
                    className={`ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${
                      isDark ? 'bg-blue-500/20 text-blue-300' : 'bg-blue-100 text-blue-700'
                    }`}
                  >
                    {savedTheses.length}
                  </span>
                )}
              </button>
            </div>

            {/* ── Overview tab ──────────────────────────────────── */}
            {activeTab === 'overview' && (
              <div className="space-y-10">
                {/* Account information — open section */}
                <section>
                  <h3 className={`text-sm font-semibold pb-2 mb-4 border-b border-[var(--color-border-subtle)] ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                    Account Information
                  </h3>
                  <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
                    {[
                      { label: 'Full Name', value: `${user?.first_name || ''} ${user?.last_name || ''}`.trim() },
                      { label: 'Email', value: user?.email },
                      { label: 'Role', value: roleLabel(user?.role) },
                      { label: 'Department', value: profileExtra.department || 'College of Computing Studies' },
                      { label: 'Research Interests', value: profileExtra.interests || '—' },
                      { label: 'Bio', value: profileExtra.bio || '—' },
                    ].map(({ label, value }) => (
                      <div key={label}>
                        <dt className={`text-xs uppercase tracking-wider font-semibold mb-0.5 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                          {label}
                        </dt>
                        <dd className={`text-sm ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                          {value || '—'}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </section>

                {/* Your recent uploads — open section */}
                <section>
                  <h3 className={`text-sm font-semibold pb-2 mb-4 border-b border-[var(--color-border-subtle)] ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                    Your Recent Uploads
                  </h3>
                  {uploadsLoading ? (
                    <div className="flex justify-center py-4"><Spinner /></div>
                  ) : uploadsError ? (
                    <div className={`rounded-lg p-3 text-sm flex items-center justify-between gap-3 ${
                      isDark ? 'bg-rose-500/10 text-rose-300 border border-rose-500/30' : 'bg-rose-50 text-rose-700 border border-rose-200'
                    }`}>
                      <span>Couldn&apos;t load your uploads. Please try again.</span>
                      <button
                        type="button"
                        onClick={() => setUploadsRetryKey((k) => k + 1)}
                        className="font-semibold underline flex-shrink-0"
                      >
                        Retry
                      </button>
                    </div>
                  ) : myUploads.length === 0 ? (
                    <div className={`rounded-lg border border-dashed p-6 flex flex-col items-center text-center gap-2 ${
                      isDark ? 'border-white/15 bg-white/[0.02]' : 'border-gray-300 bg-gray-50/50'
                    }`}>
                      <UploadCloud className={`w-7 h-7 ${isDark ? 'text-gray-600' : 'text-gray-300'}`} aria-hidden="true" />
                      <p className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                        You haven&apos;t uploaded any theses yet.
                      </p>
                      <button
                        type="button"
                        onClick={openUpload}
                        className="mt-1 px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors"
                      >
                        Upload Your First Thesis
                      </button>
                    </div>
                  ) : (
                    <ul className="space-y-2">
                      {myUploads.map((t) => (
                        <li key={t.id} className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <Link
                              to={`/repository/${t.id}`}
                              className="text-sm hover:underline line-clamp-1 text-primary"
                            >
                              {t.title}
                            </Link>
                            <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                              {' '}· {t.program} · {t.year}
                            </span>
                          </div>
                          <Badge
                            variant="outline"
                            className={`text-xs px-2 py-0.5 h-auto uppercase tracking-wide flex-shrink-0 ${statusVariantClass(t.status, isDark)}`}
                          >
                            {t.status.replace('_', ' ')}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>
            )}

            {/* ── Saved theses tab ──────────────────────────────── */}
            {activeTab === 'saved' && (
              <div>
                {savedTheses.length === 0 ? (
                  <div className="thesys-empty">
                    <Bookmark className="w-10 h-10 text-primary" aria-hidden="true" />
                    <p className={`font-semibold ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                      No saved theses yet.
                    </p>
                    <p className={`text-sm max-w-sm ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                      Save papers from the Repository to quickly access them later.
                    </p>
                    <Link
                      to="/repository"
                      className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-[var(--color-primary-hover)] transition-colors"
                    >
                      Browse Repository
                    </Link>
                  </div>
                ) : (
                  <>
                    {/* Clear All button */}
                    <div className="flex justify-end mb-4">
                      <button
                        type="button"
                        onClick={() => setShowClearConfirm(true)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                          isDark
                            ? 'border-rose-500/30 text-rose-400 hover:bg-rose-500/10'
                            : 'border-rose-200 text-rose-600 hover:bg-rose-50'
                        }`}
                      >
                        Clear All Saved Theses
                      </button>
                    </div>

                    {/* Confirmation modal */}
                    {showClearConfirm && (
                      <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
                        <div className={`rounded-xl border p-6 max-w-sm w-full ${
                          isDark ? 'bg-gray-900 border-white/10' : 'bg-white border-gray-200'
                        }`}>
                          <h3 className={`text-lg font-bold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                            Clear all saved theses?
                          </h3>
                          <p className={`text-sm mb-5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                            This will remove all theses from your saved list.
                          </p>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={handleClearAll}
                              className="flex-1 px-4 py-2 rounded-lg bg-rose-600 text-white text-sm font-semibold hover:bg-rose-700 transition-colors"
                            >
                              Clear All
                            </button>
                            <button
                              type="button"
                              onClick={() => setShowClearConfirm(false)}
                              className={`flex-1 px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                                isDark
                                  ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]'
                                  : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                              }`}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {savedTheses.map((entry) => (
                        <SavedCard
                          key={entry.id}
                          entry={entry}
                          isDark={isDark}
                          onRemove={handleRemoveSaved}
                        />
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </PageShell>
    </div>
  );
}
