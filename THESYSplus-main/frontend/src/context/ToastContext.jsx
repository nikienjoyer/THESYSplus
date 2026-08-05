/**
 * ToastContext — global notification provider.
 *
 * Exposes a stable `toast` object via useToast():
 *   toast.success(message)
 *   toast.error(message)
 *   toast.info(message)
 *
 * Behaviour:
 *   - auto-dismiss after AUTO_DISMISS_MS (~4s)
 *   - manual dismiss (close button in the toast)
 *   - stack capped at MAX_TOASTS (oldest drops)
 *
 * The provider renders the ToastViewport portal itself, so mounting
 * <ToastProvider> is all a consumer needs.
 */

import { createContext, useState, useCallback, useMemo, useRef } from 'react';
import ToastViewport from '../components/ui/Toast';

const AUTO_DISMISS_MS = 4000;
const MAX_TOASTS = 3;

// eslint-disable-next-line react-refresh/only-export-components
export const ToastContext = createContext(undefined);

let idCounter = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    setToasts((cur) => cur.filter((t) => t.id !== id));
    const tm = timers.current.get(id);
    if (tm) {
      clearTimeout(tm);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback((type, message) => {
    if (!message) return;
    const id = ++idCounter;
    setToasts((cur) => {
      const next = [...cur, { id, type, message }];
      // Cap the stack — drop the oldest beyond MAX_TOASTS
      return next.length > MAX_TOASTS ? next.slice(next.length - MAX_TOASTS) : next;
    });
    const tm = setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    timers.current.set(id, tm);
    return id;
  }, [dismiss]);

  const value = useMemo(
    () => ({
      toast: {
        success: (m) => push('success', m),
        error: (m) => push('error', m),
        info: (m) => push('info', m),
      },
      dismiss,
    }),
    [push, dismiss]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}
