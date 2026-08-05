# Design Document: THESYS+ Authentication Module

> Status: locked architecture for the capstone scope. Cross-references throughout cite the EARS acceptance criteria in `requirements.md` (e.g., "see Requirement 2.3"). Out-of-scope downstream modules (Semantic Search, Upload, Title Similarity, Topic Trend Analysis, Repository, Analytics, Researcher Directory, Saved Collections, Settings) are not part of this design.

---

## 1. Overview

### 1.1 Purpose

The Authentication Module is the identity layer of THESYS+. It provides:

- Institutional academic email sign-in
- JWT access tokens + opaque refresh tokens with rotation and reuse detection
- Role-based access control across `student`, `faculty`, `administrator`
- Administrator-gated provisioning via the Request Access workflow
- A unified password-set / forgot-password flow
- A visible Institutional SSO entry point that is intentionally a stub
- Light/Dark theme persistence, accessibility, responsive layout
- Rate limiting, CSRF protection, audit logging

### 1.2 Stack and System Context

```mermaid
flowchart LR
    Browser["Browser<br/>React + Tailwind"]
    DRF["Django REST Framework<br/>Auth_Service"]
    PG[("PostgreSQL<br/>+ citext")]
    Email["Email Backend<br/>(console / SMTP)"]
    SSO["SSO Stub<br/>(HTTP 501)"]
    Downstream["Downstream THESYS+ Modules<br/>(Semantic Search, Upload, ...)"]

    Browser -- HTTPS, cookies + JWT --> DRF
    DRF -- SQL --> PG
    DRF -- send() --> Email
    Browser -. clicks SSO .-> DRF
    DRF -. /sso/* .-> SSO
    DRF -. JWT verify, /me, role claim .-> Downstream

    classDef oos fill:#f5f5f5,stroke:#999,color:#666,stroke-dasharray: 3 3;
    class Downstream oos;
```

The Auth_Service is a single Django process. Downstream modules consume only the auth contracts: JWT verification, `GET /me`, and the `role` claim.

### 1.3 In Scope vs Out of Scope

| In scope | Out of scope |
|---|---|
| Sign-in, sign-out, token refresh, `/me` | Self-registration, MFA, biometric auth |
| Access request submission + admin review + provisioning | LMS integration, automated faculty/student roster import |
| Forgot-password and first-password-set (unified) | Password history / rotation policy |
| JWT issuance with rotation + family-wide revocation on reuse | JWT denylist, concurrent-refresh grace window |
| RBAC for three roles, permission registry | Per-resource ACLs, attribute-based access control |
| SSO stub (501) | Real SAML/OIDC integration |
| Light/Dark theme via localStorage | Server-side theme sync (deferred to Settings module) |
| Rate limiting (per-email, per-IP) | Account lockout, CAPTCHA |
| Audit logging of auth events | SIEM forwarding, alerting pipelines |
| Idle timeout (client-side, 30 min) | Multi-tab session coordination |

---

## 2. Architecture

### 2.1 High-Level Component Diagram

```mermaid
flowchart TB
    subgraph Frontend["Frontend (React + Tailwind)"]
        Pages["Pages<br/>Landing / SignIn / RequestAccess<br/>ForgotPassword / ResetPassword"]
        Ctx["Contexts<br/>AuthContext, ThemeContext"]
        Hooks["Hooks<br/>useAuth, useTheme, useIdleTimeout"]
        Api["API Layer (axios)<br/>refresh interceptor"]
    end

    subgraph Backend["Backend (Django REST Framework)"]
        AccessRequests["access_requests app"]
        AuthSvc["auth_service app<br/>login / logout / refresh / me / sso"]
        Accounts["accounts app<br/>User model, roles, permissions"]
        PwReset["password_reset app"]
        Audit["audit app"]
        Common["common<br/>rate limiter, email backend,<br/>validators, token helpers"]
    end

    DB[("PostgreSQL<br/>+ citext")]
    Mail["Email Backend"]

    Pages --> Ctx
    Pages --> Hooks
    Pages --> Api
    Api -- HTTPS+cookie --> AuthSvc
    Api --> AccessRequests
    Api --> PwReset

    AuthSvc --> Accounts
    AuthSvc --> Audit
    AuthSvc --> Common
    AccessRequests --> Accounts
    AccessRequests --> Audit
    AccessRequests --> Common
    PwReset --> Accounts
    PwReset --> Audit
    PwReset --> Common
    Accounts --> DB
    AuthSvc --> DB
    AccessRequests --> DB
    PwReset --> DB
    Audit --> DB
    Common -- send() --> Mail
```

### 2.2 Backend App Layout

| Django app | Responsibilities | Depends on |
|---|---|---|
| `accounts` | User model, role enum, password hashing config, permission registry, Django admin | `common` |
| `auth_service` | `/login`, `/logout`, `/refresh`, `/me`, `/sso/*`, JWT issuance, cookie handling | `accounts`, `audit`, `common` |
| `access_requests` | `/request-access`, `/admin/access-requests/*`, provisioning on approve | `accounts`, `password_reset`, `audit`, `common` |
| `password_reset` | `/forgot-password`, `/reset-password`, token issuance + validation | `accounts`, `auth_service` (refresh-token revocation), `audit`, `common` |
| `audit` | Append-only audit log writer, admin read endpoints | `accounts` (FK only) |
| `common` | Rate limiter, email backend abstraction, validators (institutional email), token helpers (JWT signer, opaque token generator, hashers), CSRF/Origin middleware, error envelope renderer | (leaf) |

Dependency direction is strictly downward. `common` is a leaf; `audit` only depends on `accounts` for FK; `auth_service`, `access_requests`, `password_reset` are siblings that share `accounts` + `audit` + `common`. There are no circular imports. Cross-app calls go through public service functions, not through models directly.

### 2.3 Frontend Feature Layout

```
frontend/src/
├── api/                       # axios client + auth API wrappers
│   ├── client.js              # baseURL, withCredentials, interceptors
│   └── auth.js                # login, logout, refresh, me, requestAccess, forgot, reset
├── components/
│   ├── auth/
│   │   ├── SignInCard.jsx
│   │   ├── RequestAccessForm.jsx
│   │   ├── ForgotPasswordForm.jsx
│   │   ├── ResetPasswordForm.jsx
│   │   └── SsoButton.jsx        # disabled "Coming Soon"
│   ├── landing/
│   │   ├── Hero.jsx
│   │   ├── SearchBar.jsx
│   │   ├── CtaButtons.jsx
│   │   ├── StatsCards.jsx
│   │   └── Footer.jsx
│   ├── layout/
│   │   ├── Header.jsx
│   │   └── ThemeToggle.jsx
│   └── ui/                      # primitives: Button, Input, Checkbox, Alert, Spinner
├── context/
│   ├── AuthContext.jsx          # access token (memory), role, isAuthenticated
│   └── ThemeContext.jsx         # theme, toggle, persistence
├── hooks/
│   ├── useAuth.js
│   ├── useTheme.js
│   └── useIdleTimeout.js
├── pages/                       # LandingPage, SignInPage, ...
├── routes/
│   ├── ProtectedRoute.jsx
│   └── RoleRoute.jsx
├── styles/                      # tailwind tokens, palette
├── utils/                       # validators, formatters, constants
├── App.jsx
└── main.jsx
```

### 2.4 Cross-Cutting Modules (`backend/common/`)

| Module | Responsibility |
|---|---|
| `ratelimit.py` | Decorator + middleware that consults a backing cache and returns 429 + `Retry-After` per Requirement 10 |
| `email_backend.py` | `EmailBackend` interface with `send(to, subject, template_name, context)`; concrete `ConsoleEmailBackend`, `SMTPEmailBackend` |
| `audit_logger.py` | `write(event_type, actor, target, success, metadata, request)` |
| `validators.py` | `is_institutional_email(s)` (apex + any subdomain of `pampangastateu.edu.ph`), password strength (≥12 chars, ≥1 letter, ≥1 digit) |
| `tokens/jwt.py` | `issue_access_token(user)`, `verify_access_token(s)` (HS256, `kid` header) |
| `tokens/opaque.py` | `generate_opaque_token()` (`secrets.token_urlsafe(32)`), `sha256(token)` |
| `tokens/cookies.py` | Refresh cookie set/clear with project-wide attributes |
| `errors.py` | Unified error envelope renderer + DRF exception handler |
| `csrf.py` | Origin/Referer check decorator for cookie-bearing endpoints that aren't session-protected |

### 2.5 Components and Interfaces (Public Service Functions)

These are the public functions cross-app callers may use, so models stay encapsulated:

- `accounts.services.create_user(email, first_name, last_name, role, password=None)` — `password=None` leaves `password_hash` NULL until first set.
- `accounts.services.set_password(user, plaintext)` — hashes via Argon2id; persists.
- `accounts.services.verify_password(user, plaintext)` — returns `(ok, needs_rehash)`.
- `auth_service.tokens.issue_token_pair(user, request, remember_me)` — creates refresh row (with `family_id`) and returns `(access_jwt, refresh_plaintext, refresh_row)`.
- `auth_service.tokens.rotate_refresh(token_plaintext, request)` — returns new pair, revokes prior, detects reuse, raises `RefreshReuseDetected`.
- `auth_service.tokens.revoke_family(family_id, reason)` — marks every row in the family revoked.
- `password_reset.services.issue_reset_token(user)` — returns plaintext token, stores SHA-256 hash.
- `password_reset.services.consume_reset_token(plaintext, new_password)` — atomically validates, sets password, revokes all refresh tokens, marks token used.
- `audit.services.write(...)` — never raises; failures are logged only.

---

## 3. Data Model

### 3.1 ER Diagram

```mermaid
erDiagram
    USERS ||--o{ REFRESH_TOKENS : "owns"
    USERS ||--o{ PASSWORD_RESET_TOKENS : "issued for"
    USERS ||--o{ AUDIT_LOG : "actor of"
    USERS ||--o{ AUDIT_LOG : "target of"
    USERS ||--o{ ACCESS_REQUESTS : "reviewed by"

    USERS {
        uuid id PK
        citext email UK
        varchar password_hash NULL
        varchar first_name
        varchar last_name
        varchar role "enum: student|faculty|administrator"
        bool is_active
        bool is_email_verified
        timestamptz created_at
        timestamptz updated_at
        timestamptz last_login_at NULL
    }

    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        char_64 token_hash UK "sha256 hex"
        uuid family_id "shared across rotation chain"
        uuid parent_id FK NULL "self-reference"
        bool remember_me
        timestamptz expires_at
        timestamptz revoked_at NULL
        varchar revoked_reason NULL
        timestamptz created_at
        varchar user_agent NULL
        inet ip_address NULL
    }

    PASSWORD_RESET_TOKENS {
        uuid id PK
        uuid user_id FK
        char_64 token_hash UK "sha256 hex"
        timestamptz expires_at
        timestamptz used_at NULL
        timestamptz created_at
    }

    ACCESS_REQUESTS {
        uuid id PK
        citext email
        varchar first_name
        varchar last_name
        varchar requested_role "student|faculty"
        text justification
        varchar status "pending|approved|denied"
        text review_note NULL
        uuid reviewed_by FK NULL
        timestamptz reviewed_at NULL
        timestamptz created_at
    }

    AUDIT_LOG {
        bigserial id PK
        uuid actor_user_id FK NULL
        varchar event_type
        uuid target_user_id FK NULL
        inet ip_address NULL
        varchar user_agent NULL
        bool success
        jsonb metadata
        timestamptz created_at
    }
```

### 3.2 Roles

The capstone uses a CHECK constraint with an enum-style `varchar`, not a separate `roles` table. Rationale: only three values, never user-editable, simpler joins, smaller migration surface. The Django side mirrors this with `class Role(TextChoices): STUDENT = "student"; FACULTY = "faculty"; ADMINISTRATOR = "administrator"`.

```sql
CHECK (role IN ('student', 'faculty', 'administrator'))
```

DB and JWT use lowercase. UI capitalizes for display only.

### 3.3 Table Specifications

#### `users`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | no | `gen_random_uuid()` | PK |
| `email` | CITEXT | no | — | UNIQUE; case-insensitive comparison via citext |
| `password_hash` | VARCHAR(255) | **yes** | NULL | NULL until first password set (post-approval) |
| `first_name` | VARCHAR(80) | no | — | input |
| `last_name` | VARCHAR(80) | no | — | input |
| `role` | VARCHAR(16) | no | `'student'` | CHECK constraint above |
| `is_active` | BOOL | no | TRUE | |
| `is_email_verified` | BOOL | no | FALSE | flips to TRUE on first successful password set |
| `created_at` | TIMESTAMPTZ | no | `now()` | |
| `updated_at` | TIMESTAMPTZ | no | `now()` | bumped on UPDATE |
| `last_login_at` | TIMESTAMPTZ | yes | NULL | Requirement 1.6 |

Indexes:
- `users_email_key` UNIQUE on `email` (auto-created by UNIQUE constraint, citext makes it case-insensitive)
- `users_role_idx` on `role` (fast role filtering for admin views)

#### `refresh_tokens`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | no | `gen_random_uuid()` | PK |
| `user_id` | UUID | no | — | FK → `users.id` ON DELETE CASCADE |
| `token_hash` | CHAR(64) | no | — | SHA-256 hex; UNIQUE; the plaintext is never stored |
| `family_id` | UUID | no | — | shared by every token in a rotation chain. Inherited on rotation. |
| `parent_id` | UUID | yes | NULL | FK self-reference, links rotated-from previous row |
| `remember_me` | BOOL | no | FALSE | inherited across rotation (Requirement 4.4) |
| `expires_at` | TIMESTAMPTZ | no | — | derived: now + 24h or 30d |
| `revoked_at` | TIMESTAMPTZ | yes | NULL | NULL = active |
| `revoked_reason` | VARCHAR(40) | yes | NULL | `rotated`, `logout`, `reuse_detected`, `password_reset`, `admin_revoke` |
| `created_at` | TIMESTAMPTZ | no | `now()` | |
| `user_agent` | VARCHAR(255) | yes | NULL | input |
| `ip_address` | INET | yes | NULL | input |

Indexes:
- `refresh_tokens_token_hash_key` UNIQUE on `token_hash`
- `refresh_tokens_user_active_idx` partial: `(user_id) WHERE revoked_at IS NULL` — used to count/list active sessions
- `refresh_tokens_family_idx` on `family_id` — used to revoke entire chain in one UPDATE

#### `password_reset_tokens`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | no | `gen_random_uuid()` | PK |
| `user_id` | UUID | no | — | FK → `users.id` ON DELETE CASCADE |
| `token_hash` | CHAR(64) | no | — | SHA-256 hex; UNIQUE |
| `expires_at` | TIMESTAMPTZ | no | — | derived: now + 30 min |
| `used_at` | TIMESTAMPTZ | yes | NULL | NULL = unused; single-use enforced atomically |
| `created_at` | TIMESTAMPTZ | no | `now()` | |

Indexes:
- `password_reset_tokens_token_hash_key` UNIQUE on `token_hash`
- `password_reset_tokens_user_idx` on `user_id`

#### `access_requests`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | no | `gen_random_uuid()` | PK |
| `email` | CITEXT | no | — | input |
| `first_name` | VARCHAR(80) | no | — | input |
| `last_name` | VARCHAR(80) | no | — | input |
| `requested_role` | VARCHAR(16) | no | — | CHECK IN (`student`, `faculty`) — administrator not self-requestable (Requirement 7.8) |
| `justification` | TEXT | no | — | input |
| `status` | VARCHAR(16) | no | `'pending'` | CHECK IN (`pending`, `approved`, `denied`) |
| `review_note` | TEXT | yes | NULL | denial reason or approval note |
| `reviewed_by` | UUID | yes | NULL | FK → `users.id` ON DELETE SET NULL |
| `reviewed_at` | TIMESTAMPTZ | yes | NULL | |
| `created_at` | TIMESTAMPTZ | no | `now()` | |

Indexes:
- `access_requests_email_pending_uidx` UNIQUE PARTIAL on `email WHERE status = 'pending'` — enforces Requirement 7.4 (`DUPLICATE_REQUEST_PENDING`) at the database level
- `access_requests_status_created_idx` on `(status, created_at DESC)` — admin list view

#### `audit_log`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | BIGSERIAL | no | — | PK |
| `actor_user_id` | UUID | yes | NULL | FK → `users.id` ON DELETE SET NULL |
| `event_type` | VARCHAR(64) | no | — | see Section 9.1 taxonomy |
| `target_user_id` | UUID | yes | NULL | FK → `users.id` ON DELETE SET NULL |
| `ip_address` | INET | yes | NULL | derived |
| `user_agent` | VARCHAR(255) | yes | NULL | derived |
| `success` | BOOL | no | — | input |
| `metadata` | JSONB | no | `'{}'::jsonb` | event-specific payload |
| `created_at` | TIMESTAMPTZ | no | `now()` | |

Indexes:
- `audit_log_created_at_idx` on `created_at DESC`
- `audit_log_event_type_idx` on `event_type`
- `audit_log_actor_idx` on `actor_user_id`
- `audit_log_target_idx` on `target_user_id`

Append-only enforcement: see Section 9.

### 3.4 Migrations and `citext` Extension

Migration ordering, captured per app `migrations/0001_initial.py`:

1. **`accounts.0001`**: enable `pgcrypto` (for `gen_random_uuid`) and **`citext`** at the database level via a `RunSQL` migration:
   ```sql
   CREATE EXTENSION IF NOT EXISTS citext;
   CREATE EXTENSION IF NOT EXISTS pgcrypto;
   ```
   Then create `users` (citext email, role enum CHECK, nullable `password_hash`).
2. **`audit.0001`**: create `audit_log` (depends on `users`).
3. **`access_requests.0001`**: create `access_requests` (depends on `users` for `reviewed_by`); add the partial unique index on `(email) WHERE status='pending'`.
4. **`password_reset.0001`**: create `password_reset_tokens` (depends on `users`).
5. **`auth_service.0001`**: create `refresh_tokens` with `family_id`, `parent_id`, partial active index, family index.

The CITEXT extension is the only non-default DB feature required by this module. Connection user must own or have the privilege to create extensions; in production, the DBA may run the `CREATE EXTENSION` statement manually before `manage.py migrate`.



---

## 4. API Design

All endpoints are prefixed with `/api/v1/auth`. All non-stub endpoints accept and return `application/json; charset=utf-8`.

### 4.1 Unified Error Envelope

All error responses (4xx, 5xx) use:

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email or password is incorrect.",
    "details": { "field": "..." }
  }
}
```

`details` is optional and may include per-field validation messages or, for rate-limited responses, the `retry_after_seconds` integer (also surfaced as the `Retry-After` header).

### 4.2 Auth Modes Legend

| Auth | Meaning |
|---|---|
| `none` | No credentials required |
| `refresh-cookie` | Reads the HttpOnly refresh cookie |
| `access-token` | `Authorization: Bearer <jwt>` |
| `admin-only` | `access-token` AND `role == administrator` |

CSRF modes:

| CSRF | Meaning |
|---|---|
| `session` | Standard Django CSRF token (used on session-bearing endpoints, e.g. admin views) |
| `origin-check` | Origin/Referer must match `ALLOWED_ORIGINS` (used on cookie-bearing endpoints that don't carry a session cookie) |
| `none` | No CSRF needed (pure token-bearer endpoints with no cookie credential) |

### 4.3 Endpoint Catalog

| # | Method + Path | Auth | CSRF | Rate limit | Notes |
|---|---|---|---|---|---|
| 1 | `POST /login` | none | origin-check | per-email 5 / 15min, per-IP 10 / min | Sets refresh cookie |
| 2 | `POST /logout` | refresh-cookie (tolerant) | origin-check | per-IP 60 / min | Tolerates missing/expired access token |
| 3 | `POST /refresh` | refresh-cookie | origin-check | per-IP 60 / min | Rotates token |
| 4 | `GET /me` | access-token | none | per-IP 120 / min | Returns role + permission keys |
| 5 | `POST /request-access` | none | origin-check | per-IP 5 / hour, per-email 3 / day | Public submission |
| 6 | `POST /forgot-password` | none | origin-check | per-email 3 / hour | Always 200 |
| 7 | `POST /reset-password` | none | origin-check | per-IP 10 / hour | Used for first-set + recovery |
| 8 | `GET /sso/initiate` | none | none | per-IP 60 / min | 501 stub |
| 9 | `POST /sso/callback` | none | origin-check | per-IP 60 / min | 501 stub |
| 10 | `GET /admin/access-requests` | admin-only | session | — | Paginated list |
| 11 | `POST /admin/access-requests/{id}/approve` | admin-only | session | — | Provisions user |
| 12 | `POST /admin/access-requests/{id}/deny` | admin-only | session | — | Records denial reason |

### 4.4 Endpoint Schemas

#### 4.4.1 `POST /login`

Request:
```json
{ "email": "user@pampangastateu.edu.ph", "password": "...", "remember_me": false }
```

Success `200 OK`:
```json
{
  "access_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": { "id": "...", "email": "...", "first_name": "...", "last_name": "...", "role": "student" }
}
```
Sets `Set-Cookie: refresh_token=<opaque>; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; ...`

Errors: `400 INVALID_EMAIL_DOMAIN`, `400 UNKNOWN_FIELD`, `401 INVALID_CREDENTIALS`, `403 CSRF_FAILURE`, `429 RATE_LIMITED_LOGIN`, `429 RATE_LIMITED_IP`.

Validates Requirements 1.1–1.7, 2.1, 4.1–4.4, 18.1–18.3.

#### 4.4.2 `POST /logout`

Request body: `{}` (empty allowed).

Success `204 No Content`. Clears refresh cookie. Tolerant to missing/expired access token; the client should be allowed to "sign out" cleanly even if its access token has already expired.

Errors: `403 CSRF_FAILURE`. (Missing refresh cookie returns 204 silently — no information leak.)

Validates Requirement 9.4.

#### 4.4.3 `POST /refresh`

Request body: `{}` (the refresh token rides in the cookie).

Success `200 OK`:
```json
{ "access_token": "<jwt>", "token_type": "Bearer", "expires_in": 900 }
```
Sets a new refresh cookie. Old cookie/value is now revoked.

Errors:
- `401 ACCESS_TOKEN_EXPIRED` — not used here; this is the trigger that *causes* the client to call refresh (returned by other endpoints).
- `401 REFRESH_TOKEN_EXPIRED` — Requirement 2.5
- `401 REFRESH_TOKEN_REVOKED` — Requirement 9.6
- `401 REFRESH_TOKEN_REUSE_DETECTED` — Requirement 2.4 (entire family already revoked)
- `403 CSRF_FAILURE`

Validates Requirements 2.2–2.7, 4.4, 9.6.

#### 4.4.4 `GET /me`

Success `200 OK`:
```json
{
  "id": "uuid",
  "email": "user@pampangastateu.edu.ph",
  "first_name": "...",
  "last_name": "...",
  "role": "student",
  "permissions": ["auth.read_self"]
}
```
On expired access token returns `401 ACCESS_TOKEN_EXPIRED`.

Validates Requirements 3.2, 3.3, 18.1.

#### 4.4.5 `POST /request-access`

Request:
```json
{
  "email": "u@pampangastateu.edu.ph",
  "first_name": "Jane",
  "last_name": "Cruz",
  "requested_role": "student",
  "justification": "First-year MS student."
}
```

Success `201 Created`: `{ "status": "pending", "submitted_at": "..." }`.

Errors: `400 INVALID_EMAIL_DOMAIN`, `400 INVALID_REQUESTED_ROLE`, `400 UNKNOWN_FIELD`, `409 EMAIL_ALREADY_REGISTERED`, `409 DUPLICATE_REQUEST_PENDING`, `429 RATE_LIMITED_IP`.

Validates Requirements 7.1–7.8.

#### 4.4.6 `POST /forgot-password`

Request: `{ "email": "..." }`.

Success: always `200 OK` `{ "status": "ok" }` regardless of match (Requirement 5.1). If matched, an email is dispatched asynchronously by the email backend.

Errors: `400 INVALID_EMAIL_DOMAIN` (to give immediate UX feedback for typos — note this is not enumeration because the domain is public knowledge), `429 RATE_LIMITED_FORGOT_PASSWORD`, `403 CSRF_FAILURE`.

Validates Requirements 5.1, 5.2, 10.3.

#### 4.4.7 `POST /reset-password` (unified)

Used for both first-password-set after an admin approval and ordinary forgot-password recovery. The token's source is opaque to the endpoint — what matters is that it is a valid, unexpired, unused row in `password_reset_tokens`.

Request: `{ "token": "<plaintext>", "new_password": "..." }`.

Success `200 OK`: `{ "status": "ok" }`. Side effects (Requirement 5.3): updates `users.password_hash`, sets `is_email_verified=TRUE`, marks the reset token used, revokes ALL active refresh tokens for that user (issues a `revoke_family` per family).

Errors: `400 INVALID_RESET_TOKEN`, `400 WEAK_PASSWORD`, `400 UNKNOWN_FIELD`, `429 RATE_LIMITED_IP`.

Validates Requirements 5.3–5.6, 8.1, 8.3, 8.4.

#### 4.4.8 `GET /sso/initiate` and `POST /sso/callback`

Both return `501 Not Implemented`:
```json
{ "error": { "code": "SSO_NOT_CONFIGURED", "message": "Institutional SSO is not yet configured." }, "provider": null }
```
Validates Requirement 6.

#### 4.4.9 Admin endpoints

`GET /admin/access-requests?status=pending&page=1&page_size=20` returns paginated list:
```json
{ "results": [ /* AccessRequest objects */ ], "page": 1, "page_size": 20, "total": 42 }
```

`POST /admin/access-requests/{id}/approve` body: `{ "note": "..." }` (optional). Atomically:
1. Loads the request, asserts `status == 'pending'`.
2. Creates the user with `password_hash = NULL`, `is_active = TRUE`, requested role.
3. Issues a Reset_Token via `password_reset.services.issue_reset_token`.
4. Sends activation email containing the reset link.
5. Marks the access request `approved`.
6. Audits.

Returns `200 OK` with the updated request.

`POST /admin/access-requests/{id}/deny` body: `{ "reason": "..." }`. Marks `denied`, sends denial email, audits.

Errors: `404 NOT_FOUND`, `409 NOT_PENDING`, `403 INSUFFICIENT_ROLE`.

Validates Requirements 7.5, 7.6, 7.7, 11.1.

---

## 5. Authentication Architecture

### 5.1 Token Model

| Property | Access Token | Refresh Token |
|---|---|---|
| Format | JWT, HS256 | Opaque string |
| Source of randomness | n/a (signed payload) | `secrets.token_urlsafe(32)` (≥256 bits) |
| Lifetime | 15 min | 24 h default; 30 d with Remember Me |
| Storage server-side | none | row in `refresh_tokens`, value as `sha256(plaintext)` |
| Storage client-side | memory only (Requirement 9.2) | HttpOnly cookie (Requirement 9.1) |
| Revocation model | natural expiry (no denylist) | row state: `revoked_at IS NOT NULL` |
| Header `kid` | yes — supports future key rotation | n/a |

Access JWT claims:

```json
{
  "iss": "thesys-auth",
  "sub": "<user uuid>",
  "role": "student",
  "iat": 1700000000,
  "exp": 1700000900,
  "jti": "<uuid>"
}
```

`kid` is in the JOSE header so a future key rotation can swap signing keys without invalidating in-flight tokens.

### 5.2 Login Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant FE as Auth_UI (React)
    participant BE as Auth_Service (DRF)
    participant DB as PostgreSQL
    participant AU as audit_log

    U->>FE: submit email+password (+remember_me)
    FE->>FE: client-side domain validation
    FE->>BE: POST /login
    BE->>BE: rate-limit check (per-email, per-IP)
    BE->>BE: Origin/Referer check
    BE->>DB: SELECT user WHERE email=? (citext)
    DB-->>BE: row | none
    BE->>BE: verify_password(Argon2id; PBKDF2 fallback)
    alt success
        BE->>BE: re-hash if needed
        BE->>DB: UPDATE last_login_at
        BE->>BE: issue access JWT
        BE->>BE: generate opaque refresh, sha256
        BE->>DB: INSERT refresh_tokens (family_id=new uuid)
        BE->>AU: auth.login.success
        BE-->>FE: 200 + access JWT + Set-Cookie refresh
    else failure
        BE->>AU: auth.login.failure (email, ip)
        BE-->>FE: 401 INVALID_CREDENTIALS
    end
    FE->>FE: store access in memory; set isAuthenticated
```

### 5.3 Refresh + Rotation Flow with Reuse Detection

```mermaid
sequenceDiagram
    autonumber
    participant FE as Auth_UI
    participant BE as Auth_Service
    participant DB as PostgreSQL
    participant AU as audit_log

    FE->>BE: POST /refresh (cookie carries plaintext)
    BE->>BE: sha256(plaintext)
    BE->>DB: SELECT * FROM refresh_tokens WHERE token_hash=?
    alt not found
        BE-->>FE: 401 REFRESH_TOKEN_REVOKED
    else expired (now > expires_at)
        BE->>AU: auth.refresh.expired
        BE-->>FE: 401 REFRESH_TOKEN_EXPIRED
    else revoked (revoked_at IS NOT NULL)
        Note over BE,DB: token already rotated/revoked = REUSE
        BE->>DB: UPDATE refresh_tokens SET revoked_at=now(), revoked_reason='reuse_detected'<br/>WHERE family_id=? AND revoked_at IS NULL
        BE->>AU: auth.refresh.reuse_detected (family_id, user_id)
        BE-->>FE: 401 REFRESH_TOKEN_REUSE_DETECTED
    else active
        BE->>DB: BEGIN<br/>UPDATE old SET revoked_at=now(), revoked_reason='rotated'<br/>INSERT new (family_id=old.family_id, parent_id=old.id, remember_me inherited)<br/>COMMIT
        BE->>BE: issue new access JWT
        BE-->>FE: 200 + new access JWT + Set-Cookie new refresh
    end
```

The reuse-detection path uses a single `UPDATE ... WHERE family_id = ? AND revoked_at IS NULL` to revoke every still-active token in the family in one statement. There is no concurrent-refresh grace window; the first call wins, the second is treated as theft.

### 5.4 Logout Flow

1. Client calls `POST /logout`. CSRF Origin check enforced.
2. Server reads refresh cookie. If absent, return 204 silently.
3. Compute `sha256(plaintext)`, find row.
4. If row exists and is active, set `revoked_at=now(), revoked_reason='logout'`. **Only this row** — not the entire family. (Logout is voluntary; it shouldn't kill other browsers/devices the user is signed in on.)
5. Write `auth.logout` event.
6. Clear the refresh cookie via `Set-Cookie: refresh_token=; Max-Age=0; Path=/api/v1/auth; ...`.
7. Return 204.

The endpoint is tolerant: a missing/expired access token must not block logout. Otherwise users who already crossed the 30-minute idle threshold could not "sign out" without sending a second request.

### 5.5 Frontend Idle Timeout Flow

`useIdleTimeout` (mounted inside `AuthContext` provider when `isAuthenticated`):

1. Subscribes to: `mousemove`, `mousedown`, `keydown`, `touchstart`, `scroll`, and a custom `axios:request:success` event dispatched by the API client on any 2xx.
2. Resets a single `setTimeout` to 30 minutes on each event (Requirement 9.5). Throttled to once per 5 seconds to avoid event storms.
3. On fire: clears in-memory access token, navigates to `/sign-in?reason=IDLE_TIMEOUT`. Server-side refresh cookie is not actively revoked — it will simply be unused and naturally expire.

### 5.6 Cookie Attributes

| Attribute | Value | Notes |
|---|---|---|
| Name | `refresh_token` | |
| Value | opaque plaintext (`token_urlsafe(32)`) | server holds only sha256 |
| `HttpOnly` | yes | not readable from JS (Requirement 9.1) |
| `Secure` | yes (production), no (development over http://localhost) | dev exemption gated on `DJANGO_ENV != 'production'` |
| `SameSite` | `Lax` | Requirement 9.1; allows top-level navigations carrying cookie, blocks cross-site POSTs |
| `Path` | `/api/v1/auth` | scoped — cookie not sent to non-auth APIs |
| `Domain` | from `COOKIE_DOMAIN` env (default omitted, host-only) | |
| `Max-Age` | `2592000` (30 d) if Remember Me, else session cookie (no `Max-Age`) | Requirement 4.1–4.3 |

### 5.7 CSRF Strategy Decision Matrix

| Endpoint | Carries cookie credential? | Carries session cookie? | Strategy |
|---|---|---|---|
| `POST /login` | (sets one) | no | `origin-check` |
| `POST /logout` | yes (refresh) | no | `origin-check` |
| `POST /refresh` | yes (refresh) | no | `origin-check` |
| `POST /forgot-password` | no | no | `origin-check` (defense in depth) |
| `POST /reset-password` | no | no | `origin-check` |
| `GET /me` | no (Bearer only) | no | `none` |
| `GET /sso/initiate` | no | no | `none` |
| `POST /sso/callback` | n/a (stub) | no | `origin-check` |
| Admin endpoints | yes (Django session) | yes | `session` (standard Django CSRF token) |

`origin-check`: middleware compares the request's `Origin` (preferred) or `Referer` against `settings.ALLOWED_ORIGINS`. Mismatch → 403 `CSRF_FAILURE`. Missing both on a state-changing request → 403 `CSRF_FAILURE`.

### 5.8 Permission Registry

A small extensible interface so downstream modules can register permission keys per role without modifying `accounts`:

```python
# accounts/permissions.py
class PermissionRegistry:
    _by_role: dict[str, set[str]] = {"student": set(), "faculty": set(), "administrator": set()}

    @classmethod
    def register(cls, role: str, *keys: str) -> None: ...

    @classmethod
    def for_role(cls, role: str) -> list[str]:
        return sorted(cls._by_role[role])
```

Each module's `apps.py` `ready()` hook calls `register("faculty", "uploads.review_thesis", ...)`. `GET /me` returns `PermissionRegistry.for_role(user.role)`. Default for the auth module is the empty set — only `auth.read_self` is registered for all three roles for the capstone.

Validates Requirement 3.3.



---

## 6. Request Access Workflow

### 6.1 State Machine

```mermaid
stateDiagram-v2
    [*] --> pending : POST /request-access
    pending --> approved : admin approves
    pending --> denied : admin denies
    approved --> [*] : user provisioned + activation email sent
    denied --> [*] : denial email sent

    note right of pending
        partial unique index on (email)
        WHERE status='pending' enforces
        DUPLICATE_REQUEST_PENDING
    end note
    note right of approved
        atomically: insert User
        (password_hash NULL),
        issue Reset_Token,
        send activation email
    end note
```

### 6.2 Approval Pipeline (Atomic)

`access_requests.services.approve(req_id, admin)` runs in a single DB transaction:

1. `SELECT ... FOR UPDATE` the access request, assert `status='pending'`.
2. Pre-check: `users.email` does not already exist (race-safe via UNIQUE on `users.email`).
3. `INSERT INTO users (..., password_hash=NULL, role=requested_role, is_active=TRUE, is_email_verified=FALSE)`.
4. Call `password_reset.services.issue_reset_token(user)` — same code path as forgot-password.
5. `UPDATE access_requests SET status='approved', reviewed_by=admin.id, reviewed_at=now()`.
6. Commit. Then (post-commit hook) enqueue activation email and write `auth.access_request.approved` audit event.

If any step fails, the transaction rolls back and the access request stays `pending` so the admin can retry.

### 6.3 Audit Events Emitted

| Event | Trigger |
|---|---|
| `auth.access_request.submitted` | successful `POST /request-access` |
| `auth.access_request.approved` | approve endpoint commits |
| `auth.access_request.denied` | deny endpoint commits |
| `auth.email.failure` | activation/denial email send fails |

### 6.4 Duplicate Handling

| Condition | HTTP | Code |
|---|---|---|
| Active `users` row already has the email | 409 | `EMAIL_ALREADY_REGISTERED` |
| Pending row already exists for the email (partial unique index trips on INSERT) | 409 | `DUPLICATE_REQUEST_PENDING` |

The DRF view performs a pre-check for both conditions to give friendly errors, but the DB constraint is the source of truth in case of a race.

---

## 7. Password Set / Reset Flow (Unified)

### 7.1 Unified Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant U as User (or Admin)
    participant FE as Auth_UI
    participant BE as Auth_Service
    participant DB as PostgreSQL
    participant E as Email Backend

    rect rgba(220,235,255,0.6)
    Note over U,E: Path A — Forgot Password (existing user)
    U->>FE: enter email on Forgot Password
    FE->>BE: POST /forgot-password
    BE->>DB: SELECT user
    alt match
        BE->>BE: generate plaintext, sha256
        BE->>DB: INSERT password_reset_tokens (expires_at = now + 30 min)
        BE->>E: send(reset link with plaintext)
    else no match
        Note over BE: silent
    end
    BE-->>FE: 200 generic OK
    end

    rect rgba(255,235,215,0.6)
    Note over U,E: Path B — First-password-set after admin approval
    U->>FE: clicks activation link from email
    Note over BE: token was created during approval pipeline (same table)
    end

    Note over FE,BE: Both paths converge here

    FE->>BE: POST /reset-password { token, new_password }
    BE->>BE: sha256(token)
    BE->>DB: SELECT * FROM password_reset_tokens WHERE token_hash=?
    alt invalid / expired / used
        BE-->>FE: 400 INVALID_RESET_TOKEN
    else valid
        BE->>BE: validate password strength
        BE->>DB: BEGIN
        BE->>DB: UPDATE users SET password_hash=Argon2id(new), is_email_verified=TRUE
        BE->>DB: UPDATE password_reset_tokens SET used_at=now()
        BE->>DB: UPDATE refresh_tokens SET revoked_at=now(), revoked_reason='password_reset'<br/>WHERE user_id=? AND revoked_at IS NULL
        BE->>DB: COMMIT
        BE-->>FE: 200 OK
        BE->>BE: write auth.password.reset
    end
```

### 7.2 Token Generation and Storage

- Plaintext: `secrets.token_urlsafe(32)` → ≥256 bits of entropy.
- Stored: `sha256(plaintext)` hex (CHAR(64)). The plaintext is only ever in the email body.
- TTL: 30 minutes (Requirement 5.2). Older rows are not auto-deleted; the validity check is `expires_at > now() AND used_at IS NULL`.
- Single-use: enforced by the same atomic transaction that flips `used_at`.
- Generic 200 response on `/forgot-password` regardless of email existence (Requirement 5.1).

### 7.3 Side Effects on Successful Reset

In one transaction (Requirement 5.3):

1. Update `users.password_hash` with Argon2id-hashed new password.
2. Set `users.is_email_verified = TRUE` (turns NULL→hash and "first set" into "verified" in one motion).
3. Mark the reset token `used_at = now()`.
4. Revoke ALL active `refresh_tokens` for this user. Subsequent refresh attempts return `REFRESH_TOKEN_REVOKED`.

After commit, write `auth.password.reset` to the audit log.

---

## 8. Rate Limiting and Abuse Protection

### 8.1 Backing Store

For the capstone:

- **Development**: `django.core.cache.backends.locmem.LocMemCache` (zero infrastructure).
- **Production**: `django.core.cache.backends.db.DatabaseCache` is acceptable. Redis is optional; recommended only if the deployment already has it.

Selected via `RATE_LIMIT_BACKEND` env var which maps to the corresponding `CACHES['default']` config. The rate limiter calls `cache.incr(key, ...)` with a TTL on first set. The capstone deliberately does not require Redis.

### 8.2 Rule Table

| Scope | Window | Threshold | Endpoint(s) | HTTP | Code | Source |
|---|---|---|---|---|---|---|
| `email` | 15 min | 5 failed attempts | `POST /login` | 429 | `RATE_LIMITED_LOGIN` | Requirement 10.1 |
| `ip` | 1 min | 10 attempts | `POST /login` | 429 | `RATE_LIMITED_IP` | Requirement 10.2 |
| `email` | 1 hour | 3 attempts | `POST /forgot-password` | 429 | `RATE_LIMITED_FORGOT_PASSWORD` | Requirement 10.3 |
| `ip` | 1 hour | 5 attempts | `POST /request-access` | 429 | `RATE_LIMITED_IP` | Defensive |
| `ip` | 1 hour | 10 attempts | `POST /reset-password` | 429 | `RATE_LIMITED_IP` | Defensive |

All 429 responses include a `Retry-After: <seconds>` header (Requirement 10.4) and `details.retry_after_seconds` in the error envelope.

### 8.3 Where the Rate Limiter Hooks In

```
View dispatch
  └─ Origin/CSRF middleware
      └─ @rate_limit(scope='email', window=900, max=5, key=lambda req: req.data['email'].lower())
          └─ DRF view → serializer → service → response
```

Implemented as a DRF view-level decorator (a small wrapper over Django's `cache` framework). The decorator increments BEFORE calling the underlying view for IP scopes, and AFTER for email-failure scopes (so successful logins don't count against the email's failure budget). For the failure scope, the increment lives in an exception handler around `verify_password`.

### 8.4 No Account Lockout

Per scope: this module deliberately does not lock accounts (which would make it trivial for a third party to lock out any known user just by attempting a few bad passwords). Rate limits scope abuse without weaponizing it.

---

## 9. Audit Logging

### 9.1 Event Taxonomy

| Event type | Emitted from |
|---|---|
| `auth.login.success` | `POST /login` success |
| `auth.login.failure` | `POST /login` failure (any reason) |
| `auth.logout` | `POST /logout` |
| `auth.refresh.expired` | `/refresh` with expired token |
| `auth.refresh.revoked` | `/refresh` with already-revoked token (and not part of reuse path) |
| `auth.refresh.reuse_detected` | `/refresh` triggered family-wide revoke |
| `auth.password.reset` | `POST /reset-password` success |
| `auth.role.changed` | Admin changes a user's role |
| `auth.access_request.submitted` | `POST /request-access` success |
| `auth.access_request.approved` | Approval commits |
| `auth.access_request.denied` | Denial commits |
| `auth.email.failure` | Email backend send raises |

### 9.2 Storage Shape

`audit_log` row (see Section 3.3). Common `metadata` fields by event type:

| Event | Typical metadata keys |
|---|---|
| `auth.login.failure` | `email_attempted`, `reason` ("not_found" / "bad_password") |
| `auth.refresh.reuse_detected` | `family_id`, `revoked_count` |
| `auth.role.changed` | `previous_role`, `new_role` |
| `auth.password.reset` | `revoked_refresh_count` |
| `auth.access_request.approved` | `access_request_id`, `provisioned_user_id` |
| `auth.email.failure` | `template_name`, `error_class` |

### 9.3 Append-Only Enforcement

- No DRF endpoint exposes UPDATE or DELETE for `audit_log`.
- Django Admin: `AuditLog` model registers with `has_change_permission=False` and `has_delete_permission=False` for all users including superusers.
- Optional DB-level safety: a `BEFORE UPDATE OR DELETE ON audit_log` trigger that raises an exception. Recommended but not required for the capstone.
- Retention: no automatic pruning in the capstone. If audit volume becomes a problem post-launch, add a periodic job that archives rows older than N months to a separate table (no DELETE).
- Read access: any future audit-log read endpoint MUST require `role == 'administrator'` (Requirement 11.4). Day-to-day, admins read via Django Admin.

### 9.4 Audit Writer Contract

`audit.services.write(...)` never raises into the calling view. Internal failures (e.g., DB hiccup) are logged via `logging.getLogger("audit")` so a transient audit failure cannot block a successful login.

---

## 10. Email Backend

### 10.1 Interface

```python
class EmailBackend(Protocol):
    def send(
        self,
        to: str,
        subject: str,
        template_name: str,           # e.g. "password_reset", "access_request_approved"
        context: dict[str, Any],      # template variables
    ) -> None: ...
```

Templates live under `backend/templates/email/<name>.txt` and `<name>.html`. The backend renders both.

### 10.2 Implementations

| Implementation | When | Configuration |
|---|---|---|
| `ConsoleEmailBackend` | development | `EMAIL_BACKEND=console`; wraps Django's `console.EmailBackend` |
| `SMTPEmailBackend` | production | `EMAIL_BACKEND=smtp`; uses `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `EMAIL_FROM` |

The backend is selected at startup based on `EMAIL_BACKEND` and registered as the global `default_email_backend` accessible to services (no global Django state mutation beyond what Django already does).

### 10.3 Failure Handling

- The send call is wrapped in `try/except`.
- On failure: log via `logging.getLogger("email")`, write `auth.email.failure` to the audit log, and **return** — the calling API request must not fail just because the email queue burped.
- For the capstone there is no retry queue. Production-readiness improvement is documented in Section 17.

---

## 11. Frontend Design

### 11.1 Page Inventory

| Page | Route | Components |
|---|---|---|
| Landing | `/` | `Hero`, `SearchBar`, `CtaButtons`, `StatsCards`, `Footer`, `Header` |
| Sign In | `/sign-in` | `SignInCard` (email, password, remember me, sign in button, SSO button, links) |
| Request Access | `/request-access` | `RequestAccessForm` (first/last name, email, role select, justification) |
| Forgot Password | `/forgot-password` | `ForgotPasswordForm` (email, submit) |
| Reset Password | `/reset-password?token=...` | `ResetPasswordForm` (new password, confirm, submit) |
| Placeholder routes | `/title-similarity`, `/topic-trends`, etc. | `PlaceholderPage` rendering "Module coming soon" |

### 11.2 State Management

`AuthContext` (one provider mounted at the App root):

```js
{
  accessToken: null,        // string | null — IN MEMORY ONLY (Requirement 9.2)
  user: null,               // { id, email, first_name, last_name, role, permissions } | null
  isAuthenticated: false,
  isInitializing: true,     // true until first /refresh attempt resolves on hard load
  signIn(email, password, rememberMe),
  signOut(),
  refresh(),                // single-flight (see 11.3)
  loadMe()
}
```

On mount, `AuthContext` calls `/refresh` once. If 200, it stores access token + calls `/me`. If 4xx, it stays unauthenticated. This is how Remember Me survives a browser restart.

`ThemeContext`:
```js
{ theme: 'light' | 'dark', toggleTheme(), setTheme(t) }
```

`useIdleTimeout(callback, ms)`: subscribes to activity events and calls `callback` after `ms` of silence.

### 11.3 Axios Setup

`api/client.js`:

```js
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL + "/api/v1",
  withCredentials: true,                    // send/receive refresh cookie
});
```

Request interceptor: attaches `Authorization: Bearer <accessToken>` from `AuthContext` when available.

Response interceptor (single-flight refresh):

```
on 401 with code === 'ACCESS_TOKEN_EXPIRED':
  if not currently refreshing:
    refreshing = client.post('/auth/refresh').finally(() => refreshing = null)
  await refreshing
  retry the original request once
on 401 with code in {'REFRESH_TOKEN_*'} during the retry:
  signOut(), redirect to /sign-in?reason=<code>
```

Single-flight ensures ten parallel requests that all see ACCESS_TOKEN_EXPIRED only fire ONE `/refresh`, satisfying Requirement 2.2's "once" semantics.

### 11.4 Theme System

- Tailwind dark mode strategy: `darkMode: 'class'` in `tailwind.config.js`. The `dark` class is toggled on `<html>`.
- Palette tokens defined in `tailwind.config.js` `theme.extend.colors`:
  - Light: white background, blue primary (matches Figma white/blue).
  - Dark: navy background, purple accent (matches Figma navy/purple).
- Pre-paint script, inline in `index.html` `<head>` (runs synchronously before React hydrates) to avoid flash:
  ```html
  <script>
    (function () {
      try {
        var k = 'thesys.theme';
        var stored = localStorage.getItem(k);
        var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        var theme = stored || (prefersDark ? 'dark' : 'light');
        document.documentElement.classList.toggle('dark', theme === 'dark');
      } catch (e) {}
    })();
  </script>
  ```
- `ThemeContext.toggleTheme()` flips state, applies/removes the `dark` class on `<html>` synchronously, and writes `localStorage.setItem('thesys.theme', next)`.
- Theme preference is local-only for this module; server sync is deferred to the Settings module.

### 11.5 Form Validation

- **Institutional email regex** (apex + any subdomain):
  `^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)*pampangastateu\.edu\.ph$` (case-insensitive)
- **Password rules**: ≥12 chars, ≥1 letter, ≥1 digit (Requirement 5.5).
- Inline error messages render below the field with `aria-describedby` linking input → error.
- Errors live in a region with `role="alert"` so screen readers announce them.
- On submit error, focus moves to the first invalid field (Requirement 17.5).

### 11.6 Routing

```
<Routes>
  <Route path="/" element={<LandingPage />} />
  <Route path="/sign-in" element={<SignInPage />} />
  <Route path="/request-access" element={<RequestAccessPage />} />
  <Route path="/forgot-password" element={<ForgotPasswordPage />} />
  <Route path="/reset-password" element={<ResetPasswordPage />} />

  <Route element={<ProtectedRoute />}>
    {/* placeholders for downstream modules referenced by Landing CTA */}
    <Route path="/title-similarity" element={<PlaceholderPage label="Title Similarity" />} />
    <Route path="/topic-trends" element={<PlaceholderPage label="Topic Trends" />} />

    <Route element={<RoleRoute role="administrator" />}>
      <Route path="/admin/access-requests" element={<AccessRequestsAdminPage />} />
    </Route>
  </Route>
</Routes>
```

`ProtectedRoute` redirects unauthenticated users to `/sign-in?reason=AUTH_REQUIRED&next=<path>`. `RoleRoute` returns 403 page if role mismatch.

### 11.7 Accessibility Checklist (mapped to Requirement 17)

| Item | Implementation |
|---|---|
| 17.1 Responsive at mobile/tablet/desktop | Tailwind breakpoints `sm`, `md`, `lg`; layouts validated against Figma screens; no horizontal scroll |
| 17.2 Keyboard reachable | No `tabindex="-1"` on interactive elements; visible focus rings (`focus-visible:ring-2`) |
| 17.3 Labels on every input | `<label htmlFor>` paired with each input on Sign In, Request Access, Forgot, Reset forms |
| 17.4 4.5:1 contrast | Palette tokens chosen against WCAG AA in both themes; verified in Figma + Chrome DevTools |
| 17.5 Focus first error + `role="alert"` | `useEffect` on submit error focuses first invalid `ref`; non-field error container is `role="alert"` |

---

## 12. Configuration and Environment

### 12.1 Backend Environment Variables

| Variable | Purpose | Default (dev) |
|---|---|---|
| `DJANGO_ENV` | `development` / `production` | `development` |
| `DJANGO_SECRET_KEY` | Django secret | (must be set) |
| `JWT_SECRET` | HMAC-SHA256 signing secret | (must be set) |
| `JWT_KID` | `kid` header value | `kid-2025-01` |
| `DATABASE_URL` | Postgres DSN | `postgres://thesys:thesys@localhost:5432/thesys` |
| `ALLOWED_ORIGINS` | comma-separated origins for CORS + Origin check | `http://localhost:5173` |
| `COOKIE_DOMAIN` | refresh cookie `Domain` attribute (or empty for host-only) | empty |
| `EMAIL_BACKEND` | `console` / `smtp` | `console` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_USE_TLS` | SMTP connection | — |
| `EMAIL_FROM` | from address | `noreply@pampangastateu.edu.ph` |
| `RATE_LIMIT_BACKEND` | `locmem` / `db` / `redis` | `locmem` |
| `FRONTEND_BASE_URL` | used to construct reset-password links in emails | `http://localhost:5173` |

### 12.2 Frontend Environment Variables

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | e.g. `http://localhost:8000` (no trailing `/api/v1`) |

### 12.3 Settings Module Organization

```
backend/thesys/settings/
├── __init__.py    # picks base/development/production from DJANGO_ENV
├── base.py        # everything common
├── development.py # DEBUG=True, locmem cache, Secure cookie disabled
└── production.py  # DEBUG=False, ALLOWED_HOSTS, Secure cookie enforced
```

### 12.4 Secrets Handling

- `.env` file at the repo root, **never** committed (gitignored).
- Loaded via `python-dotenv` (recommended for the capstone — minimal dependency).
- `.env.example` IS committed, documenting every variable with placeholder values.



---

## 13. Correctness Properties

> *A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

The Authentication Module mixes pure logic (token signing, hashing, validators, rotation state machine, payload serialization) with rendering (Landing/Sign In pages) and side-effecting flows (email send, audit write). PBT is appropriate for the pure-logic parts and for the API-contract parts that take inputs and produce deterministic outputs. UI-rendering acceptance criteria (12.x, 13.1/13.3/13.4/13.5, 14.x, 15.x, 16.4, 17.1/17.2/17.4) are covered by example-based component tests rather than properties. Architectural rules (6.5, 8.2, 11.3, 18.3) are covered by static lint or smoke checks.

Each property below is universally quantified, references the requirement(s) it validates, and is implementable as a single property-based test (≥100 iterations) tagged with `Feature: thesys-authentication, Property N: <text>`.

### Property 1: Login success issues compliant tokens and updates state

*For any* active user with a known plaintext password and any institutional email casing of that user's email, a successful `POST /login` SHALL return an HS256 JWT (with `kid` header and `sub`, `role`, `iat`, `exp`, `jti` claims; `exp - iat == 900`), set a `Set-Cookie: refresh_token=...; HttpOnly; SameSite=Lax; Path=/api/v1/auth` header, persist exactly one new active row in `refresh_tokens` whose `sha256(plaintext)` equals the hash, and advance the user's `last_login_at`.

**Validates: Requirements 1.1, 1.6, 2.1, 2.6, 9.1**

### Property 2: Email comparison is case-insensitive and storage is lowercase

*For any* institutional email `e` and any case permutation `e'` of `e`, login attempts and request-access submissions SHALL match the same canonical user row, AND the stored value of `users.email` SHALL be byte-equal to `e.lower()`.

**Validates: Requirement 1.5**

### Property 3: Failure responses do not disclose which factor was wrong

*For any* pair of failing login attempts `(known_email, wrong_password)` and `(unknown_email, any_password)` against the same Auth_Service, the HTTP status, error envelope `code`, and the `message` SHALL be byte-equal. Additionally, *for any* email whose domain is not the institutional pattern (apex or any subdomain of `pampangastateu.edu.ph`), `POST /login` SHALL return `400` with `code = INVALID_EMAIL_DOMAIN`.

**Validates: Requirements 1.2, 1.3**

### Property 4: Refresh-token rotation invariants

*For any* active session and any rotation depth `n ≥ 1`, after `n` successful `/refresh` calls:
- exactly one row in the family has `revoked_at IS NULL` (the latest),
- every previously-issued row has `revoked_at IS NOT NULL` with `revoked_reason = 'rotated'`,
- every row in the chain shares the same `family_id` as the original,
- every row's `remember_me` flag equals the original row's `remember_me`,
- `expires_at - created_at` is approximately 24 hours when `remember_me = false` and approximately 30 days when `remember_me = true`,
- the response carries a fresh access JWT and a new refresh cookie.

**Validates: Requirements 2.1, 2.3, 2.7, 4.1, 4.2, 4.3, 4.4**

### Property 5: Refresh-token reuse detection revokes the family

*For any* rotation chain of length `n ≥ 1`, presenting any previously-rotated or already-revoked plaintext to `POST /refresh` SHALL return `401` with `code = REFRESH_TOKEN_REUSE_DETECTED`, AND after the call the count of rows in that `family_id` with `revoked_at IS NULL` SHALL be zero.

**Validates: Requirement 2.4**

### Property 6: Revoked or expired refresh tokens are uniformly rejected

*For any* refresh token whose row has `revoked_at IS NOT NULL` OR `now() > expires_at` (excluding the reuse path covered by Property 5), `POST /refresh` SHALL return `401` with `code = REFRESH_TOKEN_REVOKED` (revoked) or `code = REFRESH_TOKEN_EXPIRED` (expired). No new row is inserted, and no other row's revocation state changes.

**Validates: Requirements 2.5, 9.6**

### Property 7: Password hashing — algorithm, salt uniqueness, upgrade-on-login

*For any* plaintext password `p` meeting the strength rules:
- the persisted `users.password_hash` SHALL begin with the prefix `$argon2id$` (or, when Argon2 is unavailable, `pbkdf2_sha256$`),
- two independent `set_password(p)` calls SHALL produce two different hash strings,
- `verify_password(stored_hash, p)` SHALL return `True` for both hashes,
- if a user has a stored hash using PBKDF2 and they perform a successful login with `p`, after the request the stored hash SHALL begin with `$argon2id$`.

**Validates: Requirements 8.1, 8.3, 8.4**

### Property 8: Role invariants

*For any* user provisioned through any pathway (admin approval, fixture, future SSO), `users.role` SHALL be in `{'student', 'faculty', 'administrator'}`. *For any* access JWT issued for a user, the `role` claim SHALL equal `users.role`. *For any* call to `GET /me` by an authenticated user, the response's `role` field SHALL equal `users.role` and the `permissions` field SHALL equal `PermissionRegistry.for_role(users.role)`. *For any* role-assignment API call with a role string outside the allowed set, the response SHALL be `400` with `code = INVALID_ROLE`. *For any* call to a permission-protected endpoint by a user whose role lacks the required permission key, the response SHALL be `403` with `code = INSUFFICIENT_ROLE`.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6**

### Property 9: Request-Access submission contract

*For any* well-formed submission `(first_name, last_name, email, requested_role, justification)` where `email` matches the institutional pattern, `requested_role ∈ {'student', 'faculty'}`, and no active user exists with that email and no `pending` access request exists with that email, `POST /request-access` SHALL return `201` and persist exactly one row with `status='pending'` and the submitted fields.

*For any* submission with a non-institutional email domain, the response SHALL be `400 INVALID_EMAIL_DOMAIN`. *For any* submission with `requested_role` outside `{'student', 'faculty'}`, `400 INVALID_REQUESTED_ROLE`. *For any* submission whose `email` already exists in `users`, `409 EMAIL_ALREADY_REGISTERED`. *For any* submission whose `email` already has a `pending` row in `access_requests`, `409 DUPLICATE_REQUEST_PENDING`.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.8**

### Property 10: Access-Request approval pipeline

*For any* `pending` access request, after a successful approve call by an administrator the system SHALL satisfy all of:
- `access_requests.status = 'approved'`, `reviewed_by` set, `reviewed_at` set,
- exactly one new `users` row with the requested email, role, `password_hash IS NULL`, `is_active = TRUE`,
- exactly one new `password_reset_tokens` row for that user, with `expires_at - created_at ≈ 30 minutes` and `used_at IS NULL`,
- the email backend was invoked exactly once with the activation template and a link containing the plaintext token.

*For any* `pending` access request, after a successful deny call: `status = 'denied'`, `reviewed_by` set, `reviewed_at` set, denial email dispatched, no `users` or `password_reset_tokens` row created.

**Validates: Requirements 7.5, 7.6, 7.7**

### Property 11: Forgot-password is enumeration-safe and creates correct token rows

*For any* email submitted to `POST /forgot-password`, the HTTP status, body bytes, and external timing class SHALL be byte-equal whether or not the email matches an active user. Additionally, *for any* matching active user, after the call there SHALL exist exactly one new `password_reset_tokens` row for that user with `expires_at - created_at ≈ 30 minutes`, `used_at IS NULL`, and the email backend SHALL have been invoked exactly once with a reset link containing the plaintext token.

**Validates: Requirements 5.1, 5.2**

### Property 12: Reset-password state machine

*For any* `password_reset_tokens` row that is unexpired AND unused AND has a known `token_hash`, AND any new password meeting the strength rules (`len ≥ 12`, `≥1 letter`, `≥1 digit`), `POST /reset-password` SHALL succeed and after the call:
- `users.password_hash` verifies against the new plaintext,
- `users.is_email_verified = TRUE`,
- the reset token row has `used_at IS NOT NULL`,
- every previously-active row in `refresh_tokens` for that user has `revoked_at IS NOT NULL` with `revoked_reason = 'password_reset'`.

*For any* token that is expired, used, or unknown — OR for any new password violating any of the strength rules with an otherwise valid token — the response SHALL be `400` with `code ∈ {INVALID_RESET_TOKEN, WEAK_PASSWORD}` and no side effect SHALL be observable on `users`, `password_reset_tokens`, or `refresh_tokens`.

**Validates: Requirements 5.3, 5.4, 5.5**

### Property 13: CSRF / Origin enforcement on state-changing endpoints

*For any* state-changing endpoint listed in Section 5.7 with CSRF strategy `origin-check` or `session`, a request whose `Origin` (or `Referer`, when `Origin` absent) is not in `ALLOWED_ORIGINS` — or whose session CSRF token is missing/invalid for `session`-mode endpoints — SHALL be rejected with `403` and `code = CSRF_FAILURE`, and SHALL NOT execute any side effect (no DB write, no email send, no audit row).

**Validates: Requirement 9.3**

### Property 14: Rate-limit contract

*For any* of the three scope/window/threshold tuples in Section 8.2 (per-email login 5/15min, per-IP login 10/min, per-email forgot-password 3/hour), once the threshold is exceeded the next request in the same window SHALL be rejected with HTTP `429` and the corresponding error code (`RATE_LIMITED_LOGIN`, `RATE_LIMITED_IP`, `RATE_LIMITED_FORGOT_PASSWORD`). Additionally, *for any* `429` response from this module the `Retry-After` header SHALL be present and SHALL parse as a positive integer ≤ the configured window.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4**

### Property 15: Audit log universal write and schema

*For any* of the eleven auth events in the Section 9.1 taxonomy that occurs successfully or unsuccessfully against the Auth_Service, exactly one new `audit_log` row SHALL be inserted with `event_type` matching the event, and the row SHALL satisfy: `event_type` non-null, `success` non-null, `metadata` is valid JSON, `created_at` non-null, and (where applicable to the event) `actor_user_id`, `target_user_id`, `ip_address`, and `user_agent` are populated according to the per-event mapping in Section 9.2. *For any* failure of the audit writer itself, the originating request SHALL still complete its primary effect (the writer never raises into the caller).

**Validates: Requirements 1.6, 1.7, 5.6, 7.7, 9.4, 11.1, 11.2**

### Property 16: Logout revokes the active refresh row only

*For any* signed-in session presenting its current refresh cookie to `POST /logout`, after the call: the row matching `sha256(plaintext)` SHALL have `revoked_at IS NOT NULL` with `revoked_reason = 'logout'`, the response SHALL include a `Set-Cookie` header that clears `refresh_token` (`Max-Age=0`), no other row in the same `family_id` SHALL change state, and exactly one `audit_log` row of type `auth.logout` SHALL be inserted. *For any* call to `POST /logout` with no refresh cookie or a stale/expired access token, the response SHALL be `204 No Content` with no error.

**Validates: Requirement 9.4**

### Property 17: Frontend single-flight refresh on ACCESS_TOKEN_EXPIRED

*For any* set of `k ≥ 1` concurrent in-flight API calls from the Auth_UI that all receive `401` with `code = ACCESS_TOKEN_EXPIRED`, exactly **one** `POST /refresh` SHALL be dispatched by the axios interceptor, all `k` original requests SHALL be retried at most once after the refresh resolves, AND the access token SHALL never be written to `localStorage` or `sessionStorage` at any point in the sequence.

**Validates: Requirements 2.2, 9.2**

### Property 18: Frontend idle timeout

*For any* signed-in `AuthContext` state, given that no event in `{mousemove, mousedown, keydown, touchstart, scroll, axios:request:success}` fires for 30 minutes, the in-memory access token SHALL be cleared, `isAuthenticated` SHALL become `false`, and the router SHALL navigate to `/sign-in?reason=IDLE_TIMEOUT`. Any qualifying activity event SHALL reset the timer.

**Validates: Requirement 9.5**

### Property 19: Theme initialization, toggle, and round-trip

*For any* combination of `(localStorage['thesys.theme'] ∈ {null, 'light', 'dark'}, prefers-color-scheme ∈ {light, dark, no-preference})`, the pre-paint script SHALL set `document.documentElement.classList.contains('dark')` according to: stored value if non-null; else `true` if `prefers-color-scheme = dark`; else `false`. *For any* page in scope (Landing, Sign In, Request Access, Forgot Password, Reset Password) and any starting theme, calling `toggleTheme()` exactly twice SHALL leave the rendered DOM identical to the pre-toggle DOM (round-trip), AND `localStorage['thesys.theme']` SHALL equal the original value (or be set to the original computed default if previously absent).

**Validates: Requirements 16.1, 16.2, 16.3, 16.5**

### Property 20: Form accessibility — labels and error focus

*For any* input element rendered on the Sign In, Request Access, Forgot Password, or Reset Password forms, there SHALL exist either a `<label>` element whose `htmlFor` matches the input's `id` OR an `aria-label` attribute on the input. *For any* form submission that produces validation errors, after the error renders the focused element SHALL be the first invalid input or the form-level error container, AND the error container SHALL have `role="alert"` (or be inside a region with that role).

**Validates: Requirements 17.3, 17.5**

### Property 21: API payload round-trip and unknown-field rejection

*For any* request or response payload defined by the auth serializers (`/login`, `/logout`, `/refresh`, `/me`, `/request-access`, `/forgot-password`, `/reset-password`, admin access-request endpoints, `/sso/*`), serializing the payload to JSON via the serializer and parsing the resulting bytes back through the same serializer SHALL produce a payload byte-equal to the original (round-trip). *For any* request payload to which an extra field not in the serializer schema is added, validation SHALL fail with `400` and `code = UNKNOWN_FIELD`.

**Validates: Requirements 18.1, 18.2**



---

## 14. Error Handling

### 14.1 Error Envelope

Every non-2xx response from this module returns:

```json
{ "error": { "code": "<UPPER_SNAKE>", "message": "<human readable>", "details": { } } }
```

Implemented via a custom DRF `EXCEPTION_HANDLER` in `common/errors.py`. It maps:

| Source | HTTP | Code |
|---|---|---|
| `serializers.ValidationError` (unknown field) | 400 | `UNKNOWN_FIELD` |
| `serializers.ValidationError` (other field errors) | 400 | `VALIDATION_FAILED` (with `details` field map) |
| `NotAuthenticated`, `AuthenticationFailed` (no token / bad token) | 401 | `ACCESS_TOKEN_EXPIRED` if expiry signature, else `INVALID_TOKEN` |
| Custom `RefreshExpired`, `RefreshRevoked`, `RefreshReuseDetected` | 401 | corresponding refresh code |
| `PermissionDenied` (role check) | 403 | `INSUFFICIENT_ROLE` |
| `csrf.CsrfFailure` | 403 | `CSRF_FAILURE` |
| `Throttled` | 429 | `RATE_LIMITED_*` (set by the throttle class), `Retry-After` header |
| 4xx not otherwise mapped | as raised | code provided by the raising service |
| Unhandled exception | 500 | `INTERNAL_ERROR` (no internals leaked) |

### 14.2 Logging vs Audit

| Channel | Captures | Retention |
|---|---|---|
| `logging.getLogger("auth")` | unexpected exceptions, email-send failures, audit-writer failures | rotating file in dev, stdout in prod |
| `audit_log` table | the eleven event types in Section 9.1 | indefinite (Section 9.3) |

### 14.3 Email Send Failures

Email failures are caught, logged, and audited as `auth.email.failure`, but never propagate. A user whose activation email is dropped can still be re-sent through an admin retry path (future enhancement; not in scope for the capstone).

### 14.4 Database-Level Race Conditions

| Race | Mitigation |
|---|---|
| Two access-request submissions for the same email arrive concurrently | Partial UNIQUE index on `(email) WHERE status='pending'` triggers `IntegrityError` on the second; mapped to 409 `DUPLICATE_REQUEST_PENDING` |
| Two `/refresh` calls present the same token simultaneously | Both compute `sha256` and `SELECT FOR UPDATE` the row inside a transaction; the second waits, then sees `revoked_at IS NOT NULL` and triggers reuse detection |
| Approve + concurrent submission for the same email | Approval pre-check inside the transaction; the user-create step uses `users.email` UNIQUE; on race the second loses with `IntegrityError` mapped to a clean error |

---

## 15. Testing Strategy

This module's testing follows the dual approach: example-based unit/integration tests for concrete behaviors, and property-based tests (PBT) for universal invariants. Both are required.

### 15.1 Property-Based Testing

- **Library**: Hypothesis on the backend (`pip install hypothesis`); fast-check on the frontend (`npm i --save-dev fast-check`). Do not implement PBT from scratch.
- **Iterations**: each property test runs ≥100 examples (`@settings(max_examples=200, deadline=None)` for backend; `fc.assert(prop, { numRuns: 100 })` for frontend).
- **Tagging**: each property test docstring or comment block carries the tag `Feature: thesys-authentication, Property N: <text>` matching Section 13.
- **Implementation rule**: each Property N in Section 13 maps to a single property-based test (one property = one PBT test). Edge cases live inside the property's input generators (e.g., the email regex generator includes apex + multi-level subdomain examples).

### 15.2 Unit Tests Per App

| App | Targets |
|---|---|
| `accounts` | `set_password` / `verify_password`, `is_institutional_email`, password strength validator, role enum boundary |
| `auth_service` | `issue_token_pair`, `rotate_refresh`, `revoke_family`, JWT encode/decode, opaque token generator |
| `password_reset` | `issue_reset_token`, `consume_reset_token`, expiry boundary |
| `access_requests` | submission validation, approval pipeline (with email backend mocked) |
| `audit` | writer schema, never-raises contract |
| `common` | rate limiter increment + reset, error-envelope renderer, Origin check |

### 15.3 Integration Tests

For each endpoint in Section 4.3, at minimum: happy path + 1–2 key error paths. DRF `APIClient`, real Postgres test database (with `citext` extension created via the migration), email backend stubbed in-memory.

### 15.4 Frontend Component Tests

React Testing Library + jsdom. Covers Requirements 12.x, 13.x, 14.x, 15.x, 16.4, 17.1/17.2/17.4 with example assertions, plus the property tests for Properties 17–20.

### 15.5 Manual UAT

A short script tied to the Figma screens: walk a tester through Landing → Sign In → invalid login → Forgot Password → email link → Reset Password → re-login with new password; then Request Access flow with admin approval. Cross-browser smoke (Chrome, Firefox, Safari latest), light/dark theme toggle on each page, mobile viewport check.

### 15.6 What is NOT Property Tested

| Acceptance criteria | Why not | What instead |
|---|---|---|
| 6.1–6.4 SSO stub UI/responses | One-shot stub responses | Single example tests |
| 11.3 audit append-only architecture | Architectural | Static URL conf inspection + Django Admin permission check |
| 12.x Landing Page UI content | Specific copy/labels | Render assertions |
| 13.1, 13.3, 13.4, 13.5 Sign In UI specifics | Specific render/loading state | Render assertions + RTL interaction tests |
| 14.x Request Access UI | Specific render | Render assertions |
| 15.x Forgot/Reset UI | Specific render + interaction | Render + interaction tests |
| 16.4 specific Figma palette | Visual | Snapshot / manual review |
| 17.1, 17.2, 17.4 responsive + keyboard + contrast | Visual / manual | Lighthouse run + manual audit |
| 8.2 plaintext-never-persisted | Architectural | Static lint + targeted audit-log spot test |
| 18.3 schema-as-code | Architectural | Code review |

---

## 16. Configuration and Environment Recap

(Full list in Section 12.) The module is operable on a single developer machine with: PostgreSQL 14+, Python 3.11, Node 20, no Redis, no external email — everything runs locally with `EMAIL_BACKEND=console` and `RATE_LIMIT_BACKEND=locmem`.

---

## 17. Security Posture

### 17.1 Threat → Mitigation

| Threat | Mitigation | Source |
|---|---|---|
| **Account enumeration via login** | Identical 401 envelope for unknown-email and bad-password (Property 3) | Req 1.3 |
| **Account enumeration via forgot-password** | Generic 200 regardless of match (Property 11) | Req 5.1 |
| **Brute-force password guessing** | Per-email + per-IP rate limits on `/login`, no lockout | Req 10.1, 10.2 |
| **Password reset abuse / email bombing** | Per-email rate limit on `/forgot-password` | Req 10.3 |
| **Database compromise → plaintext passwords** | Argon2id (PBKDF2 fallback), per-user salt, upgrade-on-login | Req 8.1, 8.3, 8.4 |
| **Database compromise → refresh-token replay** | Refresh tokens stored as SHA-256 hash; plaintext lives only in cookies | Section 5.1 |
| **Refresh-token theft** | 15-min access window + rotation on every refresh + family-wide revoke on reuse | Req 2.3, 2.4; Property 5 |
| **CSRF on cookie-bearing endpoints** | `SameSite=Lax` cookie + `Origin`/`Referer` allow-list check on login/refresh/logout/forgot/reset | Req 9.1, 9.3; Section 5.7 |
| **CSRF on session-bearing admin endpoints** | Standard Django CSRF token | Section 5.7 |
| **XSS-stealing-tokens** | Access token in JS memory only (Property 17); refresh token `HttpOnly` | Req 9.1, 9.2 |
| **Open redirect on activation/reset link** | Reset link uses `FRONTEND_BASE_URL` from server config; client never honors arbitrary `next=` for this flow | Section 17 — Open Question Q4 |
| **Email spoofing of activation emails** | `EMAIL_FROM` is a controlled sender; SMTP gateway in prod handles SPF/DKIM | Section 10 |
| **Idle-session takeover on shared devices** | 30-min client-side idle timeout (Property 18) + short access TTL | Req 9.5 |
| **Privilege escalation via API role mutation** | `INVALID_ROLE` rejection (Property 8); only admins can change roles; audit on every change | Req 3.5, 3.6 |
| **Self-elevation to administrator via Request Access** | `requested_role` constrained to `{student, faculty}` (Property 9) | Req 7.8 |
| **Audit log tampering** | No mutation/delete endpoints; admin permissions disable change/delete; optional DB trigger | Req 11.3 |

### 17.2 Explicit Non-Goals

This module deliberately does NOT implement:

- A JWT denylist. We rely on short access TTL (15 min) and refresh-token rotation. Capstone scope.
- A concurrent-refresh grace window. The first `/refresh` wins; the second concurrent attempt by the same browser is treated as theft. Acceptable for the capstone given the single-flight axios interceptor.
- Multi-tab session coordination. Each tab independently tracks idle and access tokens.
- MFA, WebAuthn, biometrics.
- IP allow-listing.
- Per-resource ACLs (only role-based permission keys).
- Account lockout (DoS surface).

These are recorded so future contributors don't reintroduce them as bugs.

---

## 18. Deployment and Scalability Notes (Capstone-Realistic)

### 18.1 Reference Deployment

```
[ Browser ]
     |  HTTPS
[ Nginx (TLS termination, static frontend) ]
     |  proxy_pass /api/v1/  ─► [ gunicorn (Django) ] ─► [ PostgreSQL 14+ ]
                                                       └► [ SMTP relay ]
```

- Single Django process behind gunicorn (3–5 workers). No Celery, no Redis, no message broker.
- Single Postgres instance. Daily logical backup is sufficient.
- Frontend built with Vite (`npm run build`) and served as static files by Nginx (or a hosted static site host like Netlify/Vercel pointed at the Django backend's domain).

### 18.2 Where to Add Redis Later, Without Rearchitecting

The two natural Redis upgrade points are isolated by abstractions:

1. **Rate limiter backing store**: `RATE_LIMIT_BACKEND` env var swaps the Django `CACHES` config from `locmem` / `db` to `redis`. The rate-limit decorator code does not change.
2. **Sessions** (admin sessions only): switch `SESSION_ENGINE` from `django.contrib.sessions.backends.db` to `django.contrib.sessions.backends.cache` + Redis cache. No model or view changes.

### 18.3 Horizontal Scale

The backend is stateless. Refresh token state lives in Postgres; the access token is self-contained (JWT). To run a second app server, add it to the Nginx upstream pool; no sticky sessions are required. Time skew between app servers is bounded by NTP — JWT `iat`/`exp` checks tolerate ≤ 30 seconds of skew via `leeway` in `jwt.decode`.

### 18.4 Database Growth Notes

| Table | Growth driver | Index strategy |
|---|---|---|
| `audit_log` | one row per auth event (high write volume) | `(created_at DESC)`, `(event_type)`, `(actor_user_id)` — supports admin filtering by time and event |
| `refresh_tokens` | rotation produces one row per refresh per session | partial index `(user_id) WHERE revoked_at IS NULL` — keeps active-session lookups fast even after years of rotated rows; consider a periodic archive of fully-revoked rows older than 90 days |
| `password_reset_tokens` | low-volume | `token_hash UNIQUE` is sufficient |
| `access_requests` | low-volume | partial unique on pending email, plus `(status, created_at DESC)` for admin views |

For the capstone, no archive job is required. The recommendation is documented for a future maintainer.

---

## 19. Recommended Development Roadmap (Authentication Module Only)

| Phase | Scope | Exit criteria |
|---|---|---|
| **A. Scaffolding** | Django project + apps, Vite + Tailwind, settings split (`base/development/production`), Postgres + `citext` migration, base CI: lint + minimal test smoke | `manage.py migrate` clean; `npm run dev` renders a placeholder Landing |
| **B. Data model + admin** | Migrations for `users`, `audit_log`, `access_requests`, `password_reset_tokens`, `refresh_tokens` (with `family_id`); Django Admin pages for inspection | All tables created; admin shows User, AccessRequest, AuditLog (read-only) |
| **C. Token helpers + auth flows** | Argon2id config; opaque token + sha256 helpers; JWT signer with `kid`; cookie helpers; `/login`, `/refresh` (with rotation + reuse), `/logout`, `/me` | Properties 1, 4, 5, 6, 7, 16 (backend portions) pass |
| **D. Password set/reset + email backend** | `EmailBackend` interface, console + SMTP impls, `/forgot-password`, `/reset-password` (unified) | Properties 11, 12 pass |
| **E. Request Access** | `/request-access`, `/admin/access-requests` list/approve/deny, provisioning pipeline | Properties 9, 10 pass |
| **F. SSO stub** | `/sso/initiate`, `/sso/callback` returning 501 | Example tests pass |
| **G. Rate limiting + Origin/CSRF + audit hooks** | `@rate_limit` decorator wired to all relevant endpoints, Origin-check middleware, audit calls inserted at every event | Properties 13, 14, 15 pass |
| **H. Frontend pages + contexts + interceptor + idle** | Landing, Sign In, Request Access, Forgot Password, Reset Password; AuthContext with single-flight interceptor; ThemeContext with pre-paint; useIdleTimeout | Properties 17, 18, 19 pass |
| **I. Accessibility + responsive polish** | Labels, focus management, contrast review against Figma, breakpoint pass | Property 20 passes; Lighthouse a11y ≥ 90 |
| **J. PBT, UAT, deployment** | All Section 13 properties green ≥ 100 iterations; Manual UAT script run; gunicorn + Nginx + Postgres deploy | Module complete |

---

## 20. Open Questions for Implementation Phase

These are the only items that need a decision before code begins. They are not architectural rewrites — they are concrete configuration / packaging choices.

| # | Question | Default if undecided |
|---|---|---|
| Q1 | Cache backend for rate limiting in production: `db` (Django DatabaseCache, no extra infra) or Redis (faster, extra infra)? | `db`. Revisit if 429 latency is observed. |
| Q2 | SMTP provider in production (Gmail SMTP relay, SendGrid free tier, university mail relay)? | University mail relay if available; SendGrid otherwise. Documented in `.env.example`. |
| Q3 | Ship Django Admin in production? | Yes, behind the standard `/admin/` path with `ADMIN_URL` env var allowing path obfuscation; gated by `is_staff` (only manually-promoted administrators). |
| Q4 | Reset-link URL construction: `FRONTEND_BASE_URL + /reset-password?token=<plaintext>` — is `FRONTEND_BASE_URL` always safe? | Yes; it is server-configured and not user-controlled. Reject any client-supplied `next` parameter on this route. |
| Q5 | JWT `kid` rotation cadence (when, how)? | Capstone: single static `JWT_KID` value. The `kid` header is present so a future maintainer can rotate without changing the verifier code. |
| Q6 | Audit log retention | Capstone: indefinite. Add archive job only if the table grows past ~1M rows. |

---

## Out of Scope (Reminder)

Downstream THESYS+ modules — Semantic Search, Thesis Upload + AI Processing, Title Similarity Validation, Topic Trend Analysis, Repository, Analytics Dashboard, Researcher Directory, Saved Collection, Settings — are **not** part of this design. They will reuse only the public auth contracts:

- JWT verification (HS256 with `kid`, claims `sub`, `role`, `iat`, `exp`, `jti`)
- `GET /me` for current user + role + permission keys
- The `role` claim and `PermissionRegistry` for module-level permission registration

No other coupling to this module is permitted.
