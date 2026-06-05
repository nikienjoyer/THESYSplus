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
 *
 * Phase 1.1 Step 1: isDark ternaries replaced with semantic token utilities
 * from tokens.css. Layout, spacing, behaviour, and routes are unchanged.
 * isDark is retained only where an inline style or non-class value is needed
 * (the AuthLayout grid background; the Sun/Moon icon swap).
 */

import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';
import { Sun, Moon } from 'lucide-react';
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

function initials(user) {
  if (!user) return '?';
  const f = (user.first_name || '').charAt(0).toUpperCase();
  const l = (user.last_name || '').charAt(0).toUpperCase();
  return f + l || user.email?.charAt(0).toUpperCase() || '?';
}

// ── Avatar button + dropdown ──────────────────────────────────────────────
// isDark is retained for the AvatarFallback background (blue tint differs
// between themes) and is still passed in by LandingPage which has its own
// theme derivation. All other colours use semantic tokens.
export function AvatarDropdown({ user, isDark, onSignOut }) {
  const { dataUrl: avatarUrl } = useProfilePicture();
  const [dropOpen, setDropOpen] = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const dropRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (dropRef.current && !dropRef.current.contains(e.target)) setDropOpen(false);
    }
    if (dropOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [dropOpen]);

  useEffect(() => {
    function handleEscape(e) {
      if (e.key === 'Escape' && showLogoutModal) setShowLogoutModal(false);
    }
    if (showLogoutModal) document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showLogoutModal]);

  const handleSignOutClick = () => { setDropOpen(false); setShowLogoutModal(true); };
  const handleConfirmSignOut = () => { setShowLogoutModal(false); onSignOut(); };

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
          <div className="absolute right-0 mt-2 w-48 thesys-dropdown z-50 bg-surface-elevated border-[var(--color-border)]">
            {/* User info header */}
            <div className="px-4 py-2.5 border-b border-[var(--color-border-subtle)] mb-1">
              <p className="text-xs font-semibold truncate text-ink">
                {user ? `${user.first_name} ${user.last_name}`.trim() : 'User'}
              </p>
              <p className="text-[11px] truncate text-muted">
                {user?.role?.charAt(0).toUpperCase()}{user?.role?.slice(1)}
              </p>
            </div>

            <DropItem to="/profile" label="My Profile" onClose={() => setDropOpen(false)}>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
            </DropItem>
            <DropItem to="/profile?section=saved" label="Saved Theses" onClose={() => setDropOpen(false)}>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
            </DropItem>
            <DropItem to="/settings" label="Settings" onClose={() => setDropOpen(false)}>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            </DropItem>

            <div className="my-1 border-t border-[var(--color-border-subtle)]" />

            <button
              type="button"
              onClick={handleSignOutClick}
              className="w-full flex items-center gap-2.5 px-4 py-2 text-sm transition-colors text-danger hover:bg-danger-bg"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
              Sign Out
            </button>
          </div>
        )}
      </div>

      {/* ── Logout confirmation modal ─────────────────────────────────────── */}
      {showLogoutModal && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="logout-modal-title"
        >
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setShowLogoutModal(false)}
            aria-hidden="true"
          />

          <div className="relative w-full max-w-sm rounded-2xl border border-[var(--color-border)] bg-surface-elevated p-6 shadow-2xl">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4 bg-danger-bg">
              <svg className="w-5 h-5 text-danger" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
              </svg>
            </div>

            <h2
              id="logout-modal-title"
              className="text-lg font-bold text-center mb-2 text-ink"
            >
              Sign out?
            </h2>
            <p className="text-sm text-center mb-6 text-body">
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
                className="w-full px-4 py-2.5 rounded-xl text-sm font-semibold border border-[var(--color-border)] text-body hover:bg-[var(--color-surface-secondary)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
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

  useEffect(() => {
    function handleEscape(e) {
      if (e.key === 'Escape' && mobileMenuOpen) setMobileMenuOpen(false);
    }
    if (mobileMenuOpen) document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [mobileMenuOpen]);

  return (
    <>
      <nav className="px-5 sm:px-10 py-3 border-b border-[var(--color-border-subtle)] bg-canvas/75 backdrop-blur-md sticky top-0 z-30">

        {/* ── MOBILE row (< lg) ─────────────────────────────────────── */}
        <div className="flex items-center justify-between lg:hidden">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open navigation menu"
              className="w-9 h-9 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 flex-shrink-0 text-muted hover:text-ink hover:bg-[var(--color-icon-btn-hover-bg)]"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
              </svg>
            </button>
            <Link to="/" className="flex items-center gap-2 select-none">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center text-sm flex-shrink-0 bg-[var(--color-logo-bg)] ring-1 ring-[var(--color-logo-ring)]">🎓</div>
              <span className="text-sm font-bold tracking-wide text-ink">THESYS+</span>
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <AvatarDropdown user={user} isDark={isDark} onSignOut={handleSignOut} />
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className="w-9 h-9 flex items-center justify-center rounded-lg text-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 text-muted hover:text-ink hover:bg-[var(--color-icon-btn-hover-bg)]"
            >
              {isDark ? <Sun className="h-5 w-5 text-primary" /> : <Moon className="h-5 w-5 text-primary" />}
            </button>
          </div>
        </div>

        {/* ── DESKTOP row (≥ lg): 3-column grid ───────────────────────── */}
        <div className="hidden lg:grid grid-cols-[1fr_auto_1fr] items-center">
          {/* COL 1 — Logo + breadcrumb */}
          <div className="flex items-center gap-2 select-none">
            <Link to="/" className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center text-sm flex-shrink-0 bg-[var(--color-logo-bg)] ring-1 ring-[var(--color-logo-ring)]">🎓</div>
              <span className="text-sm font-bold tracking-wide text-ink">THESYS+</span>
            </Link>
            {breadcrumb && (
              <>
                <span className="text-sm text-subtle">/</span>
                <span className="text-sm font-medium text-body">{breadcrumb}</span>
              </>
            )}
          </div>

          {/* COL 2 — Centered nav links */}
          <ul className="flex items-center gap-1">
            {NAV_LINKS.map(({ label, to, key, soon }) => {
              const isActive = activePage === key;
              return (
                <li key={key}>
                  <Link
                    to={soon ? '#' : to}
                    onClick={soon ? (e) => e.preventDefault() : undefined}
                    aria-disabled={soon}
                    aria-current={isActive ? 'page' : undefined}
                    className={[
                      'relative px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-150',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400',
                      soon
                        ? 'text-subtle pointer-events-none cursor-default'
                        : isActive
                        ? 'bg-nav-active-bg text-nav-active-text'
                        : 'text-muted hover:text-ink hover:bg-nav-hover-bg',
                    ].join(' ')}
                  >
                    {label}
                    {soon && (
                      <span className="ml-1 text-[9px] uppercase tracking-wider align-middle text-subtle">soon</span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>

          {/* COL 3 — Actions */}
          <div className="flex items-center gap-2 justify-end">
            <Link
              to="/upload"
              className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 active:bg-blue-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            >
              Upload Thesis
            </Link>
            <AvatarDropdown user={user} isDark={isDark} onSignOut={handleSignOut} />
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className="w-9 h-9 flex items-center justify-center rounded-lg text-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 text-muted hover:text-ink hover:bg-[var(--color-icon-btn-hover-bg)]"
            >
              {isDark ? <Sun className="h-5 w-5 text-primary" /> : <Moon className="h-5 w-5 text-primary" />}
            </button>
          </div>
        </div>
      </nav>

      {/* ── Mobile drawer (portal) ─────────────────────────────────────── */}
      {mobileMenuOpen && createPortal(
        <div
          className="fixed inset-0 z-[9999] lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />

          <div className="absolute top-0 left-0 bottom-0 w-72 max-w-[85vw] shadow-2xl bg-surface-elevated border-r border-[var(--color-border)]">
            {/* Drawer header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center text-sm bg-[var(--color-logo-bg)] ring-1 ring-[var(--color-logo-ring)]">🎓</div>
                <span className="text-sm font-bold tracking-wide text-ink">THESYS+</span>
              </div>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Close navigation menu"
                className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors text-muted hover:text-ink hover:bg-[var(--color-icon-btn-hover-bg)]"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>

            {/* Drawer nav links */}
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
                        className={[
                          'block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors',
                          soon
                            ? 'text-subtle cursor-default'
                            : isActive
                            ? 'bg-info-bg text-primary font-semibold'
                            : 'text-body hover:bg-[var(--color-surface-secondary)] hover:text-ink',
                        ].join(' ')}
                      >
                        {label}
                        {soon && (
                          <span className="ml-1.5 text-[9px] uppercase tracking-wider text-subtle">soon</span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>

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
// isDark prop removed — colours now handled by semantic tokens on parent.
function DropItem({ to, label, onClose, children }) {
  return (
    <Link
      to={to}
      onClick={onClose}
      className="flex items-center gap-2.5 px-4 py-2 text-sm transition-colors text-body hover:bg-[var(--color-surface-secondary)] hover:text-ink"
    >
      {children}
      {label}
    </Link>
  );
}
