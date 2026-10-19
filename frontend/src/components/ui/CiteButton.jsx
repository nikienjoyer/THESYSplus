import { useEffect, useRef, useState } from 'react';
import { Quote } from 'lucide-react';
import { useToast } from '../../hooks/useToast';
import { formatCitation } from '../../utils/formatters';

// Editions the formats follow: APA 7th edition, the IEEE Reference Guide
// (current IEEE Editorial Style Manual) and MLA 9th edition.
const CITE_STYLES = [
  ['apa', 'APA 7th'],
  ['ieee', 'IEEE'],
  ['mla', 'MLA 9th'],
];

/**
 * Cite: formats a reference and copies it. Copying never counts toward
 * "Cited by"; that count comes from references saved on upload.
 *
 * `compact` renders a small text trigger for the Repository result cards;
 * the default is the bordered button used in the thesis page's action row.
 */
export default function CiteButton({ thesis, compact = false }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [style, setStyle] = useState('apa');
  const wrapRef = useRef(null);
  const text = formatCitation(thesis, style);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (e.type === 'keydown' ? e.key === 'Escape' : !wrapRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Citation copied.');
      setOpen(false);
    } catch {
      toast.error("Couldn't copy. Select the text and copy it instead.");
    }
  };

  const trigger = compact
    ? 'inline-flex items-center gap-1 rounded text-sm font-medium text-[color:var(--color-primary)] underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'
    : `w-full min-h-11 sm:min-h-0 px-0 sm:px-3 py-2 rounded-lg text-sm font-semibold border transition-colors flex items-center justify-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary border-border-strong text-body hover:bg-surface-secondary ${open ? 'bg-surface-secondary' : ''}`;

  // The action-row popover floats above the phone's bottom bar; the card
  // variant always drops below its link.
  const panel = compact
    ? 'absolute left-0 top-full mt-2 w-[min(28rem,calc(100vw-2rem))]'
    : 'fixed inset-x-4 bottom-[5.5rem] sm:absolute sm:inset-x-auto sm:bottom-auto sm:left-0 sm:top-full sm:mt-2 sm:w-[28rem]';

  return (
    <div ref={wrapRef} className={compact ? 'relative' : 'sm:relative'}>
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="dialog"
        className={trigger} title="Cite this thesis">
        {!compact && <Quote className="w-4 h-4" aria-hidden="true" />}
        <span className={compact ? '' : 'sr-only sm:not-sr-only'}>Cite</span>
      </button>
      {open && (
        <div role="dialog" aria-label="Cite this thesis"
          className={`${panel} z-50 rounded-xl border border-border-strong bg-surface-elevated p-4 text-left shadow-lg cursor-default`}>
          <div className="flex gap-1" role="group" aria-label="Citation style">
            {CITE_STYLES.map(([key, label]) => (
              <button key={key} type="button" onClick={() => setStyle(key)} aria-pressed={style === key}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                  style === key ? 'bg-primary-light text-[color:var(--color-primary)]' : 'text-muted hover:text-ink'}`}>
                {label}
              </button>
            ))}
          </div>
          <p className="mt-3 rounded-lg border border-border-default bg-surface-secondary px-3 py-2.5 text-sm leading-relaxed text-body select-all">
            {text}
          </p>
          <div className="mt-3 flex items-center justify-between gap-3">
            <p className="text-xs text-muted">Copying doesn't change "Cited by".</p>
            <button type="button" onClick={copy}
              className="flex-shrink-0 px-3 py-1.5 rounded-lg bg-primary-solid text-white text-sm font-semibold hover:bg-primary-solid-hover transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2">
              Copy
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
