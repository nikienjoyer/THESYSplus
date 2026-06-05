import thesysColors from './src/styles/tokens.js';

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      // ── THESYS+ semantic design tokens (Phase 1.1)
      // All values resolve to CSS custom properties defined in tokens.css.
      // The .dark class on <html> redefines those variables, so every
      // utility (bg-canvas, text-muted, etc.) automatically resolves to
      // the correct theme value without any isDark ternary in JSX.
      colors: {
        ...thesysColors,

        // ── shadcn/ui semantic color tokens
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      // ── THESYS+ z-index scale (Phase 1.4)
      // Mirrors --z-* CSS custom properties in tokens.css.
      // Use z-navbar, z-dropdown, z-modal in JSX instead of z-[9999] etc.
      zIndex: {
        'base':     '0',
        'raised':   '10',
        'sticky':   '20',
        'navbar':   '30',
        'dropdown': '50',
        'modal':    '9999',
      },
      // ── THESYS+ easing scale (Phase 1.4)
      // Matches --ease-* CSS custom properties in tokens.css.
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
        'out':    'cubic-bezier(0, 0, 0.2, 1)',
        'in':     'cubic-bezier(0.4, 0, 1, 1)',
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      // ── THESYS+ duration scale (Phase 1.4)
      transitionDuration: {
        'fast':    '120ms',
        'normal':  '150ms',
        'surface': '180ms',
        'enter':   '200ms',
      },
      // ── THESYS+ box shadow tokens
      boxShadow: {
        'card':         '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)',
        'card-md':      '0 4px 12px -2px rgb(0 0 0 / 0.10), 0 2px 4px -2px rgb(0 0 0 / 0.06)',
        'card-lift':    '0 8px 24px -4px rgb(0 0 0 / 0.14), 0 2px 8px -2px rgb(0 0 0 / 0.08)',
        'blue-glow':    '0 0 0 1px rgb(59 130 246 / 0.15), 0 4px 16px -4px rgb(59 130 246 / 0.25)',
        'blue-glow-sm': '0 0 0 1px rgb(59 130 246 / 0.10), 0 2px 8px -2px rgb(59 130 246 / 0.15)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'shimmer': 'shimmer 1.8s linear infinite',
        'fade-in': 'fade-in 0.2s ease-out forwards',
      },
    },
  },
  plugins: [
    require('tailwindcss-animate'),
  ],
};
