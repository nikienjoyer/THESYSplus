/**
 * UploadModalContext — global open/close state for the Upload Thesis modal.
 *
 * Uploading a thesis is an interstitial action: it should overlay the current
 * page (Repository, Analytics, Home, …) instead of redirecting to a standalone
 * route. Any "Upload Thesis" button across the app calls open() from this
 * context; the single <UploadThesisModal /> mounted in App renders the overlay.
 */

import { createContext, useCallback, useMemo, useState } from 'react';

// eslint-disable-next-line react-refresh/only-export-components
export const UploadModalContext = createContext(null);

export function UploadModalProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  const value = useMemo(() => ({ isOpen, open, close }), [isOpen, open, close]);

  return (
    <UploadModalContext.Provider value={value}>
      {children}
    </UploadModalContext.Provider>
  );
}
