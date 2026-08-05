# THESYS+

An AI-Assisted Semantic-Based Thesis Retrieval and Topic Trend Analysis System — capstone project for Pampanga State University, College of Computing Studies.

This repository contains the **Authentication Module** (the first module of THESYS+). Subsequent modules — Semantic Search, Thesis Upload, Title Similarity, Topic Trend Analysis, Repository, Analytics, Researcher Directory, Saved Collections, and Settings — are out of scope here and will live in their own specs.

## Repository Layout

```
multipleacts/
├── backend/    # Django REST Framework + PostgreSQL (Auth_Service)
├── frontend/   # React + Vite + Tailwind CSS (Auth_UI)
└── .kiro/      # Spec, requirements, design, and tasks
```

## Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer (npm 9+)
- PostgreSQL 14 or newer (16 supported)
- Git

## Quick Start

### Database (optional Docker)

If you do not have PostgreSQL 14+ installed locally, you can run it via Docker:

```bash
docker compose up -d postgres
```

This brings up `postgres:16-alpine` on `localhost:5432` with the credentials from `backend/.env.example` (`thesys` / `thesys` / `thesys`). Tear down with `docker compose down -v` to also remove the named volume `thesys-postgres-data`.

Contributors who already have a local PostgreSQL on port `5432` can skip this — point `DATABASE_URL` (or the discrete `POSTGRES_*` vars) at the existing instance instead.

### Backend (Django)

1. Create the database (one-time setup, requires PostgreSQL 14+ running locally):

   ```sql
   CREATE ROLE thesys WITH LOGIN PASSWORD 'thesys' CREATEDB;
   CREATE DATABASE thesys OWNER thesys ENCODING 'UTF8';
   ```

   (or use `docker compose up -d postgres` from the previous section).

2. Set up the Python virtual environment and install dependencies:

   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Copy `backend/.env.example` to `backend/.env` and replace `DJANGO_SECRET_KEY` with a freshly generated value:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

4. Apply Django contrib migrations and boot the dev server:

   ```powershell
   .venv\Scripts\python.exe manage.py migrate
   .venv\Scripts\python.exe manage.py runserver
   ```

5. Verify in another terminal:

   ```powershell
   curl http://localhost:8000/api/v1/health
   # → {"status": "ok"}
   ```

### Frontend (React + Vite)

1. Install dependencies:
   ```powershell
   cd frontend
   npm install
   ```

2. Copy `frontend/.env.example` to `frontend/.env` (the default `VITE_API_BASE_URL` points at `http://localhost:8000/api/v1`).

3. Start the dev server:
   ```powershell
   npm run dev
   ```

4. Open `http://localhost:5173/` — you should see "Landing placeholder" with a 🌙 theme toggle in the top-right corner. Click it to switch to dark mode (navy background). The preference persists across page reloads via `localStorage`.

> **Note:** The backend should be running (`manage.py runserver`) so the axios client's `baseURL` resolves, though no API requests are issued in the Foundation Phase.

## Status

Foundation Phase in progress. See `.kiro/specs/thesys-authentication/tasks.md` for the live task list.
