/**
 * Toast / ToastViewport — presentational layer for the global notification system.
 *
 * Rendered once by ToastProvider via a portal to <body>. Fixed-position,
 * top-right on desktop and top-center on mobile, above modals.
 *
 * Theming: each toast sits on `--color-surface-elevated` with a status-quartet
 * colored icon + left accent (emerald / rose / blue). Text uses ink/body tokens.
 *
 * Accessibility:
 *   - success / info  → role="status",  aria-live="polite"
 *   - error           → role="alert",   aria-live="assertive"
 *   - manual dismiss button is keyboard-focusable with an aria-label
 *   - entrance animation is suppressed under prefers-reduced-motion (index.css)
 */

import { createPortal } from 'react-dom';
import { CheckCircle2, TriangleAlert, Info, X } from 'lucide-react';

const TYPE_META = {
  success: {
    Icon: CheckCircle2,
    iconClass: 'text-success',
    accent: 'var(--color-success)',
    live: 'polite',
    role: 'status',
  },
  error: {
    Icon: TriangleAlert,
    iconClass: 'text-danger',
    accent: 'var(--color-danger)',
    live: 'assertive',
    role: 'alert',
  },
  info: {
    Icon: Info,
    iconClass: 'text-primary',
    accent: 'var(--color-primary)',
    live: 'polite',
    role: 'status',
  },
};

function ToastItem({ toast, onDismiss }) {
  const meta = TYPE_META[toast.type] || TYPE_META.info;
  const { Icon } = meta;

  return (
    <div
      role={meta.role}
      aria-live={meta.live}
      className="thesys-toast-enter pointer-events-auto w-full sm:w-80 flex items-start gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] shadow-2xl px-4 py-3 overflow-hidden"
      style={{ borderLeftWidth: '3px', borderLeftColor: meta.accent }}
    >
      <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${meta.iconClass}`} aria-hidden="true" />
      <p className="flex-1 text-sm leading-snug text-body break-words min-w-0">
        {toast.message}
      </p>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
        className="flex-shrink-0 -mr-1 -mt-0.5 w-6 h-6 flex items-center justify-center rounded-md text-muted hover:text-ink hover:bg-[var(--color-icon-btn-hover-bg)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
      >
        <X className="w-4 h-4" aria-hidden="true" />
      </button>
    </div>
  );
}

export default function ToastViewport({ toasts, onDismiss }) {
  if (typeof document === 'undefined') return null;

  return createPortal(
    <div
      className="fixed top-4 left-1/2 -translate-x-1/2 sm:left-auto sm:right-4 sm:translate-x-0 flex flex-col gap-2 w-[calc(100vw-2rem)] sm:w-auto pointer-events-none"
      style={{ zIndex: 10000 }}
      aria-live="off"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>,
    document.body
  );
}
