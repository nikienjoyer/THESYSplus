/**
 * THESYS+ Design Tokens — Foundation Phase (JS export for Tailwind config)
 *
 * These values MUST stay in sync with tokens.css. They are consumed by
 * tailwind.config.js under theme.extend.colors so utility classes like
 * bg-background, text-primary, bg-accent resolve to CSS custom properties.
 *
 * Downstream phases should swap the hex values (in tokens.css) without
 * restructuring this file or the Tailwind config keys.
 */

// eslint-disable-next-line import/no-anonymous-default-export
export default {
  background: 'var(--color-background)', // PLACEHOLDER pending Figma palette
  primary: 'var(--color-primary)',       // PLACEHOLDER pending Figma palette
  accent: 'var(--color-accent)',         // PLACEHOLDER pending Figma palette
};
