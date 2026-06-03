/**
 * SettingsPage — /settings
 *
 * Editable profile fields persisted to user-scoped localStorage keys:
 * "thesys.profile.<userId>" or "thesys.profile.<email>"
 *
 * Email is read-only (backend-controlled). Password change link is provided
 * as a pointer to the existing forgot-password flow.
 *
 * TODO: For production, bio, department, and research interests should be
 * persisted in the backend per user.
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Camera } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/ThemeContext';
import AppNavbar from '../components/layout/AppNavbar';
import { useProfilePicture } from '../hooks/useProfilePicture';
import { getUserData, setUserData } from '../utils/userStorage';

const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
const MAX_IMG_BYTES = 4 * 1024 * 1024; // 4 MB raw; will be re-encoded by canvas

export default function SettingsPage() {
  const { theme } = useTheme();
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const isDark = theme === 'dark';
  const photoInputRef = useRef(null);
  const saveRedirectTimerRef = useRef(null);

  // Clean up the post-save redirect timer if the component unmounts before it fires
  useEffect(() => () => { if (saveRedirectTimerRef.current) clearTimeout(saveRedirectTimerRef.current); }, []);

  const { dataUrl: savedAvatarUrl, save: saveAvatar, clear: clearAvatar } = useProfilePicture();

  // pendingAvatar tracks the in-Settings preview state:
  //   undefined  = no pending change (show savedAvatarUrl)
  //   null       = user clicked Remove (preview shows initials, but not saved yet)
  //   string     = new dataUrl selected (preview shows new photo, but not saved yet)
  const [pendingAvatar, setPendingAvatar] = useState(undefined);

  // The preview the Settings page shows — pending if dirty, else saved
  const avatarUrl = pendingAvatar !== undefined ? pendingAvatar : savedAvatarUrl;

  // Load user-scoped profile data
  const stored = useMemo(() => getUserData('profile', user, {}), [user]);
  const [firstName, setFirstName] = useState(user?.first_name || '');
  const [lastName, setLastName] = useState(user?.last_name || '');
  const [bio, setBio] = useState(stored.bio || '');
  const [department, setDepartment] = useState(stored.department || 'College of Computing Studies');
  const [interests, setInterests] = useState(stored.interests || '');
  const [saved, setSaved] = useState(false);
  const [photoError, setPhotoError] = useState('');

  useEffect(() => {
    if (user) {
      setFirstName((f) => f || user.first_name || '');
      setLastName((l) => l || user.last_name || '');
    }
  }, [user]);

  const handlePhotoChange = (e) => {
    const file = e.target.files?.[0];
    setPhotoError('');
    if (!file) return;

    if (!ACCEPTED_TYPES.includes(file.type)) {
      setPhotoError('Only PNG, JPG, JPEG, or WEBP images are accepted.');
      e.target.value = '';
      return;
    }
    if (file.size > MAX_IMG_BYTES) {
      setPhotoError('Image must be smaller than 4 MB.');
      e.target.value = '';
      return;
    }

    // Encode via canvas so we control output size and format (JPEG, quality 0.85)
    const reader = new FileReader();
    reader.onload = (ev) => {
      const img = new Image();
      img.onload = () => {
        const SIZE = 256; // max output dimension
        const canvas = document.createElement('canvas');
        const scale = Math.min(SIZE / img.width, SIZE / img.height, 1);
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        // Stage in pending preview — do not write to localStorage until Save
        setPendingAvatar(dataUrl);
        setPhotoError('');
      };
      img.src = ev.target.result;
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  const handleSave = (e) => {
    e.preventDefault();
    const profile = { bio, department, interests };
    setUserData('profile', user, profile);

    // Commit any pending avatar change to localStorage (updates navbar)
    if (pendingAvatar !== undefined) {
      if (pendingAvatar === null) {
        clearAvatar();
      } else {
        saveAvatar(pendingAvatar);
      }
      setPendingAvatar(undefined);
    }

    setSaved(true);
    // Redirect to /profile after 1000 ms so the user sees the updated info
    saveRedirectTimerRef.current = setTimeout(() => {
      navigate('/profile');
    }, 1000);
  };

  const inputCls = `w-full px-3 py-2 rounded-lg border text-sm outline-none transition-colors ${
    isDark
      ? 'bg-white/[0.04] border-white/10 text-gray-200 placeholder-gray-500 focus:border-blue-500/40'
      : 'bg-white border-gray-200 text-gray-700 placeholder-gray-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100'
  }`;
  const labelCls = `block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`;
  const readonlyCls = `w-full px-3 py-2 rounded-lg border text-sm ${
    isDark
      ? 'bg-white/[0.02] border-white/[0.06] text-gray-500 cursor-not-allowed'
      : 'bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed'
  }`;
  const sectionTitle = `text-xs font-semibold uppercase tracking-wider mb-4 ${isDark ? 'text-gray-400' : 'text-gray-600'}`;

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#080d24]' : 'bg-slate-50'}`}>
      <AppNavbar activePage="settings" breadcrumb="Settings" />

      <main className="max-w-2xl mx-auto px-5 py-8">
        <div className="mb-6">
          <h1 className={`text-2xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
            Account Settings
          </h1>
          <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
            Update your profile information and preferences.
          </p>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          {/* ── General ─────────────────────────────────────────── */}
          <section
            className="thesys-card p-5 space-y-4"
          >
            <h2 className={sectionTitle}>General</h2>

            {/* ── Profile photo ─────────────────────────────────── */}
            <div>
              <label className={labelCls}>Profile Photo</label>
              <div className="flex items-center gap-4">
                {/* Clickable preview with hover overlay */}
                <button
                  type="button"
                  onClick={() => photoInputRef.current?.click()}
                  className="group relative flex-shrink-0 w-16 h-16 rounded-full overflow-hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                  aria-label="Change profile photo"
                  title="Click to change photo"
                >
                  {/* Photo or initials */}
                  {avatarUrl ? (
                    <img src={avatarUrl} alt="Current avatar" className="w-full h-full object-cover" />
                  ) : (
                    <div className={`w-full h-full flex items-center justify-center text-xl font-bold ring-2 ${
                      isDark ? 'bg-blue-600/25 text-blue-200 ring-blue-500/30' : 'bg-blue-100 text-blue-700 ring-blue-200'
                    }`}>
                      {(user?.first_name?.[0] || '').toUpperCase()}{(user?.last_name?.[0] || '').toUpperCase() || '?'}
                    </div>
                  )}
                  {/* Hover overlay — fades in on hover */}
                  <div className="absolute inset-0 rounded-full bg-black/50 flex flex-col items-center justify-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
                    <Camera className="w-5 h-5 text-white" aria-hidden="true" />
                    <span className="text-[10px] font-semibold text-white leading-tight text-center px-1">
                      Change Photo
                    </span>
                  </div>
                </button>

                {/* Controls */}
                <div className="flex flex-col gap-2">
                  <label
                    htmlFor="avatar-upload"
                    className={`cursor-pointer inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                      isDark ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]' : 'border-gray-300 text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                    </svg>
                    Upload Photo
                  </label>
                  <input
                    id="avatar-upload"
                    ref={photoInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/webp"
                    onChange={handlePhotoChange}
                    className="sr-only"
                    aria-label="Upload profile photo"
                  />
                  {avatarUrl && (
                    <button
                      type="button"
                      onClick={() => setPendingAvatar(null)}
                      className={`text-xs text-left transition-colors ${isDark ? 'text-gray-600 hover:text-rose-400' : 'text-gray-400 hover:text-rose-500'}`}
                    >
                      Remove photo
                    </button>
                  )}
                  <p className={`text-xs ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                    PNG, JPG, WEBP · max 4 MB
                  </p>
                </div>
              </div>
              {photoError && (
                <p className={`text-xs mt-1.5 ${isDark ? 'text-rose-400' : 'text-rose-600'}`}>{photoError}</p>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>First Name</label>
                <input
                  type="text"
                  value={firstName}
                  readOnly
                  className={readonlyCls}
                  title="Name changes require contacting an administrator."
                />
                <p className={`text-xs mb-0.5 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                  Contact your administrator to change.
                </p>
              </div>
              <div>
                <label className={labelCls}>Last Name</label>
                <input type="text" value={lastName} readOnly className={readonlyCls} />
              </div>
            </div>

            <div>
              <label className={labelCls}>Department / College</label>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                maxLength={120}
                className={inputCls}
              />
            </div>

            <div>
              <label className={labelCls}>Bio</label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                maxLength={500}
                rows={3}
                placeholder="A short description about yourself…"
                className={inputCls}
              />
              <p className={`text-xs text-right mt-0.5 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                {bio.length} / 500
              </p>
            </div>

            <div>
              <label className={labelCls}>Research Interests</label>
              <input
                type="text"
                value={interests}
                onChange={(e) => setInterests(e.target.value)}
                maxLength={200}
                placeholder="e.g. AI, IoT, Natural Language Processing"
                className={inputCls}
              />
            </div>
          </section>

          {/* ── Account ─────────────────────────────────────────── */}
          <section
            className="thesys-card p-5 space-y-4"
          >
            <h2 className={sectionTitle}>Account</h2>

            <div>
              <label className={labelCls}>Institutional Email</label>
              <input
                type="email"
                value={user?.email || ''}
                readOnly
                className={readonlyCls}
              />
              <p className={`text-xs mt-0.5 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                Email is managed by the institution and cannot be changed here.
              </p>
            </div>

            <div>
              <label className={labelCls}>Password</label>
              <Link
                to="/forgot-password"
                className={`inline-flex items-center gap-1.5 text-sm font-medium ${
                  isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'
                }`}
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                </svg>
                Reset Password via Email
              </Link>
              <p className={`text-xs mt-0.5 ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>
                A password reset link will be sent to your institutional email.
              </p>
            </div>
          </section>

          {/* ── Actions ─────────────────────────────────────────── */}
          <div className="flex items-center justify-between gap-3">
            <Link
              to="/profile"
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                isDark
                  ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]'
                  : 'border-gray-200 text-gray-700 hover:bg-gray-50'
              }`}
            >
              Cancel
            </Link>

            <div className="flex items-center gap-3">
              {saved && (
                <span className={`text-sm font-medium ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                  ✓ Profile updated successfully
                </span>
              )}
              <button
                type="submit"
                className="px-5 py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors"
              >
                Save Changes
              </button>
            </div>
          </div>
        </form>
      </main>
    </div>
  );
}
