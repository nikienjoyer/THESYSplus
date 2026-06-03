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
import { Bookmark } from 'lucide-react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import Spinner from '../components/ui/Spinner';
import AppNavbar from '../components/layout/AppNavbar';
import { useProfilePicture } from '../hooks/useProfilePicture';
import { Avatar, AvatarImage, AvatarFallback } from '../components/shadcn/avatar';
import { getUserData, setUserData } from '../utils/userStorage';

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
    <aside
      className={`rounded-2xl border p-6 flex flex-col items-center text-center ${
        isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-gray-200'
      }`}
    >
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
        className={`mt-5 w-full grid grid-cols-2 divide-x rounded-xl overflow-hidden border ${
          isDark ? 'border-white/[0.08] divide-white/[0.08]' : 'border-gray-200 divide-gray-200'
        }`}
      >
        {[
          { label: 'Saved', value: stats.saved },
          { label: 'Uploaded', value: stats.uploaded },
        ].map((s) => (
          <div
            key={s.label}
            className={`flex flex-col items-center py-3 ${
              isDark ? 'bg-white/[0.02]' : 'bg-gray-50'
            }`}
          >
            <span className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
              {s.value ?? 0}
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
  const [searchParams] = useSearchParams();
  const isDark = theme === 'dark';

  const initialSection = searchParams.get('section') === 'saved' ? 'saved' : 'overview';
  const [activeTab, setActiveTab] = useState(initialSection);
  const [savedTheses, setSavedTheses] = useState(() => loadSaved(user));
  const [uploadedTheses, setUploadedTheses] = useState([]);
  const [uploadsLoading, setUploadsLoading] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  // Read profile extra fields from user-scoped localStorage (set by Settings page)
  const profileExtra = useMemo(() => getUserData('profile', user, {}), [user]);

  // Update active tab if ?section changes via dropdown navigation
  useEffect(() => {
    const sec = searchParams.get('section');
    if (sec === 'saved') setActiveTab('saved');
  }, [searchParams]);

  // Load user's uploaded theses
  useEffect(() => {
    if (!isAuthenticated || activeTab !== 'overview') return;
    let cancelled = false;
    (async () => {
      setUploadsLoading(true);
      try {
        const res = await client.get('/theses/?page_size=5');
        if (!cancelled) setUploadedTheses(res.data.results || []);
      } catch {
        // silent
      } finally {
        if (!cancelled) setUploadsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [isAuthenticated, activeTab]);

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
    uploaded: uploadedTheses.length,
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
      <AppNavbar activePage="profile" breadcrumb="Profile" />

      <main className="max-w-6xl mx-auto px-5 sm:px-10 py-8">
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
              <div className="space-y-5">
                {/* Info card */}
                <div className={`rounded-xl border p-5 ${isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-gray-200'}`}>
                  <h3 className={`text-sm font-semibold uppercase tracking-wider mb-4 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
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
                </div>

                {/* Recent uploads */}
                <div className={`rounded-xl border p-5 ${isDark ? 'bg-white/[0.03] border-white/10' : 'bg-white border-gray-200'}`}>
                  <h3 className={`text-sm font-semibold uppercase tracking-wider mb-4 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Recent Theses in Repository
                  </h3>
                  {uploadsLoading ? (
                    <div className="flex justify-center py-4"><Spinner /></div>
                  ) : uploadedTheses.length === 0 ? (
                    <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>No theses in repository yet.</p>
                  ) : (
                    <ul className="space-y-2">
                      {uploadedTheses.slice(0, 5).map((t) => (
                        <li key={t.id}>
                          <Link
                            to={`/repository/${t.id}`}
                            className={`text-sm hover:underline line-clamp-1 ${isDark ? 'text-blue-400' : 'text-blue-600'}`}
                          >
                            {t.title}
                          </Link>
                          <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                            {' '}· {t.program} · {t.year}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
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
                      className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors"
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
      </main>
    </div>
  );
}
