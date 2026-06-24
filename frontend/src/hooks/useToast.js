/**
 * useToast — access the global toast notifier.
 *
 * Usage:
 *   const { toast } = useToast();
 *   toast.success('Thesis uploaded.');
 *   toast.error('Upload failed. Please try again.');
 *   toast.info('Validating title…');
 *
 * Must be used within a <ToastProvider> (mounted in main.jsx).
 */

import { useContext } from 'react';
import { ToastContext } from '../context/ToastContext';

export function useToast() {
  const ctx = useContext(ToastContext);
  if (ctx === undefined) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}
