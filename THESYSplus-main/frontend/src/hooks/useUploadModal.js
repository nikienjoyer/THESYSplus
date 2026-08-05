/**
 * useUploadModal — accessor for the global Upload Thesis modal controls.
 *
 * Returns { isOpen, open, close }. Call open() from any "Upload Thesis"
 * trigger; the modal is rendered once at the App root.
 */

import { useContext } from 'react';
import { UploadModalContext } from '../context/UploadModalContext';

export function useUploadModal() {
  const ctx = useContext(UploadModalContext);
  if (!ctx) {
    throw new Error('useUploadModal must be used within an UploadModalProvider');
  }
  return ctx;
}
