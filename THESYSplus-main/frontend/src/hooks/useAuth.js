/**
 * useAuth hook - ergonomic re-export of useAuthContext
 *
 * Allows callers to import { useAuth } from '@/hooks/useAuth'
 * instead of the longer useAuthContext import.
 *
 * Requirements: 25.
 */

export { useAuthContext as useAuth } from '../context/AuthContext';
