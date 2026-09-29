# Document processing on one VPS

Thesis metadata previews, title previews, final thesis uploads, and access document OCR now use the PostgreSQL `processing_jobs` table. The web process returns a job ID (or an access-request claim) after accepting a validated file. One separate worker performs the slow work. Repository search and title similarity checks remain synchronous.

## Start and monitor

1. Back up PostgreSQL and private/media files, then run `python manage.py migrate`.
2. Start the web process with `DJANGO_ENV=production`. SBERT loads and completes a warm encode before the WSGI app is ready. Check `/api/v1/ready` for HTTP 200; `/api/v1/health` remains a basic process check.
3. Start **one** long-running `python manage.py process_jobs` process with the same settings, database, and private/media mounts as the web process. Configure the service manager to restart it on failure. The Windows demo launcher starts a hidden worker and records `worker.pid` and `worker.stderr.log` in `.demo-run`.
4. Watch `thesys.performance` logs for stage times. They contain a request ID or job ID and stage name, without document text, search text, names, or email addresses.

The worker claims one job at a time. Its lease refreshes while processing; a crashed worker's job becomes claimable after about two minutes. Each job has at most three attempts. Terminal results remain available for two days, after which the worker prunes them. Private working files are removed when a job reaches a terminal state; source verification documents follow their existing retention policy.

The authenticated `GET /api/v1/jobs/<id>/` endpoint only returns jobs owned by the caller. The public access-request claim status endpoint distinguishes `processing`, email verification, manual review, and rejection. A browser may stop polling after a file is replaced; this does not cancel the server job.

## Rollout and rollback

`DOCUMENT_PROCESSING_ASYNC` defaults to true. Set it to false only as a temporary rollback for thesis upload and preview endpoints; this restores their synchronous behavior and original timeout risk. Access-request OCR always uses the worker. Keep the worker running until queued jobs drain before disabling it. Do not remove the `processing_jobs` table while jobs exist.

For a title-vector backfill after migration, run `python manage.py embed_theses --titles-only`. A title vector is reused only when its dimensions and model-and-title fingerprint match. Editing a thesis title through Django Admin regenerates its title vector; if generation fails, title matching falls back to encoding that one stale title on demand. If titles are changed through another path, run the backfill command or regenerate those vectors there as well.

The access-request email path avoids replaying OCR or sending a second email after the request reaches `pending_email_verification`. As with ordinary SMTP, a process crash between committing the verification token and actual delivery cannot prove whether the message was sent. An administrator can review such a request if the applicant reports no email.
