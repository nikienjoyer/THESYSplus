/**
 * MainLayout — Foundation Phase shared layout wrapper.
 *
 * Renders a top-of-page header slot containing the ThemeToggle and an <Outlet />
 * for nested route children. NO real header content, NO real navigation, NO
 * sidebar — only the slot positions so future phases can fill them in without
 * restructuring the route tree.
 *
 * Requirements: 12 (Landing page surface), 25 (folder structure).
 */

import { Outlet } from 'react-router-dom';
import ThemeToggle from './ThemeToggle';

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-background text-gray-900 dark:text-gray-100">
      {/* Header slot — ThemeToggle lives here; real nav lands in a later phase */}
      <header className="flex items-center justify-end px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <ThemeToggle />
      </header>

      {/* Route content */}
      <main>
        <Outlet />
      </main>
    </div>
  );
}
