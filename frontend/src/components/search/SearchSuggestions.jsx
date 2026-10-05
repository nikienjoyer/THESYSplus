/**
 * SearchSuggestions: a search input with suggestions while typing.
 *
 * Calls GET /theses/suggest/?q= 200ms after typing stops, cancelling any
 * request still in flight. Signed-out users only get keywords back (the
 * server decides). ARIA combobox: ↑/↓ move, Enter picks, Esc closes.
 * Picking a thesis opens it, or calls onPickTitle when given; picking a keyword or author calls onPick(text).
 * Errors are ignored: suggestions are a convenience and must never block search.
 */

import { useEffect, useId, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../../api/client';

const GROUPS = [
  { key: 'titles',   label: 'Theses'   },
  { key: 'keywords', label: 'Keywords' },
  { key: 'authors',  label: 'Authors'  },
];

export default function SearchSuggestions({
  value, onChange, onPick, onPickTitle, inputClassName = '', wrapperClassName = '', placeholder, ariaLabel,
}) {
  const navigate = useNavigate();
  const listId = useId();
  const [items, setItems] = useState([]);
  const [isOpen, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const skipNext = useRef(false);
  const open = isOpen && value.trim().length >= 2;

  useEffect(() => {
    if (skipNext.current) { skipNext.current = false; return undefined; }
    const q = value.trim();
    if (q.length < 2) return undefined; // list is hidden by `show` below
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const { data } = await client.get('/theses/suggest/', { params: { q }, signal: ctrl.signal });
        const flat = GROUPS.flatMap(({ key }) => (data[key] || []).map((v) => (
          key === 'titles'
            ? { group: key, text: v.title, id: v.id, meta: v.year }
            : { group: key, text: v }
        )));
        setItems(flat);
        setActive(-1);
        setOpen(flat.length > 0);
      } catch {
        /* aborted or failed: keep the input usable, show nothing */
      }
    }, 200);
    return () => { clearTimeout(timer); ctrl.abort(); };
  }, [value]);

  const pick = (item) => {
    setOpen(false);
    if (item.group === 'titles') {
      if (onPickTitle) { onPickTitle({ id: item.id, title: item.text, year: item.meta }); return; }
      navigate(`/repository/${item.id}`);
      return;
    }
    skipNext.current = true; // the value change below should not reopen the list
    onPick(item.text);
  };

  const onKeyDown = (e) => {
    if (!open) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % items.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i <= 0 ? items.length - 1 : i - 1)); }
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); pick(items[active]); }
    else if (e.key === 'Escape') { setOpen(false); }
  };

  return (
    <div className={`relative ${wrapperClassName}`}>
      <input
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        aria-label={ariaLabel}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onFocus={() => items.length && setOpen(true)}
        className={inputClassName}
        autoComplete="off"
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-full mt-1 z-40 max-h-80 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-surface-elevated shadow-lg py-1 text-left"
        >
          {items.map((item, i) => (
            <li key={`${item.group}-${item.text}-${i}`} role="presentation">
              {(i === 0 || items[i - 1].group !== item.group) && (
                <p className="px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  {GROUPS.find((g) => g.key === item.group).label}
                </p>
              )}
              <div
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => { e.preventDefault(); pick(item); }}
                onMouseEnter={() => setActive(i)}
                className={`px-3 py-2 text-sm cursor-pointer flex justify-between gap-3 ${
                  i === active ? 'bg-nav-hover-bg text-ink' : 'text-body'
                }`}
              >
                <span className="truncate">{item.text}</span>
                {item.meta && <span className="text-xs text-muted tabular-nums">{item.meta}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
