# THESYSplus temporary ngrok demonstration (Windows)

This setup keeps the React/Vite frontend on Vercel and runs Django, PostgreSQL,
uploads, OCR, and the semantic model on the Windows host. Only Django's loopback
HTTP port is tunneled. It does not publish PostgreSQL, the media directory, or
the ngrok inspection interface.

## Local backend

Required local services are PostgreSQL 16, Python 3.11 in `backend/venv`,
Tesseract OCR, and Poppler. The backend's existing `.env` contains the database
and Gmail SMTP settings. The ignored `.env.demo` holds separate random Django
and JWT secrets; never commit it or paste its contents into chat. The frontend
origin and email-link base URL are both `https://thesysplus.vercel.app`.

From the repository root in PowerShell, start the secure backend:

```powershell
& .\backend\scripts\start_demo_backend.ps1
```

This collects Django admin static files and starts Waitress on
`127.0.0.1:8000`. It refuses to start if another process owns the port. The
launcher and listener PIDs and logs are under ignored `backend/.demo-run/`.
It does not install an automatic startup service. The demo WSGI wrapper accepts
an HTTPS forwarding chain from the local tunnel and removes other forwarding
headers before Django receives the request.

To stop it:

```powershell
& .\backend\scripts\stop_demo_backend.ps1
```

To restart after stopping, run the start command again. After you know the
ngrok hostname, pass it explicitly to the start command:

```powershell
& .\backend\scripts\start_demo_backend.ps1 -NgrokHost 'province-veal-eleven.ngrok-free.dev'
```

Use the hostname **without** `https://`. The script adds only that hostname to
Django's allowed hosts and trusted origins. It does not change local development
settings. The process must be restarted if the ngrok hostname changes.

Before any tunnel, verify `http://127.0.0.1:8000/api/v1/health` returns
`{"status":"ok"}`, a nonexistent route has no debug page, `/media/<a real
manuscript path>` returns 404, and unauthenticated
`/api/v1/theses/<id>/download/` returns 401. Django admin CSS should load from
`/static/admin/css/base.css`. Do not use the development `runserver` with ngrok.

## ngrok endpoint

Install the Windows ngrok agent using the [official Windows instructions](https://ngrok.com/download/windows).
Authenticate it privately in your own terminal:

```powershell
ngrok config add-authtoken <YOUR_AUTHTOKEN>
```

Do not paste the authtoken into chat or put it in a project file. Once the
secure local checks pass, start one endpoint to port 8000 from the repository
root:

```powershell
& .\backend\scripts\start_demo_ngrok.ps1
```

The script repeats the local safety checks, starts ngrok in the background,
and records its launcher PID, logs, and assigned HTTPS URL under
`backend/.demo-run/`. The agent must stay running; there is no startup service
in this setup. Obtain the assigned HTTPS URL from the script output or ngrok's
`http://127.0.0.1:4040/api/tunnels` API. If the account reports
`ERR_NGROK_15013`, reserve its free dev domain in the ngrok dashboard and
start with `ngrok http 8000 --url=https://<assigned-domain>`.

The URL assigned for this rehearsal is
`https://province-veal-eleven.ngrok-free.dev`. It may change if the tunnel is
recreated. To stop the agent safely, run:

```powershell
& .\backend\scripts\stop_demo_ngrok.ps1
```

Restart the backend with `-NgrokHost` set to that assigned hostname, then test
`<public URL>/api/v1/health`. A successful tunnel must return THESYSplus JSON,
not an ngrok warning or error page. Do not expose ports 5432, 4040, or a file
server. Do not add a Traffic Policy or warning-bypass header without approval.

At this rehearsal URL, a direct browser visit displays ngrok's free-tier
"Visit Site" warning. With the operator's approval, the Vercel frontend sends
`ngrok-skip-browser-warning: true` on API requests through its rewrite. The
warning remains on direct visits to the ngrok hostname. A paid ngrok account
is another way to remove it.

Monitor the tunnel through [ngrok's dashboard](https://dashboard.ngrok.com/)
or its local inspection interface at `http://127.0.0.1:4040` on this computer.
The local inspection interface must never be tunneled.

## Vercel integration

The existing browser client reads `VITE_API_BASE_URL`. In the Vercel project,
set it to `/api/v1` for the environment serving
`https://thesysplus.vercel.app`, then redeploy. Add this external rewrite in the
Vercel project's configured root directory, replacing the destination with
the verified ngrok HTTPS URL:

```json
{
  "rewrites": [
    {
      "source": "/api/v1/:path*/",
      "destination": "https://province-veal-eleven.ngrok-free.dev/api/v1/:path*/"
    },
    {
      "source": "/api/v1/:path*",
      "destination": "https://province-veal-eleven.ngrok-free.dev/api/v1/:path*"
    },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

The second rule allows React routes such as `/login` to load after a browser
refresh. The browser then calls `/api/v1` on the Vercel origin, which matters because
THESYSplus refreshes its in-memory access token using an HttpOnly,
`SameSite=Lax` cookie. Direct browser calls to an unrelated ngrok origin do
not reliably carry that cookie. This project's confirmed Vercel root is
`frontend`, so the rewrite is in `frontend/vercel.json`. The production
environment variable and deployment were changed with the operator's approval.

## Rehearsal and backup

Before the defense, back up both the PostgreSQL database and `backend/media`
to a location outside the project, and verify that a representative manuscript
still previews after a restart. Rehearse from the real Vercel origin with
approved test accounts: login, page refresh, logout, search, upload of a
disposable machine-readable PDF, indexing, preview/download, and denial of
unauthorized access. Test an OCR document separately because scanned PDFs can
hold a Waitress thread for a long time. Do not overwrite existing manuscripts.

The first semantic-search request in a fresh process may load the cached model;
keep that cache available. Files under `backend/media` persist across restarts,
and embeddings are stored in PostgreSQL. Gmail SMTP can send email from the
local host; confirm receipt of a test message and that links use the Vercel
origin. If ngrok returns an upstream error, recheck the local health route and
the process bound to port 8000 before changing tunnel settings.
