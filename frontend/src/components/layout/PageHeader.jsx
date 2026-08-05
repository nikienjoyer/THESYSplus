/**
 * PageHeader — the shared header contract.
 *
 * Renders the page H1 at one fixed scale, color, and position
 * (text-2xl / font-bold / text-ink, with a 1.5rem bottom margin on the
 * block) so the title lands in the identical spot on every route.
 *
 * The subtitle is passed as children so pages can include bespoke inline
 * elements (status badges, "semantic search enabled" markers, soft-loading
 * indicators) while the H1 itself stays uniform across the platform.
 *
 * Props:
 *   title      — page H1 text
 *   children   — optional subtitle / meta row rendered beneath the H1
 *   className  — optional extra classes on the <header> block
 */
export default function PageHeader({ title, children, className = '' }) {
  return (
    <header className={`mb-6 ${className}`.trim()}>
      <h1 className="text-2xl font-bold text-ink mb-1">{title}</h1>
      {children}
    </header>
  );
}
