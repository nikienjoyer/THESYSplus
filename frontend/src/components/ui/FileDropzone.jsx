/**
 * FileDropzone — reusable drag-and-drop + click-to-browse file input.
 *
 * Handles file acquisition, client-side validation (type + size), the
 * drag-over visual state, and the staged-file chip with a remove control.
 * Validation failures are blocked before staging and reported via a toast,
 * so the file (and any downstream network request) never proceeds.
 *
 * Canonical limits (THESYS+): PDF / DOCX only, 15 MB max.
 *
 * Props:
 *   file          — the currently staged File (controlled by the parent)
 *   onFileSelect  — called with a VALID File once it passes validation
 *   onRemove      — called when the user removes the staged file
 *   disabled      — disables interaction (e.g. while submitting)
 *   maxBytes      — size cap (default 15 MB)
 *   accept        — array of allowed extensions (default ['pdf','docx'])
 *   idleTitle / idleHint — copy for the empty state
 *   inputId       — id for the hidden <input> (label association)
 *
 * Accessibility: the drop area is a focusable button-role element;
 * Enter/Space open the native picker. The hidden input carries the
 * accept filter. The remove control is a labeled button.
 */

import { useRef, useState, useId } from 'react';
import { UploadCloud, FileText, X } from 'lucide-react';
import { useToast } from '../../hooks/useToast';

const DEFAULT_MAX_BYTES = 15 * 1024 * 1024; // 15 MB — canonical THESYS+ limit

const MIME_BY_EXT = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};

function fmtBytes(b) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileDropzone({
  file,
  onFileSelect,
  onRemove,
  disabled = false,
  maxBytes = DEFAULT_MAX_BYTES,
  accept = ['pdf', 'docx'],
  idleTitle = 'Drag & drop your file here',
  idleHint,
  inputId,
}) {
  const { toast } = useToast();
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const generatedId = useId();
  const fieldId = inputId || `file-dropzone-${generatedId}`;

  const maxMb = Math.round(maxBytes / (1024 * 1024));
  const acceptAttr = accept
    .flatMap((ext) => [`.${ext}`, MIME_BY_EXT[ext]].filter(Boolean))
    .join(',');
  const hint = idleHint || `PDF or DOCX · max ${maxMb} MB`;

  // Validate then stage (or reject with a toast).
  const handleFile = (f) => {
    if (!f) return;
    const ext = f.name.toLowerCase().split('.').pop();
    if (!accept.includes(ext)) {
      toast.error(`Only ${accept.map((e) => e.toUpperCase()).join(' and ')} files are allowed.`);
      return;
    }
    if (f.size > maxBytes) {
      toast.error(`File exceeds the ${maxMb} MB limit (selected: ${fmtBytes(f.size)}).`);
      return;
    }
    onFileSelect?.(f);
  };

  const openPicker = () => {
    if (disabled) return;
    inputRef.current?.click();
  };

  const onKeyDown = (e) => {
    if (disabled) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openPicker();
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  };

  // ── Staged file chip ────────────────────────────────────────────────
  if (file) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-secondary)] px-4 py-3">
        <div className="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center bg-blue-50 dark:bg-blue-500/15">
          <FileText className="w-5 h-5 text-primary dark:text-blue-300" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate text-ink" title={file.name}>{file.name}</p>
          <p className="text-xs text-muted">{fmtBytes(file.size)}</p>
        </div>
        {!disabled && (
          <button
            type="button"
            onClick={() => { onRemove?.(); if (inputRef.current) inputRef.current.value = ''; }}
            aria-label={`Remove ${file.name}`}
            className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-md text-muted hover:text-ink hover:bg-[var(--color-icon-btn-hover-bg)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        )}
        <input
          ref={inputRef} id={fieldId} type="file" accept={acceptAttr}
          className="sr-only" disabled={disabled}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />
      </div>
    );
  }

  // ── Empty drop zone ─────────────────────────────────────────────────
  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label={`${idleTitle}. ${hint}. Activate to browse for a file.`}
      aria-disabled={disabled}
      onClick={openPicker}
      onKeyDown={onKeyDown}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      className={[
        'w-full flex flex-col items-center justify-center text-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400',
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
        dragOver
          ? 'border-primary bg-[var(--color-info-bg)]'
          : 'border-gray-300 dark:border-white/15 hover:border-gray-400 dark:hover:border-white/25 hover:bg-gray-50 dark:hover:bg-white/[0.03]',
      ].join(' ')}
    >
      <div className="w-11 h-11 rounded-full flex items-center justify-center bg-blue-50 dark:bg-blue-500/15">
        <UploadCloud className="w-5 h-5 text-primary dark:text-blue-300" aria-hidden="true" />
      </div>
      <p className="text-sm font-medium text-body">
        {idleTitle} <span className="text-primary">or browse</span>
      </p>
      <p className="text-xs text-muted">{hint}</p>
      <input
        ref={inputRef} id={fieldId} type="file" accept={acceptAttr}
        className="sr-only" disabled={disabled}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
      />
    </div>
  );
}
