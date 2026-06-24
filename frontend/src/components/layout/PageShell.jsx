/**
 * PageShell — canonical content band for every authenticated page.
 *
 * Guarantees an identical horizontal baseline (px-5 sm:px-10), content
 * band width (max-w-6xl mx-auto), and top padding (py-8) across all routes,
 * so navigating between tabs produces zero layout shift: the logo, the
 * left gutter, and the page H1 stay in the exact same position.
 *
 * Width tiering for focused task pages (Settings, Upload, Title Similarity,
 * Thesis Detail) is done by constraining their OWN inner content with a
 * max-w-* wrapper below a full-width header — the shell itself never changes.
 *
 * Props:
 *   children   — page content (header + body)
 *   className  — optional extra classes on the <main> band
 */
export default function PageShell({ children, className = '' }) {
  return (
    <main className={`max-w-6xl mx-auto px-5 sm:px-10 py-8 ${className}`.trim()}>
      {children}
    </main>
  );
}
