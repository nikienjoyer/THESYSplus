/**
 * AppNavbar — shared authenticated-page navbar for THESYS+.
 *
 * Used by: Repository, ThesisDetail, Upload, TitleSimilarity,
 *          TrendAnalysis, Profile, Settings.
 *
 * Layout (desktop):
 *   LEFT  (flex-1): hamburger (mobile) · THESYS+ logo
 *   CENTER (auto):  Home · Repository · Title Similarity · Trend Analysis · Analytics
 *   RIGHT (flex-1): Upload Thesis (CTA) · Profile Avatar Dropdown · Theme Toggle
 *
 * Active state: pill-style background highlight — immediately visible in
 * both light and dark mode.
 *
 * Profile dropdown: My Profile · Settings · Divider · Sign Out
 *
 * Props:
 *   activePage (string) — highlights the matching nav link
 *   breadcrumb (string | null) — optional breadcrumb text after logo
 */

import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useTheme } from '../../context/ThemeContext';
import { useProfilePicture } from '../../hooks/useProfilePicture';
import { Avatar, AvatarImage, AvatarFallback } from '../shadcn/avatar';

const NAV_LINKS = [
  { label: 'Home',             to: '/',                 key: 'home'       },
  { label: 'Repository',       to: '/repository',       key: 'repository' },
  { label: 'Title Similarity', to: '/title-similarity', key: 'similarity' },
  { label: 'Trend Analysis',   to: '/trend-analysis',   key: 'trends'     },
  { label: 'Analytics',        to: '/analytics',        key: 'analytics'  },
];


// Compute avatar initials from the user object.
function initials(user) {
  if (!user) return '?';
  const f = (user.first_name || '').charAt(0).toUpperCase();
  const l = (user.last_name || '').charAt(0).toUpperCase();
  return f + l || user.email?.charAt(0).toUpperCase() || '?';
}

// ── Avatar button + dropdown — used by both AppNavbar and LandingPage ──────
export function AvatarDropdown({ user, isDark, onSignOut }) {
  const { dataUrl: avatarUrl } = useProfilePicture();
  const [dropOpen, setDropOpen]         = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const dropRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (dropRef.current && !dropRef.current.contains(e.target)) {
        setDropOpen(false);
      }
    }
    if (dropOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [dropOpen]);

  // Close modal on Escape key
  useEffect(() => {
    function handleEscape(e) {
      if (e.key === 'Escape' && showLogoutModal) {
        setShowLogoutModal(false);
      }
    }
    if (showLogoutModal) document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showLogoutModal]);

  // Close dropdown when modal opens
  const handleSignOutClick = () => {
    setDropOpen(false);
    setShowLogoutModal(true);
  };

  const handleConfirmSignOut = () => {
    setShowLogoutModal(false);
    onSignOut();
  };

  return (
    <>
      <div className="relative" ref={dropRef}>
        <button
          type="button"
          onClick={() => setDropOpen((o) => !o)}
          aria-label="Profile menu"
          aria-expanded={dropOpen}
          className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-full transition-opacity hover:opacity-90 flex-shrink-0"
        >
          <Avatar className="w-8 h-8">
            {avatarUrl && <AvatarImage src={avatarUrl} alt="Profile" />}
            <AvatarFallback
              className={`text-xs font-bold ${
                isDark ? 'bg-blue-600/30 text-blue-200' : 'bg-blue-100 text-blue-700'
              }`}
            >
              {initials(user)}
            </AvatarFallback>
          </Avatar>
        </button>

        {dropOpen && (
          <div
            className={`absolute right-0 mt-2 w-48 thesys-dropdown z-50 ${
              isDark
                ? 'bg-[#0f1a3a] border-white/[0.09]'
                : 'bg-white border-slate-200'
            }`}
          >
            {/* User info header */}
            <div className={`px-4 py-2.5 border-b mb-1 ${isDark ? 'border-white/10' : 'border-gray-100'}`}>
              <p className={`text-xs font-semibold truncate ${isDark ? 'text-white' : 'text-gray-900'}`}>
                {user ? `${user.first_name} ${user.last_name}`.trim() : 'User'}
              </p>
              <p className={`text-[11px] truncate ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                {user?.role?.charAt(0).toUpperCase()}{user?.role?.slice(1)}
              </p>
            </div>

            <DropItem to="/profile" label="My Profile" isDark={isDark} onClose={() => setDropOpen(false)}>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
            </DropItem>
            <DropItem to="/profile?section=saved" label="Saved Theses" isDark={isDark} onClose={() => setDropOpen(false)}>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
            </DropItem>
            <DropItem to="/settings" label="Settings" isDark={isDark} onClose={() => setDropOpen(false)}>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            </DropItem>

            <div className={`my-1 border-t ${isDark ? 'border-white/10' : 'border-gray-100'}`} />

            <button
              type="button"
              onClick={handleSignOutClick}
              className={`w-full flex items-center gap-2.5 px-4 py-2 text-sm transition-colors ${
                isDark ? 'text-rose-400 hover:bg-rose-500/10' : 'text-rose-600 hover:bg-rose-50'
              }`}
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
              Sign Out
            </button>
          </div>
        )}
      </div>

      {/* ── Logout confirmation modal (rendered via Portal) ─────────────────────────────── */}
      {showLogoutModal && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="logout-modal-title"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setShowLogoutModal(false)}
            aria-hidden="true"
          />

          {/* Modal card */}
          <div
            className={`relative w-full max-w-sm rounded-2xl border p-6 shadow-2xl ${
              isDark
                ? 'bg-[#0f1a3a] border-white/10'
                : 'bg-white border-gray-200'
            }`}
          >
            {/* Icon */}
            <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4 ${
              isDark ? 'bg-rose-500/15' : 'bg-rose-50'
            }`}>
              <svg className="w-5 h-5 text-rose-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
              </svg>
            </div>

            <h2
              id="logout-modal-title"
              className={`text-lg font-bold text-center mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}
            >
              Sign out?
            </h2>
            <p className={`text-sm text-center mb-6 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
              You will need to sign in again to access your saved theses and research tools.
            </p>

            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={handleConfirmSignOut}
                className="w-full px-4 py-2.5 rounded-xl bg-rose-600 text-white text-sm font-semibold hover:bg-rose-700 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
              >
                Sign Out
              </button>
              <button
                type="button"
                onClick={() => setShowLogoutModal(false)}
                className={`w-full px-4 py-2.5 rounded-xl text-sm font-semibold border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                  isDark
                    ? 'border-white/15 text-gray-300 hover:bg-white/[0.06]'
                    : 'border-gray-200 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Stay Logged In
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}


export default function AppNavbar({ activePage = '', breadcrumb = null }) {
  const { theme, toggleTheme } = useTheme();
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const isDark = theme === 'dark';
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleSignOut = async () => {
    await signOut();
    navigate('/sign-in');
  };

  // Close mobile menu on Escape key
  useEffect(() => {
    function handleEscape(e) {
      if (e.key === 'Escape' && mobileMenuOpen) {
        setMobileMenuOpen(false);
      }
    }
    if (mobileMenuOpen) document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [mobileMenuOpen]);

  const navBorderCls = isDark
    ? 'border-white/[0.06] bg-[#080d24]/75 backdrop-blur-md'
    : 'border-gray-200/80 bg-white/75 backdrop-blur-md';

  return (
    <>
      {/*
       * Three-column grid:
       *   col 1 (flex-1): hamburger + logo — left-aligned
       *   col 2 (auto):   nav links — truly centered
       *   col 3 (flex-1): actions — right-aligned
       * On screens < lg the center column is hidden; hamburger reveals drawer.
       */}
      <nav
        className={`grid grid-cols-[1fr_auto_1fr] items-center px-5 sm:px-10 py-3 border-b sticky top-0 z-30 ${navBorderCls}`}
      >
        {/* ── COL 1 — Logo ─────────────────────────────────────────── */}
        <div className="flex items-center gap-3">
          {/* Hamburger — mobile only */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            aria-label="Open navigation menu"
            className={`lg:hidden w-9 h-9 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 flex-shrink-0 ${
              isDark
                ? 'text-gray-400 hover:text-white hover:bg-white/10'
                : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
            }`}
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
          </button>

          {/* Logo + optional breadcrumb */}
          <div className="flex items-center gap-2 select-none">
            <Link to="/" className="flex items-center gap-2">
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm flex-shrink-0 ${
                  isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
                }`}
              >
                🎓
              </div>
              <span
                className={`text-sm font-bold tracking-wide ${isDark ? 'text-white' : 'text-gray-900'}`}
              >
                THESYS+
              </span>
            </Link>
            {breadcrumb && (
              <>
                <span className={`text-sm ${isDark ? 'text-gray-600' : 'text-gray-400'}`}>/</span>
                <span className={`text-sm font-medium ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                  {breadcrumb}
                </span>
              </>
            )}
          </div>
        </div>

        {/* ── COL 2 — Centered nav links (desktop only) ────────────── */}
        <ul className="hidden lg:flex items-center gap-1">
          {NAV_LINKS.map(({ label, to, key, soon }) => {
            const isActive = activePage === key;
            return (
              <li key={key}>
                <Link
                  to={soon ? '#' : to}
                  onClick={soon ? (e) => e.preventDefault() : undefined}
                  aria-disabled={soon}
                  aria-current={isActive ? 'page' : undefined}
                  className={`
                    relative px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-150
                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400
                    ${soon
                      ? isDark
                        ? 'text-gray-600 pointer-events-none cursor-default'
                        : 'text-gray-300 pointer-events-none cursor-default'
                      : isActive
                      ? isDark
                        ? 'bg-white/10 text-white'
                        : 'bg-gray-100 text-gray-900'
                      : isDark
                      ? 'text-gray-400 hover:text-white hover:bg-white/[0.06]'
                      : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100/70'
                    }
                  `}
                >
                  {label}
                  {soon && (
                    <span
                      className={`ml-1 text-[9px] uppercase tracking-wider align-middle ${
                        isDark ? 'text-gray-600' : 'text-gray-400'
                      }`}
                    >
                      soon
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>

        {/* ── COL 3 — Actions (right-aligned) ─────────────────────── */}
        <div className="flex items-center gap-2 justify-end">
          {/* Upload CTA */}
          <Link
            to="/upload"
            className="hidden sm:inline-flex px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 active:bg-blue-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            Upload Thesis
          </Link>

          {/* Profile avatar dropdown */}
          <AvatarDropdown user={user} isDark={isDark} onSignOut={handleSignOut} />

          {/* Theme toggle — ALWAYS FAR RIGHT */}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            className={`w-9 h-9 flex items-center justify-center rounded-lg text-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
              isDark
                ? 'text-gray-400 hover:text-white hover:bg-white/10'
                : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
            }`}
          >
            {isDark ? '☀️' : '🌙'}
          </button>
        </div>
      </nav>

      {/* ── Mobile menu overlay (rendered via Portal) ─────────────────────────────── */}
      {mobileMenuOpen && createPortal(
        <div
          className="fixed inset-0 z-[9999] lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />

          {/* Menu drawer */}
          <div
            className={`absolute top-0 left-0 bottom-0 w-72 max-w-[85vw] shadow-2xl ${
              isDark
                ? 'bg-[#0f1a3a] border-r border-white/10'
                : 'bg-white border-r border-gray-200'
            }`}
          >
            {/* Header */}
            <div className={`flex items-center justify-between px-5 py-4 border-b ${
              isDark ? 'border-white/10' : 'border-gray-200'
            }`}>
              <div className="flex items-center gap-2">
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm ${
                    isDark ? 'bg-blue-600/20 ring-1 ring-blue-500/30' : 'bg-blue-100 ring-1 ring-blue-200'
                  }`}
                >
                  🎓
                </div>
                <span className={`text-sm font-bold tracking-wide ${isDark ? 'text-white' : 'text-gray-900'}`}>
                  THESYS+
                </span>
              </div>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Close navigation menu"
                className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${
                  isDark
                    ? 'text-gray-400 hover:text-white hover:bg-white/10'
                    : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
                }`}
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>

            {/* Nav links */}
            <nav className="p-4">
              <ul className="space-y-1">
                {NAV_LINKS.map(({ label, to, key, soon }) => {
                  const isActive = activePage === key;
                  return (
                    <li key={key}>
                      <Link
                        to={soon ? '#' : to}
                        onClick={(e) => {
                          if (soon) e.preventDefault();
                          else setMobileMenuOpen(false);
                        }}
                        aria-disabled={soon}
                        aria-current={isActive ? 'page' : undefined}
                        className={`block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                          soon
                            ? isDark
                              ? 'text-gray-600 cursor-default'
                              : 'text-gray-300 cursor-default'
                            : isActive
                            ? isDark
                              ? 'bg-blue-500/15 text-white'
                              : 'bg-blue-50 text-blue-700 font-semibold'
                            : isDark
                            ? 'text-gray-300 hover:bg-white/[0.07] hover:text-white'
                            : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                        }`}
                      >
                        {label}
                        {soon && (
                          <span
                            className={`ml-1.5 text-[9px] uppercase tracking-wider ${
                              isDark ? 'text-gray-600' : 'text-gray-400'
                            }`}
                          >
                            soon
                          </span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>

              {/* Upload CTA in mobile menu */}
              <Link
                to="/upload"
                onClick={() => setMobileMenuOpen(false)}
                className="mt-4 block w-full px-4 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-semibold text-center hover:bg-blue-700 transition-colors"
              >
                Upload Thesis
              </Link>
            </nav>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

// ── Dropdown item ─────────────────────────────────────────────────────────
function DropItem({ to, label, isDark, onClose, children }) {
  return (
    <Link
      to={to}
      onClick={onClose}
      className={`flex items-center gap-2.5 px-4 py-2 text-sm transition-colors ${
        isDark
          ? 'text-gray-300 hover:bg-white/[0.07] hover:text-white'
          : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
      }`}
    >
      {children}
      {label}
    </Link>
  );
}


