/**
 * ThemeContext — Foundation Phase theme system.
 *
 * Provides a `theme` state ('light' | 'dark'), a `toggleTheme()` function,
 * and persists the preference to localStorage under the key 'thesys.theme'.
 * The provider toggles the 'dark' class on <html> so Tailwind's darkMode: 'class'
 * strategy activates dark-mode utilities.
 *
 * Requirements: 14 (theme system), 15 (light default, dark toggle), 16.2 (localStorage persistence).
 */

import { createContext, useContext, useState, useEffect } from 'react';

const STORAGE_KEY = 'thesys.theme';

const ThemeContext = createContext(undefined);

function getInitialTheme() {
  if (typeof window === 'undefined') return 'light';
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'dark' || stored === 'light') return stored;
  // Respect OS/browser dark mode preference when no stored choice exists
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light'; // fallback default
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
