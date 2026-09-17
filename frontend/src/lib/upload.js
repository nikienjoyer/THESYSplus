/**
 * upload.js — single source of truth for thesis upload file limits.
 *
 * WHY THIS MODULE EXISTS
 * Three independent 15 MB constants previously lived in
 * TitleSimilarityPage, UploadThesisModal, and FileDropzone. The backend
 * has always accepted 25 MB (see `MAX_FILE_SIZE_BYTES` in
 * theses/validators.py for the upload path and
 * `ThesisExtractTitleView.MAX_FILE_SIZE_BYTES` for extraction), so the
 * browser was rejecting files the server would have happily taken —
 * and three separate constants is exactly how that drift happened.
 *
 * Anything user-facing that mentions a size MUST derive it from
 * `MAX_UPLOAD_MB` rather than hardcoding a number, so the copy can never
 * disagree with the enforced limit again.
 *
 * Keep this in step with the backend. If the backend cap changes, this
 * is the only frontend value to update.
 */

/** Hard byte cap for thesis uploads and metadata extraction — matches the backend. */
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

/** Whole-megabyte label derived from the cap, for use in user-facing copy. */
export const MAX_UPLOAD_MB = Math.round(MAX_UPLOAD_BYTES / (1024 * 1024));

/** Human-readable byte size (e.g. "4.2 MB"), shared by the upload surfaces. */
export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
