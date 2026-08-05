/**
 * ThemeToggle — Foundation Phase dark/light mode toggle button.
 *
 * Renders a sun (☀️) in dark mode and a moon (🌙) in light mode so the icon
 * represents what clicking will switch TO. Keyboard-accessible with a visible
 * focus ring.
 *
 * Requirements: 14 (theme toggle), 15 (dark mode toggle), 16 (responsive).
 */

import { useTheme } from '../../context/ThemeContext';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label="Toggle theme"
      className="rounded-md p-2 text-xl transition-colors hover:bg-gray-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary dark:hover:bg-gray-700"
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  );
}
