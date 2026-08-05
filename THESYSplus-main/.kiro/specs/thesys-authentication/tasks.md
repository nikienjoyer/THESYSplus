# Implementation Plan: THESYS+ Authentication Module — Foundation + Authentication Phases

## Overview

✅ **Foundation Phase COMPLETE — verified locally on 2026-05-19.** Backend boots (`manage.py runserver` against PostgreSQL 16, `/api/v1/health` → 200 `{"status": "ok"}`), frontend boots (Vite dev server at `localhost:5173`, placeholder Landing route renders, `ThemeToggle` flips and persists across reloads), all five empty Django apps are registered, the `common/` package + `common/tokens/` subpackage carry stub modules with docstrings, and the frontend folder layout in design §2.3 is in place.

This task list now spans two phases:

1. **Foundation Phase** (Tasks 1–17, **complete**) — project skeleton, build tooling, environment wiring, and folder structure per design §2.2, §2.3, §2.4. No business logic.
2. **Authentication Phase** (Tasks 18–45, **new**) — fills in real behavior for `Auth_Service` end-to-end per `requirements.md` and `design.md` §3–§9. NO architectural changes — every model, endpoint, validator, and helper is already specified in the design. The phase is split into 14 waves (A1–A14) — each wave is a parent "wave task" followed by a checkpoint task, alternating across tasks 18–45 so each wave produces a verifiable, testable deliverable. The Foundation Phase scaffolds remain unchanged: the Authentication Phase fills in real behavior into the apps, `common/` modules, and frontend contexts that already exist.

### Out of Scope (Both Phases)

The following are **explicitly excluded** from both the Foundation Phase and the Authentication Phase, because they belong to downstream modules of THESYS+:

- Semantic Search, Thesis Upload, AI/NLP pipelines, Repository browsing, Title Similarity, Topic Trend Analysis, Researcher Directory, Saved Collections, Analytics dashboards
- Application Settings beyond authentication-related theme persistence
- Real SSO integration with a SAML or OAuth identity provider (only a 501 stub is in scope)
- Authenticated password change while signed in (deferred to the future Settings module per Requirement 25)
- Email infrastructure provisioning beyond what is required to send password reset, account activation, and access-request notifications

The Foundation Phase additionally deferred (and the Authentication Phase now introduces) the following items previously listed as "out of scope for the foundation":

- User / RefreshToken / PasswordResetToken / AccessRequest / AuditLog model definitions and migrations → introduced in **Wave A1**
- `login` / `logout` / `refresh` / `me` / `forgot-password` / `reset-password` / `request-access` / `sso` / admin endpoints, serializers, and views → introduced in **Waves A3–A5**
- JWT issuance, opaque token generation, password hashing wiring → introduced in **Waves A1 and A2**
- Refresh-cookie set/clear behavior → introduced in **Wave A2**
- Rate limiting logic → introduced in **Waves A2 and A7**
- CSRF / Origin enforcement logic → introduced in **Wave A2**
- Audit logger writes → introduced in **Waves A2 and A6**
- Email backend implementations → introduced in **Wave A2**
- Real `SignInCard`, `RequestAccessForm`, `ForgotPasswordForm`, `ResetPasswordForm`, `SsoButton`, `Hero`, `SearchBar`, `CtaButtons`, `StatsCards`, `Footer`, `Header` components — auth-form components introduced in **Waves A10–A12**; landing-section components remain out of scope for this spec
- Permission registry, `ProtectedRoute` / `RoleRoute` route guards → introduced in **Wave A13**
- `useAuth`, `useIdleTimeout` hooks → introduced in **Waves A9 and A13**
- PostgreSQL `citext` / `pgcrypto` extension migrations (Requirement 26) → introduced in **Wave A1**

### Property-Based Testing Note

The Foundation Phase introduced no business logic, so there were no correctness properties to encode yet — that decision was correct. PBT setup (`hypothesis` on the backend, `fast-check` on the frontend) is **actively introduced in Wave A2** for the four pure validators / token helpers (institutional-email matcher, password strength, opaque-token entropy + idempotent sha256, JWT round-trip) and **expanded in Wave A8** to cover the refresh-token state machine, password-salt uniqueness, and refresh-family invariants. Frontend PBT is added in **Wave A14** (institutional-email validator parity + axios single-flight refresh). Each property test references a specific property in design §13 and the requirement clause(s) it validates.

## Tasks

- [x] 1. Repository scaffold
  - [x] 1.1 Initialize repository layout, root README, and .gitignore
    - Create the top-level repo layout: `backend/` and `frontend/` sibling directories.
    - Create the root `README.md` documenting prerequisites (Python 3.11+, Node 18+, PostgreSQL 14+) and the run-instructions skeleton for both halves (filled in by later tasks).
    - Add a root `.gitignore` covering Python (`__pycache__/`, `.venv/`, `*.pyc`), Node (`node_modules/`, `dist/`), and env files (`.env`).
    - _Requirements: 25 (folder structure), Architecture & Scope Reference_

- [x] 2. Backend project bootstrap
  - [x] 2.1 Create `backend/requirements.txt` with foundation dependencies
    - List exact pinned versions for: `Django`, `djangorestframework`, `django-cors-headers`, `psycopg[binary]`, `django-environ`, `argon2-cffi` (listed for later phase, not yet wired).
    - Do NOT add `hypothesis` or any property-testing libraries in this phase.
    - _Requirements: 26 (Postgres connection wiring), Architecture & Scope Reference_

  - [x] 2.2 Initialize the Django project `thesys/` and `manage.py`
    - Run `django-admin startproject thesys backend` (or equivalent) so the layout is `backend/manage.py` + `backend/thesys/{__init__.py,asgi.py,wsgi.py,urls.py}` per design §2.2.
    - Verify `manage.py check` exits 0 against the unsplit settings before proceeding.
    - _Requirements: 25 (folder structure)_

  - [x] 2.3 Split settings into `base.py` / `dev.py` / `prod.py`
    - Replace the generated `thesys/settings.py` with a `thesys/settings/` package: `__init__.py`, `base.py`, `dev.py`, `prod.py`.
    - Use `django-environ` (or `os.environ`) to read all environment-driven values.
    - `__init__.py` selects between `dev` and `prod` based on `DJANGO_ENV` (default `development`).
    - `base.py` defines `INSTALLED_APPS`, `MIDDLEWARE`, `TEMPLATES`, `DATABASES` (driven by env), `SECRET_KEY` (from env), and `ROOT_URLCONF`.
    - _Requirements: 26 (environment configuration)_

  - [x] 2.4 Wire PostgreSQL via env vars
    - In `thesys/settings/base.py`, configure `DATABASES['default']` from `DATABASE_URL` (preferred) with discrete `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` as a fallback.
    - Do NOT enable `citext` or `pgcrypto` extensions, and do NOT create or run any custom migrations in this phase. Only Django's contrib `auth` / `admin` / `sessions` / `contenttypes` migrations needed for the server to boot are allowed.
    - Verify `python manage.py migrate` succeeds against a real Postgres instance (only Django contrib migrations apply).
    - _Requirements: 26 (Postgres connection wiring; explicitly NOT the citext extension migration yet)_

  - [x] 2.5 Add minimal DRF configuration
    - Add `rest_framework` to `INSTALLED_APPS`.
    - Add a minimal `REST_FRAMEWORK` dict in `base.py` with: default JSON renderer, default JSON parser, `DEFAULT_AUTHENTICATION_CLASSES = []` (intentionally empty for the foundation phase), and pagination defaults (`PageNumberPagination`, `PAGE_SIZE = 20`).
    - _Requirements: Architecture & Scope Reference_

  - [x] 2.6 Add CORS via `django-cors-headers`
    - Add `corsheaders` to `INSTALLED_APPS` and `corsheaders.middleware.CorsMiddleware` to `MIDDLEWARE` (above `CommonMiddleware`).
    - Drive `CORS_ALLOWED_ORIGINS` from a `FRONTEND_ORIGIN` env var (default `http://localhost:5173` in dev).
    - Set `CORS_ALLOW_CREDENTIALS = True` so future cookie-bearing requests will work.
    - _Requirements: 26 (environment configuration), Architecture & Scope Reference_

- [x] 3. Backend app skeleton (empty packages only)
  - [x] 3.1 Create the five empty Django apps
    - Create `backend/accounts/`, `backend/auth_service/`, `backend/access_requests/`, `backend/password_reset/`, `backend/audit/`.
    - Each app contains ONLY: `__init__.py`, `apps.py` (with the correct `AppConfig` and `default_auto_field = 'django.db.models.BigAutoField'`), and `migrations/__init__.py`.
    - Do NOT create `models.py`, `views.py`, `serializers.py`, `admin.py`, `tests.py`, or any service modules in this phase.
    - Register all five apps in `INSTALLED_APPS` so the project boots.
    - _Requirements: 25 (folder structure)_

  - [x] 3.2 Create empty per-app URL placeholders
    - For each of the five apps, create `urls.py` containing only `urlpatterns = []`.
    - These placeholders exist so the root URLConf can `include()` them without crashing.
    - _Requirements: 25 (folder structure)_

- [x] 4. Backend `common/` package skeleton
  - [x] 4.1 Create the `common/` package and stub leaf modules
    - Create `backend/common/__init__.py`.
    - Create `backend/common/ratelimit.py`, `email_backend.py`, `audit_logger.py`, `validators.py`, `errors.py`, `csrf.py`.
    - Each file contains ONLY a module docstring describing its future responsibility (per design §2.4) and a `# TODO` placeholder. NO business logic.
    - _Requirements: 25 (folder structure)_

  - [x] 4.2 Create the `common/tokens/` subpackage stubs
    - Create `backend/common/tokens/__init__.py`.
    - Create `backend/common/tokens/jwt.py`, `opaque.py`, `cookies.py`.
    - Each file contains ONLY a module docstring and a `# TODO` placeholder. NO token logic.
    - _Requirements: 25 (folder structure)_

- [x] 5. Root URLConf and health endpoint
  - [x] 5.1 Wire `/api/v1/` prefix in `thesys/urls.py`
    - The root URLConf includes each app's empty `urls.py` under `path('api/v1/...', include('<app>.urls'))` so the routing tree exists end-to-end.
    - Mount `/api/v1/auth/` for `auth_service.urls`, `/api/v1/auth/` for `password_reset.urls`, `/api/v1/access-requests/` for `access_requests.urls`, `/api/v1/admin/` for `audit.urls` and admin views (placeholder includes only).
    - _Requirements: 25 (folder structure), Architecture & Scope Reference_

  - [x] 5.2 Implement `GET /api/v1/health` endpoint
    - In `thesys/urls.py` (or a tiny `thesys/health.py` module imported from there), define a single function-based view returning `JsonResponse({"status": "ok"})` with HTTP 200.
    - This is a foundation health check, NOT an auth endpoint — it has no rate limiting, no CSRF requirement, and no auth class. It exists so the next task can verify the server boots end-to-end against a real Postgres connection.
    - _Requirements: Architecture & Scope Reference, Foundational — no direct EARS criterion_

- [x] 6. Backend environment file and runtime verification
  - [x] 6.1 Create `backend/.env.example`
    - Document every env var the foundation phase reads: `DJANGO_ENV`, `DJANGO_SECRET_KEY`, `DATABASE_URL` (with discrete `POSTGRES_*` fallback), `FRONTEND_ORIGIN`. Include placeholder values and a comment indicating production-only vars (`JWT_SECRET`, `EMAIL_BACKEND`, etc.) will be added in later phases.
    - _Requirements: 26 (environment configuration)_

  - [x] 6.2 Verify end-to-end backend boot
    - Confirm `python manage.py runserver` starts against a real Postgres connection sourced from `.env`.
    - Confirm `curl http://localhost:8000/api/v1/health` returns `{"status": "ok"}` with HTTP 200.
    - Update the root `README.md` with the exact backend run instructions.
    - _Requirements: 26 (environment configuration)_

- [x] 7. Optional Postgres docker-compose
  - [x] 7.1 Add `docker-compose.yml` for Postgres only (optional)*
    - Create a top-level `docker-compose.yml` defining a single `postgres:14-alpine` (or 15) service with a named volume, env-driven `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`, and port `5432:5432`.
    - The compose file does NOT define an app service — only Postgres.
    - Document `docker compose up -d postgres` in the root `README.md`.
    - _Requirements: 26 (environment configuration), Architecture & Scope Reference_

- [x] 8. Backend foundation checkpoint
  - Ensure `manage.py check` passes, `manage.py migrate` applies Django contrib migrations cleanly against a fresh database, `runserver` boots, and `/api/v1/health` responds. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 25, 26, Architecture & Scope Reference_

- [x] 9. Frontend project bootstrap
  - [x] 9.1 Scaffold React + Vite (JavaScript) under `frontend/`
    - Run `npm create vite@latest frontend -- --template react` (JavaScript, NOT TypeScript, per design §1.2).
    - After scaffolding, run `npm install` and verify the default Vite app boots before further customization.
    - _Requirements: 25 (folder structure)_

  - [x] 9.2 Install and configure Tailwind CSS
    - Install `tailwindcss`, `postcss`, `autoprefixer`. Run `npx tailwindcss init -p` to generate `tailwind.config.js` and `postcss.config.js`.
    - Set `darkMode: 'class'` in `tailwind.config.js` (per design §11.4).
    - Configure `content` to include `./index.html` and `./src/**/*.{js,jsx}`.
    - Add the Tailwind directives (`@tailwind base; @tailwind components; @tailwind utilities;`) to `src/index.css` and import it from `main.jsx`.
    - _Requirements: 14 (theme system foundation), 16 (responsive layout — Tailwind config supports it)_

  - [x] 9.3 Add a placeholder palette/theme tokens file with real values
    - Create `frontend/src/styles/tokens.css` defining real CSS custom properties on `:root` (light mode) and on `.dark` (dark mode), AND additionally export the same values as a JS object from `frontend/src/styles/tokens.js` so Tailwind's `tailwind.config.js` (`theme.extend.colors`) can consume them. Both files MUST stay in sync.
    - Light mode placeholder values (real, consumable values — NOT comments):
      - `--color-background: #ffffff;` (white)
      - `--color-primary: #2563eb;` (blue — Tailwind blue-600 — flagged as placeholder pending Figma palette)
    - Dark mode placeholder values (real, consumable values — NOT comments):
      - `--color-background: #0b1437;` (navy — flagged as placeholder pending Figma palette)
      - `--color-accent: #7c3aed;` (purple — Tailwind violet-600 — flagged as placeholder pending Figma palette)
    - Each token MUST carry an inline comment in both `tokens.css` and `tokens.js` flagging it as `PLACEHOLDER pending Figma palette` so later phases know to replace the values without restructuring the token plumbing.
    - Wire `tokens.css` into `src/index.css` (via `@import './styles/tokens.css';`) so the custom properties are present at runtime, AND wire the JS export into `tailwind.config.js` under `theme.extend.colors` (e.g., `background: 'var(--color-background)'`, `primary: 'var(--color-primary)'`, `accent: 'var(--color-accent)'`) so Tailwind utility classes (e.g., `bg-background`, `text-primary`, `bg-accent`) resolve to the placeholder values.
    - The placeholder Landing route (Task 15.1) MUST therefore render with a recognizable light/dark palette on first run, and the dark mode toggle (Task 12.2) MUST visibly swap the background between white and navy.
    - Downstream phases SHALL only need to swap the four hex values (and add any additional tokens) without restructuring the file layout, the import wiring, or the Tailwind config keys.
    - _Requirements: 14 (theme palette placeholder), 15 (dark mode palette placeholder)_

  - [x] 9.4 Configure ESLint + Prettier (minimal)
    - Add `eslint`, `eslint-config-prettier`, `prettier`, and the React ESLint plugin generated by Vite.
    - Add `npm run lint` and `npm run format` scripts to `package.json`.
    - Commit a minimal `.eslintrc.cjs` and `.prettierrc` so future contributors get consistent formatting; no custom rules beyond the Vite-React defaults plus Prettier compatibility.
    - _Requirements: Architecture & Scope Reference, Foundational — no direct EARS criterion_

- [x] 10. Frontend folder skeleton
  - [x] 10.1 Create the full empty folder layout from design §2.3
    - Create directories: `src/api/`, `src/assets/`, `src/components/auth/`, `src/components/landing/`, `src/components/layout/`, `src/components/ui/`, `src/context/`, `src/hooks/`, `src/pages/`, `src/routes/`, `src/styles/`, `src/utils/`.
    - For directories that will not yet contain real files (e.g., `assets/`, `hooks/`, `routes/`, `utils/`, `pages/`), add a `.gitkeep` so the folder exists in git.
    - For directories that will get an index/barrel pattern (e.g., `components/auth/`, `components/landing/`), add an `index.js` that exports nothing yet (`export {};`) so future phases extend the barrel rather than create it.
    - Do NOT create `useAuth.js` or `useIdleTimeout.js` in `hooks/`. Do NOT create `ProtectedRoute.jsx` or `RoleRoute.jsx` in `routes/`. Do NOT create real form components under `components/auth/` or landing components under `components/landing/`.
    - _Requirements: 25 (folder structure)_

- [x] 11. Frontend API client skeleton
  - [x] 11.1 Create `src/api/client.js` axios instance
    - Install `axios`.
    - Create `src/api/client.js` exporting a single axios instance configured with `baseURL: import.meta.env.VITE_API_BASE_URL`, `withCredentials: true`, and `headers: { 'Content-Type': 'application/json' }`.
    - Add empty interceptor scaffolding (`client.interceptors.request.use(...)`, `client.interceptors.response.use(...)`) where each interceptor is a pass-through with a `// TODO` comment indicating that refresh-token retry logic will be added in a later phase. NO refresh logic in this phase.
    - _Requirements: 25 (folder structure), 26 (environment configuration)_

  - [x] 11.2 Create `src/api/index.js` barrel
    - Re-export the axios `client` from `src/api/client.js` so callers can import from `src/api`.
    - _Requirements: 25 (folder structure)_

- [x] 12. Frontend theme system (foundation)
  - [x] 12.1 Implement `ThemeContext` and `useTheme`
    - Create `src/context/ThemeContext.jsx` exporting a `ThemeProvider` component and a `useTheme()` hook.
    - Internal state: `theme: 'light' | 'dark'`. Default is `'light'` (per requirement 14.1) UNLESS `localStorage.getItem('thesys.theme')` is set, in which case use the stored value.
    - The provider toggles the `dark` class on `document.documentElement` whenever `theme` changes (per design §11.4).
    - Persist every change to `localStorage` under the key `thesys.theme` (per requirement 16.2).
    - Wrap `<App />` in `<ThemeProvider>` inside `main.jsx`.
    - _Requirements: 14 (theme system), 15 (light default, dark toggle), 16.2 (localStorage persistence)_

  - [x] 12.2 Implement `ThemeToggle` component
    - Create `src/components/layout/ThemeToggle.jsx`.
    - Render a single button that calls `useTheme().toggleTheme()` on click and shows a sun/moon affordance based on the current theme. Tailwind classes only; no external icon library required (a simple unicode glyph or inline SVG is fine).
    - Apply `aria-label="Toggle theme"` and a visible `focus-visible` ring so it is keyboard-accessible.
    - _Requirements: 14 (theme toggle), 15 (dark mode toggle), 16 (responsive layout — the button must work at all breakpoints)_

- [x] 13. Frontend UI primitive shells
  - [x] 13.1 Create minimal styled wrappers under `src/components/ui/`
    - Create `Button.jsx`, `Input.jsx`, `Checkbox.jsx`, `Alert.jsx`, `Spinner.jsx`.
    - Each component is a thin Tailwind-styled wrapper around the corresponding native element (`<button>`, `<input>`, `<input type="checkbox">`, `<div role="alert">`, an SVG/CSS spinner) with `...props` forwarded to the underlying element and a `className` merge that respects callers' overrides.
    - NO domain logic, NO form-state hooks, NO validation. These are pure presentational shells.
    - Add a barrel `src/components/ui/index.js` re-exporting all five.
    - _Requirements: 25 (folder structure), 16 (responsive layout — primitives use Tailwind utility classes that respect breakpoints)_

- [x] 14. Frontend AuthContext shell (structural only)
  - [x] 14.1 Create empty `AuthContext` shell
    - Create `src/context/AuthContext.jsx` exporting an `AuthProvider` and a `useAuthContext()` hook.
    - The context value is a static placeholder object: `{ isAuthenticated: false, user: null, accessToken: null }`. NO `signIn`, `signOut`, `refresh`, or `loadMe` functions in this phase.
    - Wrap `<App />` in `<AuthProvider>` (inside `<ThemeProvider>`) in `main.jsx` so downstream phases can fill in real state without re-plumbing.
    - Do NOT create `src/hooks/useAuth.js` in this phase.
    - _Requirements: 25 (folder structure)_

- [x] 15. Frontend routing with placeholder pages
  - [x] 15.1 Install React Router v6, create `MainLayout`, and set up nested routes in `App.jsx`
    - Install `react-router-dom@6`.
    - Create `src/components/layout/MainLayout.jsx` as a structural wrapper component. It MUST render a top-of-page header slot containing the `<ThemeToggle />` and an `<Outlet />` for nested route children. NO real header content, NO real navigation, NO sidebar — only the slot positions so future phases can fill them in without restructuring the route tree. Import `Outlet` from `react-router-dom`.
    - In `src/App.jsx`, render `<BrowserRouter>` (or use `RouterProvider` with `createBrowserRouter`) and define the routes using React Router v6's nested-route pattern: a parent `<Route element={<MainLayout />}>` whose children are the five routes `/`, `/sign-in`, `/request-access`, `/forgot-password`, `/reset-password` (or the `createBrowserRouter` equivalent with `children: [...]`).
    - Each child route MUST still render a one-line inline placeholder component (e.g., `<div className="p-8">Landing placeholder</div>`, `<div className="p-8">Sign In placeholder</div>`, etc.). Do NOT create real `LandingPage`, `SignInPage`, etc. — those land in the auth-UI phase.
    - The `<ThemeToggle />` MUST be rendered inside `MainLayout` (NOT in `App.jsx`) so the requirement "render the `<ThemeToggle />` in a top-of-page header slot on every route" is satisfied via the shared layout. `App.jsx` MUST NOT render `<ThemeToggle />` directly.
    - This shell is introduced now so that when real navigation/header/sidebar lands in a later phase, those elements are added inside `MainLayout` without restructuring the route tree or touching every page.
    - _Requirements: 12 (Landing page surface — placeholder route only), 25 (folder structure)_

- [x] 16. Frontend environment file and runtime verification
  - [x] 16.1 Create `frontend/.env.example`
    - Document `VITE_API_BASE_URL=http://localhost:8000/api/v1` with a comment explaining it must include the `/api/v1` prefix used by the backend root URLConf.
    - _Requirements: 26 (environment configuration)_

  - [x] 16.2 Verify end-to-end frontend boot
    - Confirm `npm run dev` starts the Vite dev server.
    - Confirm the placeholder Landing route renders at `http://localhost:5173/` and the `ThemeToggle` flips between light and dark, persisting across reload.
    - Update the root `README.md` with the exact frontend run instructions and a note that the backend should be running so the axios client's `baseURL` resolves (no requests are issued yet).
    - _Requirements: 14 (theme), 15 (light default + persistence), 16.2 (localStorage persistence)_

- [x] 17. Final foundation checkpoint
  - Ensure `manage.py check` and `manage.py migrate` succeed, `runserver` returns 200 on `/api/v1/health`, `npm run dev` boots, the placeholder Landing renders, and the theme toggle flips and persists across reloads. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 14, 15, 16.2, 25, 26_

## Authentication Phase

This phase implements the Auth_Service end-to-end per `requirements.md` and
`design.md` §3–§9. It does NOT introduce architectural changes — every model,
endpoint, validator, and helper is already specified in the design. The phase
is split into 14 waves so each wave produces a verifiable, testable deliverable.

The Foundation Phase scaffolds (above) remain unchanged: the Authentication
Phase fills in real behavior into the apps, `common/` modules, and frontend
contexts that already exist.


- [ ] 18. Wave A1 — Database models, migrations, and User manager
  - [ ] 18.1 Enable PostgreSQL `citext` and `pgcrypto` extensions
    - In `accounts/migrations/0001_initial.py`, add a `RunSQL` operation that runs `CREATE EXTENSION IF NOT EXISTS citext;` and `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (with corresponding reverse SQL for safe rollback).
    - This migration MUST run before any other app's `0001_initial` so `users.email` (citext) and UUID `gen_random_uuid()` defaults work everywhere.
    - _Requirements: 26._

  - [ ] 18.2 Implement the `User` model and custom `UserManager`
    - In `accounts/models.py`, define `User(AbstractBaseUser, PermissionsMixin)`: UUID PK with `default=uuid.uuid4`, `email` as `CICharField` / `CITextField` (django.contrib.postgres) UNIQUE, normalized to lowercase on save, `password_hash` nullable, `first_name` (varchar 80), `last_name` (varchar 80), `role` (varchar 16, lowercase TextChoices, default `student`), `is_active` (default True), `is_email_verified` (default False), `created_at`, `updated_at`, `last_login_at` nullable. Add a CHECK constraint enforcing `role IN ('student', 'faculty', 'administrator')` and an index on `role`.
    - Implement `UserManager(BaseUserManager)` with `create_user(email, first_name, last_name, role, password=None)` (password=None permitted for admin-provisioned accounts per Requirement 5.7) and `create_superuser`.
    - Set `AUTH_USER_MODEL = 'accounts.User'` in `thesys/settings/base.py`.
    - _Requirements: 1.5, 3.1, 3.6, 3.7, 5.7, 8.1, 26._

  - [ ] 18.3 Implement the `Role` enum
    - In `accounts/models.py`, define `class Role(models.TextChoices): STUDENT = "student", "Student"; FACULTY = "faculty", "Faculty"; ADMINISTRATOR = "administrator", "Administrator"`.
    - Expose `Role.ALLOWED_FOR_REQUEST = (Role.STUDENT, Role.FACULTY)` as a class attribute for use in the `access_requests` serializer (Requirement 7.8).
    - Decision per design §3.2: NO separate `roles` table — CHECK constraint enum only.
    - _Requirements: 3.1, 3.7, 7.8._

  - [ ] 18.4 Configure password hashers and wire `accounts.services`
    - In `thesys/settings/base.py`, set `PASSWORD_HASHERS = ['django.contrib.auth.hashers.Argon2PasswordHasher', 'django.contrib.auth.hashers.PBKDF2PasswordHasher', 'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher', 'django.contrib.auth.hashers.BCryptSHA256PasswordHasher', 'django.contrib.auth.hashers.ScryptPasswordHasher']` (Argon2 first, PBKDF2-SHA256 second, plus standard fallbacks).
    - Create `accounts/services.py` exposing `set_password(user, plaintext)` (hashes via Argon2id and persists into `password_hash`) and `verify_password(user, plaintext)` returning `(ok, needs_rehash)`. Use `django.contrib.auth.hashers.check_password` + `is_password_usable` and `make_password`.
    - _Requirements: 8.1, 8.2, 8.3._

  - [ ] 18.5 Implement the `RefreshToken` model
    - In `auth_service/models.py`: UUID PK, `user_id` FK CASCADE, `token_hash` (CHAR(64) unique), `family_id` UUID, `parent_id` self-FK nullable, `remember_me` bool, `expires_at`, `revoked_at` nullable, `revoked_reason` (varchar 40, CHECK IN `rotated|logout|reuse_detected|password_reset|admin_revoke`), `created_at`, `user_agent` (varchar 255 nullable), `ip_address` (`GenericIPAddressField` mapped to INET).
    - Indexes: UNIQUE on `token_hash`, partial index `(user_id) WHERE revoked_at IS NULL`, index on `family_id`.
    - _Requirements: 2.8, 2.9, 4.4, 9.6, 9.8._

  - [ ] 18.6 Implement the `PasswordResetToken` model
    - In `password_reset/models.py`: UUID PK, `user_id` FK CASCADE, `token_hash` (CHAR(64) unique), `expires_at`, `used_at` nullable, `created_at`. Index on `user_id`.
    - _Requirements: 5.2, 5.3, 5.4._

  - [ ] 18.7 Implement the `AccessRequest` model
    - In `access_requests/models.py`: UUID PK, `email` (CITextField), `first_name`, `last_name`, `requested_role` (varchar 16, CHECK IN student/faculty), `justification` (text), `status` (varchar 16, CHECK IN pending/approved/denied, default pending), `review_note` text nullable, `reviewed_by` FK SET NULL nullable to `User`, `reviewed_at` nullable, `created_at`.
    - Indexes: partial UNIQUE on `(email) WHERE status = 'pending'` (enforces Requirement 7.4 at the DB level), composite index on `(status, created_at DESC)`.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.8._

  - [ ] 18.8 Implement the `AuditLog` model
    - In `audit/models.py`: BigAutoField PK, `actor_user_id` FK SET NULL nullable, `event_type` (varchar 64), `target_user_id` FK SET NULL nullable, `ip_address` (GenericIPAddressField/INET nullable), `user_agent` (varchar 255 nullable), `success` bool, `metadata` JSONField default empty dict, `created_at`.
    - Indexes: `(created_at DESC)`, `(event_type)`, `(actor_user_id)`, `(target_user_id)`.
    - _Requirements: 11.1, 11.2._

  - [ ] 18.9 Run migrations and bootstrap admin
    - Run `python manage.py makemigrations accounts auth_service password_reset access_requests audit` then `migrate` against the local Postgres `thesys` database; verify the citext/pgcrypto extensions are created and all five tables exist with the correct constraints (CHECK constraints, partial UNIQUE on access_requests, partial active index on refresh_tokens).
    - Add basic Django admin registration for `User` (read-only role display) so Administrators can be bootstrapped via `python manage.py createsuperuser`.
    - _Requirements: 25, 26._

- [ ] 19. Wave A1 checkpoint — migrations and models verified
  - Ensure `manage.py makemigrations --check`, `manage.py migrate`, and `manage.py check` all pass; verify all FK constraints, CHECK constraints, and partial indexes exist in Postgres (`\d+ users`, `\d+ refresh_tokens`, `\d+ access_requests`, `\d+ password_reset_tokens`, `\d+ audit_log`). Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 25, 26, 1.5, 2.8, 3.1, 5.2, 7.4, 11.1._

- [ ] 20. Wave A2 — `common/` utilities
  - [ ] 20.1 Implement `common/validators.py`
    - Replace the docstring + TODO with: `is_institutional_email(s: str) -> bool` — case-insensitive match against `pampangastateu.edu.ph` apex AND any subdomain (`*.pampangastateu.edu.ph`) using the regex `^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)*pampangastateu\.edu\.ph$` per design §11.5.
    - `validate_password_strength(s: str) -> None` — raises a structured `ValidationError` with code `WEAK_PASSWORD` when the input is shorter than 12 chars OR has zero letters OR has zero digits.
    - Expose error code constants `INVALID_EMAIL_DOMAIN` and `WEAK_PASSWORD`.
    - _Requirements: 1.2, 1.4, 5.5._

  - [ ] 20.2 Implement `common/tokens/jwt.py`
    - `issue_access_token(user) -> str` returns an HS256 JWT with claims `iss="thesys-auth"`, `sub=str(user.id)`, `role=user.role`, `iat`, `exp` (now + 15min), `jti=uuid4()`, plus a JOSE header `kid` from settings. Use `pyjwt`.
    - `verify_access_token(token: str) -> dict` validates signature, `exp`, presence of `jti` and `role`, and returns the decoded payload. Raises `AccessTokenExpired` on `ExpiredSignatureError`.
    - Settings additions: `JWT_SECRET`, `JWT_KID` (default `kid-2025-01`), `JWT_ACCESS_TTL_SECONDS = 900`. Add `pyjwt` to `requirements.txt`.
    - _Requirements: 2.1, 2.6, 2.7, 3.2._

  - [ ] 20.3 Implement `common/tokens/opaque.py`
    - `generate_opaque_token() -> str` using `secrets.token_urlsafe(32)` (≥256 bits entropy).
    - `sha256(token: str) -> str` returning lowercase hex digest of `hashlib.sha256(token.encode()).hexdigest()`.
    - _Requirements: 2.8._

  - [ ] 20.4 Implement `common/tokens/cookies.py`
    - `set_refresh_cookie(response, token, *, remember_me)` and `clear_refresh_cookie(response)` setting `HttpOnly`, `Secure` (gated on `DJANGO_ENV != 'development'` per Requirement 27), `SameSite=Lax`, `Path=/api/v1/auth`, and `Max-Age` per remember_me (24h or 30d, in seconds) or session cookie when not remember_me. Cookie name `refresh_token`.
    - `clear_refresh_cookie` sets `Max-Age=0` with the same `Path` and attributes.
    - _Requirements: 4.2, 4.3, 4.5, 4.6, 9.1, 27.1._

  - [ ] 20.5 Implement `common/errors.py`
    - Unified envelope renderer + DRF exception handler producing `{"error": {"code", "message", "details"}}` per design §14.1. Map `serializers.ValidationError`, `NotAuthenticated`, `AuthenticationFailed`, `PermissionDenied`, custom `RefreshExpired`/`RefreshRevoked`/`RefreshReuseDetected`, `Throttled`.
    - Provide a helper `set_retry_after(response, seconds)` for 429s that sets the `Retry-After` header and `details.retry_after_seconds`.
    - Wire as `REST_FRAMEWORK['EXCEPTION_HANDLER'] = 'common.errors.unified_exception_handler'` in `base.py`.
    - _Requirements: 4.1 (design §4.1), 10.4, 14.1._

  - [ ] 20.6 Implement `common/csrf.py`
    - `@require_origin_match` decorator. Validates `Origin` (or `Referer` fallback) against `settings.CORS_ALLOWED_ORIGINS`; on mismatch returns `403 ORIGIN_NOT_ALLOWED` (mapped via the unified error envelope). On both headers absent for a state-changing request, also rejects with `403 CSRF_FAILURE` per design §5.7.
    - _Requirements: 9.4._

  - [ ] 20.7 Implement `common/ratelimit.py`
    - Cache-backed rate limiter using `django.core.cache`. Decorators `@rate_limit_per_email(limit, window_seconds, error_code)` (key derives from `request.data['email'].lower()`) and `@rate_limit_per_ip(limit, window_seconds, error_code)`.
    - On exceed, returns 429 envelope with `code=error_code`, `details.retry_after_seconds`, and `Retry-After` header. Backed by `django.core.cache.backends.locmem.LocMemCache` in dev (configurable via `RATE_LIMIT_BACKEND` env in `settings/base.py`'s `CACHES` block per design §8.1).
    - _Requirements: 10.1, 10.2, 10.3, 10.4._

  - [ ] 20.8 Implement `common/email_backend.py`
    - Pluggable `EmailBackend` Protocol with `send(to, subject, template_name, context)` per design §10.1.
    - Concrete `ConsoleEmailBackend` (default in dev, wraps `django.core.mail.backends.console.EmailBackend`) and `SMTPEmailBackend` (uses `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `EMAIL_FROM`).
    - Selected at startup via `EMAIL_BACKEND` env (`console` or `smtp`); expose `default_email_backend` factory consumed by services.
    - _Requirements: 5.2 (delivery), 24.1._

  - [ ] 20.9 Implement `common/audit_logger.py`
    - `write(event_type, *, actor=None, target=None, success, metadata=None, request=None)` writes one `AuditLog` row, deriving `ip_address` and `user_agent` from `request.META` when present. Wraps the insert in `try/except` so failures are swallowed and forwarded to `logging.getLogger("audit")` per design §9.4 — never raises into the caller.
    - _Requirements: 11.1, 11.2, 11.3, 24.2._

  - [ ] 20.10* Property tests for pure validators and token helpers
    - Add `hypothesis` to `requirements.txt`. Create `tests/property/test_common_pbt.py`.
    - **Property 9 (institutional email matcher)**: hypothesis strategy generates valid emails ending in `pampangastateu.edu.ph` (apex + multi-level subdomains) and invalid lookalikes (`pampangastateu.edu.ph.evil.tld`, `notpampangastateu.edu.ph`, etc.); assert `is_institutional_email` accepts/rejects accordingly. **Validates: Requirement 1.2.**
    - **Password strength**: hypothesis generates strings; assert `validate_password_strength` raises iff `len < 12 OR no letters OR no digits`. **Validates: Requirement 5.5.**
    - **Property 4 (opaque entropy)**: generate 100k tokens; assert all unique (collision probability < 1e-6). **Validates: Requirement 2.8.**
    - **Property 6 (sha256 idempotence)**: hypothesis text strategy; assert `sha256(s) == sha256(s)` and length is 64 lowercase hex. **Validates: Requirement 2.8.**
    - **Property 1 (JWT round-trip)**: hypothesis generates synthetic user dicts; assert `verify_access_token(issue_access_token(u))` returns claims with matching `sub`, `role`, and `exp > iat`, `exp - iat == 900`. **Validates: Requirement 2.6.**
    - _Requirements: 1.2, 2.6, 2.8, 5.5; Property 1, Property 4, Property 6, Property 9._

- [ ] 21. Wave A2 checkpoint — common utilities verified
  - Ensure all `common/` modules import without errors, the unified exception handler is wired into DRF, the rate limiter cache backend boots, and `manage.py check` passes. Run the property tests added in 20.10 (`pytest tests/property/test_common_pbt.py`). Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 1.2, 1.4, 2.6, 2.8, 5.5, 9.1, 9.4, 10.1, 10.2, 10.3, 10.4, 11.1, 24.1._

- [ ] 22. Wave A3 — Auth API (`/login`, `/refresh`, `/logout`, `/me`, SSO stub)
  - [ ] 22.1 Implement `POST /login`
    - Add `LoginSerializer` to `auth_service/serializers.py` with `email`, `password`, `remember_me` (optional, default False); rejects unknown fields per Requirement 18.2.
    - Add `LoginView` to `auth_service/views.py`: validates institutional email client-side and server-side via `common.validators.is_institutional_email`, calls `accounts.services.verify_password`, re-hashes if `needs_rehash` (Req 8.3), updates `last_login_at`, issues access JWT via `common.tokens.jwt.issue_access_token`, generates an opaque refresh token, inserts a `RefreshToken` row with a new `family_id` and `remember_me`, sets the refresh cookie via `common.tokens.cookies.set_refresh_cookie`, writes `auth.login.success` audit. Failure path writes `auth.login.failure` with `email_attempted` and `reason` ("not_found" | "bad_password") and returns `401 INVALID_CREDENTIALS`.
    - Wire the route into `auth_service/urls.py` as `path('login/', LoginView.as_view())`.
    - _Requirements: 1.1, 1.3, 1.5, 1.6, 1.7, 2.1, 2.6, 2.8, 2.9, 4.1, 4.4, 4.5, 4.6._

  - [ ] 22.2 Implement `POST /refresh` with rotation and reuse detection
    - Add `RefreshView` to `auth_service/views.py`: read refresh cookie, sha256, lookup row.
    - **Reuse-detection branch** (revoked row exists, not expired): atomically `UPDATE refresh_tokens SET revoked_at=now(), revoked_reason='reuse_detected' WHERE family_id=? AND revoked_at IS NULL`, audit `auth.refresh.reuse_detected` with `family_id` and `revoked_count`, return `401 REFRESH_TOKEN_REUSE_DETECTED`.
    - **Expired branch**: audit `auth.refresh.expired`, return `401 REFRESH_TOKEN_EXPIRED`.
    - **Not-found branch**: return `401 REFRESH_TOKEN_REVOKED` (per design §5.3 not-found is treated as revoked).
    - **Active branch**: atomic transaction (`SELECT ... FOR UPDATE`): mark old row `revoked_at=now(), revoked_reason='rotated'`, insert new row inheriting `family_id` and `remember_me` with `parent_id=old.id` and a new opaque token + sha256, set the new refresh cookie, return new access JWT.
    - Wire `path('refresh/', RefreshView.as_view())`.
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.10, 4.4, 4.6, 9.6, 9.8._

  - [ ] 22.3 Implement `POST /logout`
    - Add `LogoutView` to `auth_service/views.py`: tolerant of missing/expired access token (no DRF auth class enforced). Read refresh cookie; if absent, return 204 silently. If present, sha256, find row, if active set `revoked_at=now(), revoked_reason='logout'` (ONLY that row, NOT the family per design §5.4), clear cookie via `clear_refresh_cookie`, audit `auth.logout`. Always return 204.
    - Wire `path('logout/', LogoutView.as_view())`.
    - _Requirements: 9.4, 9.5, 9.6._

  - [ ] 22.4 Implement `GET /me` and JWT authentication class
    - Add `JWTAuthentication` (DRF `BaseAuthentication`) in `auth_service/authentication.py` that reads `Authorization: Bearer <jwt>`, calls `common.tokens.jwt.verify_access_token`, returns `(user, payload)`. Maps `ExpiredSignatureError` to `AuthenticationFailed` with `code='ACCESS_TOKEN_EXPIRED'` (so the error envelope sets the right code).
    - Wire into `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']` in `base.py`.
    - Add `MeView` (`IsAuthenticated`) returning `{id, email, first_name, last_name, role, permissions}` with `permissions` sourced from `accounts.permissions.PermissionRegistry.for_role(user.role)` (empty array when no module has registered any).
    - Wire `path('me/', MeView.as_view())`.
    - Implement `accounts/permissions.py` `PermissionRegistry` per design §5.8 with `_by_role`, `register`, `for_role`. Register `auth.read_self` for all three roles in `accounts.apps.AccountsConfig.ready()`.
    - _Requirements: 3.2, 3.3, 18.1._

  - [ ] 22.5 Implement SSO stub views
    - Create `auth_service/sso.py` (dedicated module per Requirement 6.5 so swapping in a real provider doesn't touch login/token issuance) with `InitiateSsoView` (GET) and `SsoCallbackView` (POST). Both return `501` with envelope `{"error": {"code": "SSO_NOT_CONFIGURED", "message": "Institutional SSO is not yet configured."}, "provider": null}`.
    - Wire `path('sso/initiate/', InitiateSsoView.as_view())` and `path('sso/callback/', SsoCallbackView.as_view())` in `auth_service/urls.py`.
    - _Requirements: 6.3, 6.4, 6.5._

- [ ] 23. Wave A3 checkpoint — auth API verified
  - Ensure `manage.py check` passes; manually exercise `/login`, `/refresh`, `/logout`, `/me` against the local server with curl or pytest+APIClient to confirm cookie set/clear, JWT issuance, rotation revokes the prior row, and SSO endpoints return 501. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4, 3.2, 6.3, 6.4, 9.4._

- [ ] 24. Wave A4 — Password set/reset unified flow
  - [ ] 24.1 Implement `POST /forgot-password`
    - Add `ForgotPasswordSerializer` and `ForgotPasswordView` in `password_reset/views.py`. Domain-validate via `is_institutional_email`. Enforce per-email rate limit (3/hour) using `@rate_limit_per_email(3, 3600, 'RATE_LIMITED_FORGOT_PASSWORD')`. On a match, call `password_reset.services.issue_reset_token(user)` which generates an opaque token, persists `sha256(token)` with `expires_at = now() + 30min`, and dispatches the reset email with the plaintext token via the email backend. On miss, do nothing. ALWAYS return 200 with `{"status": "ok"}` per Requirement 5.1. Audit `auth.password.reset_requested`.
    - Wire `path('forgot-password/', ForgotPasswordView.as_view())` in `password_reset/urls.py`.
    - _Requirements: 5.1, 5.2, 10.3, 11.1, 20.1, 20.2._

  - [ ] 24.2 Implement `POST /reset-password`
    - Add `ResetPasswordSerializer` (validates `token` non-empty + `new_password` via `validate_password_strength`) and `ResetPasswordView`. Look up `sha256(token)`. Atomically:
      1. Inside `transaction.atomic()`: lock the reset row (`SELECT ... FOR UPDATE`); validate `expires_at > now() AND used_at IS NULL`.
      2. `users.password_hash = make_password(new_password)`; `is_email_verified = True`.
      3. `password_reset_tokens.used_at = now()`.
      4. `UPDATE refresh_tokens SET revoked_at=now(), revoked_reason='password_reset' WHERE user_id=? AND revoked_at IS NULL`.
    - Accepts both first-set (existing `password_hash IS NULL`) and reset cases per Requirement 5.7. On invalid/expired/used token, return `400 INVALID_RESET_TOKEN` with no side effect. On weak password, return `400 WEAK_PASSWORD`. Audit `auth.password.reset_completed` with `revoked_refresh_count`.
    - Implement `password_reset.services.issue_reset_token(user)` and `password_reset.services.consume_reset_token(plaintext, new_password)` as the public service functions per design §2.5.
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7, 8.4, 20.1._

  - [ ] 24.3 Author the password-reset and account-activation email templates
    - Create `backend/templates/email/password_reset.txt` and `password_reset.html`, plus `account_activation.txt` and `account_activation.html`. Plain-text + minimal HTML. Both link back to `${FRONTEND_BASE_URL}/reset-password?token=<plaintext>`.
    - The activation template (used by Wave A5 approval flow) reuses the same endpoint per Requirement 7.5 — the template differs only in copy.
    - Add `FRONTEND_BASE_URL` env var (already documented in design §12.1) to `settings/base.py` and `.env.example`.
    - _Requirements: 5.2, 7.5._

- [ ] 25. Wave A4 checkpoint — password flow verified
  - Manually exercise `/forgot-password` and `/reset-password` end-to-end with the console email backend; confirm the generic 200 response on `/forgot-password` regardless of email match, and that successful reset revokes all active refresh tokens for the user. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7._

- [ ] 26. Wave A5 — Request Access workflow
  - [ ] 26.1 Implement public `POST /request-access`
    - Add `RequestAccessSerializer` (`email`, `first_name`, `last_name`, `requested_role`, `justification`; rejects unknown fields per Requirement 18.2) and `RequestAccessView` in `access_requests/views.py`.
    - Validate institutional email via `is_institutional_email`. Reject `EMAIL_ALREADY_REGISTERED` (409) when an active user exists. Reject `DUPLICATE_REQUEST_PENDING` (409) when a pending request already exists — perform a pre-check AND catch `IntegrityError` from the partial-unique index per design §6.4 (the DB constraint is the source of truth). Reject `requested_role` not in `Role.ALLOWED_FOR_REQUEST` with `400 INVALID_REQUESTED_ROLE`.
    - Apply `@rate_limit_per_ip(5, 3600, 'RATE_LIMITED_REQUEST_ACCESS')` and `@rate_limit_per_email(3, 86400, 'RATE_LIMITED_REQUEST_ACCESS')` per design §8.2.
    - On success, persist with `status='pending'`, return 201 with `{"status": "pending", "submitted_at": "..."}`, audit `auth.access_request.submitted`.
    - Wire `path('request-access/', RequestAccessView.as_view())` in `access_requests/urls.py`.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.8, 11.1, 19.1._

  - [ ] 26.2 Implement admin review endpoints and `IsAdministrator` permission
    - Create `accounts/permissions.py::IsAdministrator` (DRF `BasePermission`) requiring authenticated user with `role == 'administrator'`; mismatches return `403 INSUFFICIENT_ROLE`.
    - Add `AccessRequestListView` (`GET /admin/access-requests`) — paginated, filter by `status`, ordering by `created_at DESC`. Restricted to `IsAdministrator`.
    - Add `ApproveAccessRequestView` (`POST /admin/access-requests/{id}/approve`): inside `transaction.atomic()` per design §6.2 — `SELECT FOR UPDATE` the request, assert `status='pending'`, create User (`password_hash=None`, `is_active=True`, requested role, `is_email_verified=False`), call `password_reset.services.issue_reset_token` to issue activation token, send activation email, mark request approved with `reviewed_by` and `reviewed_at`, audit `auth.access_request.approved` with `provisioned_user_id`. On race (`users.email` UNIQUE trips), map to a clean error.
    - Add `DenyAccessRequestView` (`POST /admin/access-requests/{id}/deny`): mark denied with `review_note`, send denial email, audit `auth.access_request.denied`.
    - Wire `path('admin/access-requests/', ...)`, `path('admin/access-requests/<uuid:id>/approve/', ...)`, `path('admin/access-requests/<uuid:id>/deny/', ...)`.
    - _Requirements: 7.5, 7.6, 7.7, 11.1._

- [ ] 27. Wave A5 checkpoint — access request workflow verified
  - Verify the full submit → admin approve → activation email → first password set chain works end-to-end against the console email backend. Verify denials send a denial email and do NOT create a user. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8._

- [ ] 28. Wave A6 — Audit logging integration
  - [ ] 28.1 Verify and complete audit log coverage; add admin read endpoint
    - Audit every auth-relevant view per Requirement 11.1: login success/failure, logout, refresh failures (`auth.refresh.expired`, `auth.refresh.revoked`, `auth.refresh.reuse_detected`), password reset request/completion, role change, access request submit/approve/deny, email failure (`auth.email.failure`).
    - Add `AuditLogListView` (`GET /api/v1/admin/audit-log`) restricted to `IsAdministrator`. Paginated; filterable by `event_type`, `actor_user_id`, `target_user_id`, `created_at__gte`, `created_at__lte`.
    - Audit log MUST be append-only at the API surface — NO update/delete views, NO admin-mutable list serializer (Django Admin registration uses `has_change_permission=False`, `has_delete_permission=False` per design §9.3).
    - Add tests asserting that login success/failure, logout, refresh failures (expired/revoked/reuse), password reset request/completion, role change, and access request submit/approve/deny each produce the expected event row and metadata shape.
    - Wire `path('admin/audit-log/', AuditLogListView.as_view())` in `audit/urls.py`.
    - _Requirements: 11.1, 11.2, 11.3, 11.4._

- [ ] 29. Wave A6 checkpoint — audit logging verified
  - Run the audit-coverage tests and confirm every event type is emitted on the corresponding view. Confirm Django Admin disallows updating or deleting audit log rows. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 11.1, 11.2, 11.3, 11.4._

- [ ] 30. Wave A7 — Rate limiting integration
  - [ ] 30.1 Wire login rate limits and add tests
    - Wire `@rate_limit_per_email(5, 15*60, 'RATE_LIMITED_LOGIN')` and `@rate_limit_per_ip(10, 60, 'RATE_LIMITED_IP')` onto `POST /login`.
    - Per-email counter increments only on FAILED attempts (success path resets the budget per design §8.3); per-IP counter increments on every attempt regardless of outcome.
    - Add tests covering both budgets, including assertion that `Retry-After` header is set on 429s and matches the remaining window.
    - _Requirements: 10.1, 10.2, 10.4._

  - [ ] 30.2 Wire remaining rate limits
    - `POST /forgot-password`: per-email 3/hour, error code `RATE_LIMITED_FORGOT_PASSWORD` (already wired in 24.1; verify here).
    - `POST /request-access`: per-IP 5/hour and per-email 3/day (already wired in 26.1; verify here per Requirement 19.1).
    - `POST /reset-password`: per-IP 10/hour, error code `RATE_LIMITED_IP` (Requirement 19.2 also requires per-IP/per-token 5/15min — apply both decorators per design §8.2).
    - `POST /refresh`: per-IP 60/min.
    - Add tests covering all of the above.
    - _Requirements: 10.3, 10.4, 19.1, 19.2, 19.3._

- [ ] 31. Wave A7 checkpoint — rate limiting verified
  - Run all rate-limit tests; confirm no false 429s on legitimate traffic and 429s with `Retry-After` on abuse. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 19.1, 19.2, 19.3._

- [ ] 32. Wave A8 — Backend property-based tests
  - [ ] 32.1* Refresh token round-trip property test
    - **Property 4 (refresh-token rotation invariants — round-trip portion)**: hypothesis generates synthetic `RefreshToken` field tuples (user_id, family_id, remember_me, expires_at, etc.); persisting then loading the row returns equivalent fields. **Validates: Requirement 2.10.**
    - Tag the test with `Feature: thesys-authentication, Property 4 (round-trip)`.
    - _Requirements: 2.10._

  - [ ] 32.2* Opaque token entropy property test
    - **Property 4 (opaque entropy)**: generate 100k tokens via `generate_opaque_token`; assert pairwise uniqueness (collision probability < 1e-6). **Validates: Requirement 2.8.**
    - _Requirements: 2.8._

  - [ ] 32.3* Password salt uniqueness property test
    - **Property 7 (password hashing)**: hypothesis text strategy for plaintexts meeting strength rules; hashing same plaintext twice yields distinct hash strings; both verify true. **Validates: Requirement 8.4.**
    - _Requirements: 8.4._

  - [ ] 32.4* Institutional email matcher property test (backend mirror)
    - **Property 9 (request-access submission contract — domain portion)**: hypothesis strategy generates inputs ending `pampangastateu.edu.ph` (apex + multi-level subdomain) and fuzzy lookalikes; assert acceptance/rejection. Mirrors the test added in 20.10 but tagged for the request-access contract. **Validates: Requirement 1.2.**
    - _Requirements: 1.2._

  - [ ] 32.5* JWT round-trip property test
    - **Property 1 (login success issues compliant tokens)**: hypothesis generates synthetic users; assert `verify_access_token(issue_access_token(u))` returns claims including `sub`, `role`, `exp > iat`, `exp - iat == 900`, `kid` header present. **Validates: Requirement 2.6.**
    - _Requirements: 2.6._

  - [ ] 32.6* Refresh family invariant property test
    - **Property 5 (reuse detection revokes the family)**: hypothesis generates rotation chains of length `n ≥ 1`; every rotated descendant inherits the original `family_id`; calling `revoke_family(family_id, reason)` marks every still-active row in the family revoked atomically; presenting any previously-rotated plaintext to `/refresh` returns 401 `REFRESH_TOKEN_REUSE_DETECTED`. **Validates: Requirements 2.4, 2.9.**
    - _Requirements: 2.4, 2.9._

- [ ] 33. Wave A8 checkpoint — backend PBT verified
  - Run the full backend property test suite (`pytest tests/property/`) with `@settings(max_examples=200, deadline=None)`; ensure ≥100 examples pass per property. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 1.2, 2.4, 2.6, 2.8, 2.9, 2.10, 8.4._

- [ ] 34. Wave A9 — Frontend AuthContext and axios refresh interceptor
  - [ ] 34.1 Replace the placeholder AuthContext shell with real state
    - In `src/context/AuthContext.jsx`, replace the static placeholder value with: `{ user, accessToken, isAuthenticated, isInitializing, signIn, signOut, refresh, loadMe }`. Access token held in memory only — NEVER persisted to `localStorage` or `sessionStorage` per Requirement 9.2.
    - On mount, attempt a silent `POST /auth/refresh` once. On success, store the access token and call `loadMe()` (`GET /auth/me`) to populate `user`. On 4xx, stay unauthenticated. Set `isInitializing` accordingly.
    - `signIn(email, password, rememberMe)` calls `POST /auth/login`, stores the access token, calls `loadMe`. `signOut()` calls `POST /auth/logout` and clears state.
    - _Requirements: 9.2, 18.1._

  - [ ] 34.2 Wire the axios interceptor with single-flight refresh
    - In `src/api/client.js`, replace the empty interceptor scaffolding with:
      - **Request interceptor**: attach `Authorization: Bearer ${accessToken}` to every request when the token is present.
      - **Response interceptor**: detect `401` with `error.code === 'ACCESS_TOKEN_EXPIRED'`. Call `POST /auth/refresh` once via a singleton refresh promise (`let refreshing = null`) so that `k` concurrent 401s only trigger ONE refresh per design §11.3. Retry the original request once on success. On refresh failure (any `REFRESH_TOKEN_*` code), clear the access token, dispatch `signOut`, and redirect to `/sign-in?reason=session_expired`.
      - On any 2xx response, dispatch a custom `axios:request:success` event that `useIdleTimeout` (Wave A13) subscribes to.
    - _Requirements: 2.2, 9.2, 9.6._

  - [ ] 34.3 Create `src/hooks/useAuth.js`
    - Re-export `useAuthContext` as `useAuth` for ergonomic imports. Single one-liner module so callers can `import { useAuth } from '@/hooks/useAuth'`.
    - _Requirements: 25._

- [ ] 35. Wave A9 checkpoint — auth context and interceptor verified
  - Confirm `useAuth().signIn` populates state, `signOut` clears it, the interceptor performs single-flight refresh under concurrent 401s, and the access token never reaches `localStorage` (DevTools inspection). Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 2.2, 9.2, 9.6, 18.1._

- [ ] 36. Wave A10 — Sign In page
  - [ ] 36.1 Implement `SignInCard` component
    - Create `src/components/auth/SignInCard.jsx`: email + password fields, remember-me checkbox, `<SsoButton />` (disabled, "Coming Soon" tooltip per Requirement 6.1), submit button, inline error region with `role="alert"` per Requirement 17.5. Client-side institutional email validation on blur and submit. Uses UI primitives from `src/components/ui/`. Each input paired with a `<label htmlFor>` per Requirement 17.3.
    - Create `src/components/auth/SsoButton.jsx` — visually disabled button with a tooltip "Coming Soon" that issues no network request on click per Requirement 6.2.
    - Update the barrel `src/components/auth/index.js` to export both.
    - _Requirements: 1.4, 4.1, 6.1, 6.2, 13.1, 13.2, 17.3, 17.5._

  - [ ] 36.2 Implement `SignInPage`
    - Create `src/pages/SignInPage.jsx`. Replaces the `/sign-in` placeholder route in `App.jsx`.
    - On submit: calls `useAuth().signIn(email, password, rememberMe)`, navigates to `/` on success, displays inline error envelope on failure (mapping `INVALID_CREDENTIALS` to "Email or password is incorrect" per Requirement 13.5).
    - Honors `?reason=IDLE_TIMEOUT|session_expired|password_set` query param to show context-appropriate banner (idle timeout per Requirement 9.7, password-set confirmation per Wave A12).
    - Disable the submit button while the request is in flight; show a spinner per Requirement 13.4.
    - _Requirements: 1.1, 1.4, 9.7, 13.1, 13.3, 13.4, 13.5._

- [ ] 37. Wave A10 checkpoint — sign-in UI verified
  - Manually exercise the sign-in flow end-to-end against the local backend; verify success redirects to `/`, invalid credentials show the unified error message, idle-timeout banner renders when navigated with `?reason=IDLE_TIMEOUT`. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 1.1, 1.4, 9.7, 13.1, 13.3, 13.4, 13.5._

- [ ] 38. Wave A11 — Request Access page
  - [ ] 38.1 Implement `RequestAccessForm` component
    - Create `src/components/auth/RequestAccessForm.jsx`: first name, last name, email (institutional only — client-side validation), `requested_role` (Student / Faculty radio — Administrator excluded per Requirement 7.8), justification textarea, submit. Uses UI primitives. Each field labeled per Requirement 17.3.
    - The role selector's underlying values MUST be `student` and `faculty` (canonical lowercase) and displayed labels MUST be "Student" and "Faculty" per Requirement 14.1.
    - Update the barrel `src/components/auth/index.js`.
    - _Requirements: 7.1, 7.8, 14.1, 17.3._

  - [ ] 38.2 Implement `RequestAccessPage`
    - Create `src/pages/RequestAccessPage.jsx`. Replaces the `/request-access` placeholder.
    - On submit: shows success message "Submitted — an administrator will review your request." per Requirement 14.2.
    - Maps backend error codes to friendly inline messages: `INVALID_EMAIL_DOMAIN` → "Please use your institutional email address."; `EMAIL_ALREADY_REGISTERED` → "An account already exists for this email."; `DUPLICATE_REQUEST_PENDING` → "A request for this email is already pending review."; `INVALID_REQUESTED_ROLE` → "Please choose Student or Faculty." per Requirement 14.3.
    - Render a link back to `/sign-in` per Requirement 14.4.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.8, 14.1, 14.2, 14.3, 14.4._

- [ ] 39. Wave A11 checkpoint — request access UI verified
  - Manually exercise the request access flow end-to-end; verify success message renders, duplicate-pending and email-already-registered errors map to friendly inline messages. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.8, 14.1, 14.2, 14.3, 14.4._

- [ ] 40. Wave A12 — Forgot/Reset password pages
  - [ ] 40.1 Implement `ForgotPasswordForm` and `ForgotPasswordPage`
    - Create `src/components/auth/ForgotPasswordForm.jsx` (email field + "Send Reset Link" button) and `src/pages/ForgotPasswordPage.jsx`. Replaces the `/forgot-password` placeholder.
    - On submit always shows the same generic confirmation regardless of whether email matched per Requirement 5.1 / 15.2.
    - Update the barrel `src/components/auth/index.js`.
    - _Requirements: 5.1, 15.1, 15.2._

  - [ ] 40.2 Implement `ResetPasswordForm` and `ResetPasswordPage`
    - Create `src/components/auth/ResetPasswordForm.jsx` (new password + confirm password fields) and `src/pages/ResetPasswordPage.jsx`. Replaces the `/reset-password` placeholder.
    - Read `?token=` from URL via `useSearchParams`. Validate strength client-side (≥12 chars, ≥1 letter, ≥1 digit) and that confirm matches new password (Requirement 15.4 — inline error and prevent submission on mismatch).
    - Call `POST /auth/reset-password` with `{ token, new_password }`. Handles both first-password-set (after admin approval) and forgot-password recovery flows via the unified endpoint per Requirement 5.7.
    - On `INVALID_RESET_TOKEN`, render a message indicating the link is invalid or expired and a link back to `/forgot-password` per Requirement 15.5.
    - On success, navigate to `/sign-in?reason=password_set` so the SignInPage banner from Wave A10 confirms the flow completed.
    - _Requirements: 5.3, 5.4, 5.5, 5.7, 15.3, 15.4, 15.5._

- [ ] 41. Wave A12 checkpoint — password reset UI verified
  - Manually exercise both forgot-password and reset-password flows end-to-end against the console email backend. Verify confirm-password mismatch is blocked, invalid token shows the friendly error, success navigates to `/sign-in?reason=password_set`. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 5.1, 5.3, 5.4, 5.5, 5.7, 15.1, 15.2, 15.3, 15.4, 15.5._

- [ ] 42. Wave A13 — Protected routes and idle timeout
  - [ ] 42.1 Implement `ProtectedRoute`
    - Create `src/routes/ProtectedRoute.jsx`: redirects to `/sign-in?reason=AUTH_REQUIRED&next=<path>` when `!isAuthenticated`. While `isInitializing`, render a Spinner instead of bouncing the user.
    - Add a one-line example usage in `App.jsx` as a sentinel `/account` route protected by `ProtectedRoute` (rendering a placeholder `<div>Account placeholder</div>`) so the wrapper is exercised end-to-end. Foundation Phase routes (`/`, `/sign-in`, `/request-access`, `/forgot-password`, `/reset-password`) remain public.
    - _Requirements: 18.1._

  - [ ] 42.2 Implement `RoleRoute`
    - Create `src/routes/RoleRoute.jsx`: takes `allowedRoles` prop. Redirects to `/` or renders a 403 surface (`<div role="alert">You do not have permission to view this page.</div>`) when the current user's role isn't in the list.
    - _Requirements: 3.4._

  - [ ] 42.3 Implement `useIdleTimeout` hook
    - Create `src/hooks/useIdleTimeout.js`. Subscribes to `mousemove`, `mousedown`, `keydown`, `touchstart`, `scroll`, and the custom `axios:request:success` event dispatched by the API client (Wave A9). Throttled to once per 5 seconds to avoid event storms per design §5.5.
    - Resets a single 30-minute `setTimeout`. On fire: clears the in-memory access token, dispatches `signOut`, navigates to `/sign-in?reason=IDLE_TIMEOUT`.
    - Mounted inside `AuthProvider` (only when `isAuthenticated`) so unauthenticated users incur no listeners.
    - _Requirements: 9.7._

- [ ] 43. Wave A13 checkpoint — protected routes and idle timeout verified
  - Verify `ProtectedRoute` redirects to `/sign-in` when signed out, the sentinel `/account` route works when signed in, and the idle timer fires after 30 minutes of inactivity (or use a smaller test value via env). Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 3.4, 9.7, 18.1._

- [ ] 44. Wave A14 — Frontend tests
  - [ ] 44.1* fast-check property test for the institutional-email validator
    - Add `fast-check` to `frontend/package.json` devDependencies.
    - Create `src/utils/validators.test.js`. **Property 9 (frontend mirror)**: fast-check arbitraries generate valid emails ending `pampangastateu.edu.ph` (apex + subdomain) and lookalikes; assert the frontend `isInstitutionalEmail` validator agrees with the backend `is_institutional_email` (parity with Wave A2's PBT). **Validates: Requirements 1.2, 1.4.**
    - _Requirements: 1.2, 1.4; Property 9 (frontend mirror)._

  - [ ] 44.2* Vitest unit tests for the axios refresh interceptor
    - **Property 17 (single-flight refresh)**: configure Vitest + a mock axios adapter. Cases: (a) single 401 ACCESS_TOKEN_EXPIRED triggers exactly one `/refresh`, original request retries on success; (b) `k=10` concurrent 401s trigger exactly one `/refresh`; (c) `/refresh` fails → `signOut` + redirect to `/sign-in?reason=session_expired`; (d) access token never written to `localStorage` or `sessionStorage` at any point.
    - _Requirements: 2.2, 9.2; Property 17._

  - [ ] 44.3* React Testing Library smoke tests for auth forms
    - Add Vitest + `@testing-library/react` + `@testing-library/jest-dom` to `frontend/package.json` devDependencies.
    - Tests for `SignInCard`, `RequestAccessForm`, `ForgotPasswordForm`, `ResetPasswordForm`: render, submit happy path with mocked API, error display on invalid input, error display on backend error envelope. Each test asserts label associations per Property 20.
    - _Requirements: 1.1, 5.3, 7.1; Property 20 (labels + error focus)._

- [ ] 45. Wave A14 checkpoint — frontend tests verified
  - Run `npm test` (Vitest) and confirm all property tests pass with `numRuns: 100`, all unit tests for the interceptor pass, all RTL smoke tests pass. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 1.1, 1.2, 1.4, 2.2, 5.3, 7.1, 9.2._

## Notes

- This task list spans the **Foundation Phase** (Tasks 1–17, complete) and the **Authentication Phase** (Tasks 18–45, in progress). The Authentication Phase is organized into 14 waves (A1–A14) with one checkpoint task per wave.
- Tasks marked with `*` are optional and can be skipped for faster MVP. All test sub-tasks (property, unit, integration, RTL smoke) are marked optional per the workflow's testing rules. Core implementation tasks are never optional.
- Each leaf task references the requirement(s) it advances. Tasks that advance only structural / environment goals cite "Architecture & Scope Reference" or are flagged "Foundational — no direct EARS criterion".
- **Property-based testing** (`hypothesis` on the backend, `fast-check` on the frontend) is **actively introduced in Wave A2** for pure validators and token helpers, **expanded in Wave A8** to cover the refresh-token state machine, and **mirrored on the frontend in Wave A14**. The Foundation Phase deliberately deferred PBT — that decision was correct because no business logic existed to validate.
- The PostgreSQL `citext` and `pgcrypto` extensions (Requirement 26) are enabled by `accounts/migrations/0001_initial.py` in Wave A1 (Task 18.1).
- Architectural rules (audit append-only, no JWT denylist, no account lockout, no concurrent-refresh grace window, no MFA) are recorded in design §17 and §9 and are NOT introduced as bugs in any wave.
- Checkpoint tasks (8, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45) are NOT included in the Task Dependency Graph per workflow rules — only leaf sub-tasks with decimal notation.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "2.2"] },
    { "id": 1, "tasks": ["2.3", "2.4", "2.5", "2.6"] },
    { "id": 2, "tasks": ["3.1", "4.1", "4.2"] },
    { "id": 3, "tasks": ["3.2"] },
    { "id": 4, "tasks": ["5.1", "5.2"] },
    { "id": 5, "tasks": ["6.1", "7.1"] },
    { "id": 6, "tasks": ["6.2"] },
    { "id": 7, "tasks": ["9.1"] },
    { "id": 8, "tasks": ["9.2", "9.4"] },
    { "id": 9, "tasks": ["9.3", "10.1"] },
    { "id": 10, "tasks": ["11.1", "13.1", "16.1"] },
    { "id": 11, "tasks": ["11.2", "12.1"] },
    { "id": 12, "tasks": ["12.2", "14.1"] },
    { "id": 13, "tasks": ["15.1"] },
    { "id": 14, "tasks": ["16.2"] },
    { "id": 15, "tasks": ["18.1"] },
    { "id": 16, "tasks": ["18.2", "18.3"] },
    { "id": 17, "tasks": ["18.4", "18.5", "18.6", "18.7", "18.8"] },
    { "id": 18, "tasks": ["18.9"] },
    { "id": 19, "tasks": ["20.1", "20.2", "20.3", "20.4", "20.5", "20.6", "20.7", "20.8", "20.9"] },
    { "id": 20, "tasks": ["20.10"] },
    { "id": 21, "tasks": ["22.1"] },
    { "id": 22, "tasks": ["22.2", "22.3", "22.4", "22.5"] },
    { "id": 23, "tasks": ["24.1", "24.3"] },
    { "id": 24, "tasks": ["24.2"] },
    { "id": 25, "tasks": ["26.1"] },
    { "id": 26, "tasks": ["26.2"] },
    { "id": 27, "tasks": ["28.1"] },
    { "id": 28, "tasks": ["30.1", "30.2"] },
    { "id": 29, "tasks": ["32.1", "32.2", "32.3", "32.4", "32.5", "32.6"] },
    { "id": 30, "tasks": ["34.1"] },
    { "id": 31, "tasks": ["34.2", "34.3"] },
    { "id": 32, "tasks": ["36.1"] },
    { "id": 33, "tasks": ["36.2"] },
    { "id": 34, "tasks": ["38.1"] },
    { "id": 35, "tasks": ["38.2"] },
    { "id": 36, "tasks": ["40.1"] },
    { "id": 37, "tasks": ["40.2"] },
    { "id": 38, "tasks": ["42.1", "42.2", "42.3"] },
    { "id": 39, "tasks": ["44.1", "44.2", "44.3"] }
  ]
}
```

> Notes on the graph:
> - Foundation Phase waves (0–14) are preserved verbatim from the prior task list; Authentication Phase waves start at id 15.
> - Only leaf sub-tasks (decimal notation) are included; top-level parent tasks and checkpoint tasks (`8`, `17`, `19`, `21`, `23`, `25`, `27`, `29`, `31`, `33`, `35`, `37`, `39`, `41`, `43`, `45`) are intentionally omitted per workflow rules.
> - `18.1` (citext/pgcrypto migration) runs alone in wave 15 because every subsequent model migration depends on the extensions being available.
> - `18.2`/`18.3` (User model + Role enum) run together in wave 16 — both touch `accounts/models.py`, but they are co-located in a single PR so they are scheduled in the same wave; the agent should treat them as a single edit unit.
> - `20.x` tasks all run in parallel in wave 19 because each touches a distinct `common/` module (`validators.py`, `tokens/jwt.py`, `tokens/opaque.py`, `tokens/cookies.py`, `errors.py`, `csrf.py`, `ratelimit.py`, `email_backend.py`, `audit_logger.py`).
> - `22.x` (login/refresh/logout/me/sso) tasks serialize on `auth_service/urls.py` and `auth_service/views.py`. `22.1` lands first to establish the login wiring; `22.2`–`22.5` follow in wave 22 with sequential merges into the shared modules.
> - `24.x` (password flow) tasks serialize on `password_reset/urls.py`, `views.py`, `services.py`, and the shared email templates folder. `24.1` and `24.3` (which authors templates) can run in parallel in wave 23; `24.2` follows in wave 24.
> - `26.x` (request access) tasks serialize on `access_requests/urls.py` and `views.py`; `26.1` (public submission) lands before `26.2` (admin review) so the access-request creation path exists when admins approve.
> - `28.1` (audit log integration + admin read endpoint) runs after all auth views exist so each event-emission site is wired in one pass.
> - `30.x` (rate limit decorators) runs after the corresponding views exist; `30.1` and `30.2` can be scheduled together in wave 28 since each decorates a different view.
> - `32.x` (backend PBT) tasks all run in parallel in wave 29 because each lives in its own test file.
> - `34.x` (frontend AuthContext + interceptor + useAuth) serializes on `src/context/AuthContext.jsx` and `src/api/client.js`. `34.1` lands first; `34.2`/`34.3` follow in wave 31 with sequential merges.
> - Frontend page waves (`36.x` → `38.x` → `40.x`) all touch `src/App.jsx` (route registration) so they are scheduled in distinct waves to avoid file-write conflicts.
> - `42.x` (route guards + idle timeout) tasks each touch a distinct file (`ProtectedRoute.jsx`, `RoleRoute.jsx`, `useIdleTimeout.js`) plus `App.jsx` for the sentinel route — schedule together in wave 38; the agent should land the routes as a single change.
> - `44.x` (frontend tests) runs last in wave 39 because the tests assert against components and the interceptor behavior introduced in earlier waves.
