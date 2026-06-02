# Requirements Document

## Introduction

The Authentication Module is the first module of THESYS+ (AI-Powered Semantic-Based Thesis Retrieval and Topic Trend Analysis System), a capstone project for Pampanga State University College of Computing Studies (PSU CCS). This module establishes identity, access control, and session management for all subsequent modules (Semantic Search, Thesis Upload, Title Similarity, Topic Trend Analysis, Repository, Analytics, Researcher Directory, Saved Collections, Settings) which are out of scope for this spec.

The module provides academic-email-based sign-in, JWT access and refresh tokens with rotation, role-based access control for Student, Faculty, and Administrator roles, a self-service Request Access workflow for unprovisioned users, an email-based password reset flow, and a placeholder for future institutional SSO integration. The user-facing surface includes a Landing Page, a Sign In card ("Welcome Back"), a Request Access page, and a Forgot Password flow, all rendered in a Light Mode default theme with a Dark Mode toggle that persists across sessions.

Tech stack:
- Frontend: ReactJS, Tailwind CSS, JavaScript
- Backend: Django REST Framework (Python)
- Database: PostgreSQL
- Authentication: JWT access tokens + opaque refresh tokens with rotation

Architecture is explicitly modular monolithic: React Frontend → Django REST API → PostgreSQL → AI Modules (the AI modules are downstream and out of scope for this Auth spec).

### Relationship to Parent THESYS+ Spec

- This module supersedes Requirements 1.1–1.3 of the parent thesys-plus spec for the authentication path. There is NO self-registration. Users obtain accounts only through the Request Access workflow plus Administrator approval.
- Where the parent spec and this module disagree, this module wins for all authentication concerns (password rules, session lifetimes, account-recovery flows, role identifiers, lockout vs rate-limiting).
- The parent spec's account-lockout behavior (Requirement 1.6) is intentionally replaced by IP- and email-scoped rate limiting in this module; see Requirement 10 and Requirement 19.
- Theme preference is persisted in browser `localStorage` by this module. Server-side per-user theme persistence is deferred to the future Settings module and is out of scope here.

## Glossary

- **THESYS+**: The overall thesis retrieval and analysis platform of which the Authentication Module is the first module.
- **Auth_Service**: The backend Django REST Framework service responsible for authentication, authorization, password reset, and access requests.
- **Auth_UI**: The ReactJS frontend that renders the Landing Page, Sign In card, Request Access page, Forgot Password flow, and theme toggle.
- **User**: Any natural person interacting with THESYS+, whether authenticated or not.
- **Role**: One of the canonical lowercase identifiers `student`, `faculty`, or `administrator`. Capitalized labels (Student, Faculty, Administrator) are display-only and appear only at the presentation layer.
- **Student**: A registered User with role `student`; default role assigned through the Request Access flow when no other role is specified.
- **Faculty**: A registered User with role `faculty`; granted elevated permissions reserved for downstream modules.
- **Administrator**: A registered User with role `administrator`; reviews access requests and manages users and roles.
- **Academic_Email**: An email address whose domain is `pampangastateu.edu.ph` OR ends with `.pampangastateu.edu.ph` (case-insensitive). Both the apex domain and any subdomain (for example `student.pampangastateu.edu.ph`) are accepted.
- **Access_Token**: A short-lived JWT used to authorize API calls. Signed with HMAC-SHA256.
- **Refresh_Token**: A longer-lived OPAQUE random token (NOT a JWT) used to obtain a new Access_Token without re-entering credentials. Only its SHA-256 hash is persisted server-side.
- **Refresh_Rotation**: The practice of issuing a new Refresh_Token each time one is used and invalidating the prior Refresh_Token.
- **Remember_Me**: A login option that, when selected, extends the Refresh_Token lifetime so the session persists across browser restarts.
- **Idle_Timeout**: The duration of user inactivity after which the Access_Token is treated as expired by the Auth_UI.
- **User_Initiated_Activity**: Any of the following events originating from the Auth_UI: keyboard input, mouse movement, mouse click, touch event, or successful API request originating from the Auth_UI. Resets the Idle_Timeout countdown.
- **Access_Request**: A submission from an unprovisioned User asking the Administrator to create an account for them.
- **Audit_Log**: An append-only record of authentication-related events used for security review.
- **SSO_Stub**: The placeholder Institutional SSO button and backend endpoint that returns a "not yet configured" response and is structured to be replaced by a real SAML or OAuth provider in the future.
- **Theme**: The visual mode of the Auth_UI, either Light Mode or Dark Mode.
- **Reset_Token**: A single-use, time-limited opaque random token sent by email to allow a User to set a new password (or to set their initial password after Administrator approval). Only its SHA-256 hash is persisted server-side.
- **Lockout (intentionally replaced)**: The parent thesys-plus spec describes a temporary account lockout after repeated failed logins. This module DOES NOT implement account lockout; equivalent abuse-protection is provided exclusively by rate limiting (see Requirement 10 and Requirement 19).

## Scope

### In Scope

- Academic email sign-in with domain validation
- JWT access + refresh token issuance, rotation, and revocation
- Role-Based Access Control with Student, Faculty, and Administrator roles
- Remember Me option
- Forgot Password and Reset Password flows
- Institutional SSO placeholder (UI button + backend stub endpoint)
- Request Access submission and Administrator review workflow
- Secure password hashing
- Session handling, CSRF protection, logout, and idle timeout
- Landing Page, Sign In card, Request Access page, Forgot Password flow UI per Figma
- Light Mode default and Dark Mode toggle with persistence
- Responsive layout, accessibility, rate limiting, and audit logging for authentication events

### Out of Scope

- Semantic Search, Thesis Upload, AI/NLP pipelines
- Repository browsing, Analytics dashboards
- Researcher Directory, Saved Collections
- Application Settings beyond authentication-related settings (theme persistence)
- Real SSO integration with a SAML or OAuth identity provider
- Email infrastructure provisioning beyond what is required to send password reset and access request notifications

## Architecture and Scope Reference

This section captures pre-implementation deliverables that the design phase will elaborate. These are recorded here so that downstream acceptance criteria reference a stable vocabulary.

### Recommended Folder Structure

Frontend (ReactJS):
```
frontend/
├── public/
├── src/
│   ├── api/                # axios client, auth API wrappers
│   ├── assets/
│   ├── components/
│   │   ├── auth/           # SignInCard, RequestAccessForm, ForgotPasswordForm, ResetPasswordForm, SsoButton
│   │   ├── landing/        # Hero, SearchBar, CtaButtons, StatsCards, Footer
│   │   ├── layout/         # Header, ThemeToggle
│   │   └── ui/             # Button, Input, Checkbox, Alert primitives
│   ├── context/            # AuthContext, ThemeContext
│   ├── hooks/              # useAuth, useTheme, useIdleTimeout
│   ├── pages/              # LandingPage, SignInPage, RequestAccessPage, ForgotPasswordPage, ResetPasswordPage
│   ├── routes/             # ProtectedRoute, RoleRoute
│   ├── styles/             # tailwind config consumers, theme tokens
│   ├── utils/              # validators (email domain), token storage helpers
│   ├── App.jsx
│   └── main.jsx
├── tailwind.config.js
└── package.json
```

Backend (Django REST Framework):
```
backend/
├── manage.py
├── thesys/                 # Django project root
│   ├── settings/
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/           # User model, roles, profile
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── permissions.py
│   │   └── urls.py
│   ├── auth_service/       # login, logout, refresh, me, sso stub
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── tokens.py
│   │   └── urls.py
│   ├── access_requests/    # request access + admin review
│   ├── password_reset/     # forgot/reset password
│   └── audit/              # audit log writer + admin views
├── common/                 # rate limiting, email backend, validators
└── requirements.txt
```

### Database Tables

The following PostgreSQL tables are in scope for this module. Column lists are indicative and will be finalized during design.

- `users` — id (UUID), email (unique, citext), password_hash (nullable; remains NULL between Administrator-driven account provisioning and the User's first password set), first_name, last_name, role (lowercase string: `student` | `faculty` | `administrator`), is_active, is_email_verified, created_at, updated_at, last_login_at
- `roles` — id, name (`student` | `faculty` | `administrator`, lowercase canonical identifier), description
- `access_requests` — id, email, first_name, last_name, requested_role (`student` | `faculty`), justification, status (`pending` | `approved` | `denied`), reviewed_by (FK users.id, nullable), reviewed_at, created_at
- `password_reset_tokens` — id, user_id (FK), token_hash (SHA-256 hex of opaque random Reset_Token), expires_at, used_at, created_at
- `refresh_tokens` — id, user_id (FK), token_hash (SHA-256 hex of an opaque random Refresh_Token; the plaintext is never stored), parent_id (FK self, nullable; the immediate predecessor in the rotation chain), family_id (UUID; assigned when a Refresh_Token is first issued at login and inherited by every rotated descendant so the entire family can be revoked in a single UPDATE), remember_me (bool), expires_at, revoked_at, created_at, user_agent, ip_address
- `audit_log` — id, actor_user_id (nullable), event_type, target_user_id (nullable), ip_address, user_agent, success (bool), metadata (jsonb), created_at

The initial database migration SHALL enable the PostgreSQL `citext` extension so the `users.email` column can be stored case-insensitively (see Requirement 26).

### API Endpoints

All endpoints are prefixed with `/api/v1/auth` unless noted.

- `POST /login` — Authenticate with academic email and password; returns Access_Token and sets Refresh_Token cookie.
- `POST /logout` — Revoke current Refresh_Token and clear cookies.
- `POST /refresh` — Exchange a valid Refresh_Token for a new Access_Token and a rotated Refresh_Token.
- `GET  /me` — Return the authenticated User's profile, role, and permissions.
- `POST /request-access` — Submit an Access_Request (unauthenticated).
- `POST /forgot-password` — Initiate password reset by email.
- `POST /reset-password` — Complete password reset using a Reset_Token.
- `GET  /sso/initiate` — SSO_Stub: returns a structured "not_configured" response (placeholder).
- `POST /sso/callback` — SSO_Stub: returns a structured "not_configured" response (placeholder).
- `GET  /admin/access-requests` — Administrator lists Access_Requests with filters.
- `POST /admin/access-requests/{id}/approve` — Administrator approves an Access_Request and provisions the User.
- `POST /admin/access-requests/{id}/deny` — Administrator denies an Access_Request with a reason.

## Requirements

### Requirement 1: Academic Email Sign-In with Domain Validation

**User Story:** As a User, I want to sign in with my institutional email and password, so that I can access THESYS+ with my PSU identity.

#### Acceptance Criteria

1. WHEN a User submits the Sign In form with a syntactically valid Academic_Email and a password, THE Auth_Service SHALL authenticate the credentials and, on success, return an Access_Token and set a Refresh_Token cookie.
2. WHEN a User submits the Sign In form with an email whose domain does not match the institutional pattern, THE Auth_Service SHALL reject the submission with HTTP 400 and an error code `INVALID_EMAIL_DOMAIN`.
3. IF the submitted credentials do not match an active User, THEN THE Auth_Service SHALL return HTTP 401 with error code `INVALID_CREDENTIALS` and SHALL NOT disclose whether the email or the password was incorrect.
4. WHEN the Sign In form is submitted, THE Auth_UI SHALL validate the email domain client-side before calling the Auth_Service and SHALL display an inline error if the domain does not match.
5. THE Auth_Service SHALL treat email comparison as case-insensitive and SHALL store emails in normalized lowercase form.
6. WHEN authentication succeeds, THE Auth_Service SHALL update the User's `last_login_at` timestamp and SHALL write an `auth.login.success` event to the Audit_Log.
7. IF authentication fails, THEN THE Auth_Service SHALL write an `auth.login.failure` event to the Audit_Log including the submitted email and the source IP address.

### Requirement 2: JWT Issuance, Rotation, and Refresh

**User Story:** As a User, I want my session to be maintained securely with short-lived access tokens and refresh tokens, so that I do not have to re-enter my password frequently while remaining protected against token theft.

#### Acceptance Criteria

1. WHEN authentication succeeds, THE Auth_Service SHALL issue an Access_Token with a lifetime of 15 minutes and a Refresh_Token with a lifetime of 24 hours by default.
2. WHEN the Auth_UI receives an HTTP 401 with error code `ACCESS_TOKEN_EXPIRED` from any API call, THE Auth_UI SHALL call `POST /refresh` once before retrying the original request.
3. WHEN `POST /refresh` is called with a valid, non-revoked Refresh_Token, THE Auth_Service SHALL issue a new Access_Token and a new Refresh_Token, AND SHALL revoke the prior Refresh_Token (Refresh_Rotation).
4. IF `POST /refresh` is called with a Refresh_Token that has already been rotated or revoked, THEN THE Auth_Service SHALL revoke the entire rotation family (every Refresh_Token sharing the same `family_id`) for that User and SHALL return HTTP 401 with error code `REFRESH_TOKEN_REUSE_DETECTED`.
5. IF a Refresh_Token is presented after its `expires_at`, THEN THE Auth_Service SHALL return HTTP 401 with error code `REFRESH_TOKEN_EXPIRED`.
6. THE Auth_Service SHALL sign all Access_Tokens with HMAC-SHA256 using a secret loaded from environment configuration AND SHALL include `sub` (user id), `role`, `iat`, `exp`, and `jti` claims at minimum.
7. THE Auth_Service SHALL include a `kid` header on each Access_Token to support future key rotation, even when only one signing key is currently configured.
8. THE Auth_Service SHALL generate Refresh_Tokens as opaque random strings of at least 256 bits of entropy (for example using `secrets.token_urlsafe(32)`) and SHALL persist only the SHA-256 hash of the token in the `refresh_tokens.token_hash` column.
9. WHEN a Refresh_Token is first issued at login, THE Auth_Service SHALL assign a new UUID `family_id` to the token, AND every Refresh_Token issued by Refresh_Rotation from that token SHALL inherit the same `family_id`.
10. FOR ALL issued Refresh_Tokens, persisting then loading the token record SHALL produce an equivalent record (round-trip property over the persisted fields).

### Requirement 3: Role-Based Access Control

**User Story:** As a system stakeholder, I want users to be assigned exactly one of Student, Faculty, or Administrator, so that downstream modules can enforce role-appropriate permissions.

#### Acceptance Criteria

1. THE Auth_Service SHALL persist a `role` value for every User that is exactly one of `student`, `faculty`, or `administrator`.
2. WHEN an Access_Token is issued, THE Auth_Service SHALL include the User's role in the token's `role` claim using the canonical lowercase identifier.
3. WHEN `GET /me` is called by an authenticated User, THE Auth_Service SHALL return the User's role and a permission keys array. WHEN no downstream module has registered permissions for the User's role, THE Auth_Service SHALL return an empty array. THE permission registry SHALL be extensible by downstream modules without modifying the Auth_Service.
4. IF a request to a role-restricted endpoint is made by a User whose role lacks the required permission, THEN THE Auth_Service SHALL return HTTP 403 with error code `INSUFFICIENT_ROLE`.
5. WHEN an Administrator changes another User's role, THE Auth_Service SHALL write an `auth.role.changed` event to the Audit_Log including the previous role, the new role, and the actor's User id.
6. THE Auth_Service SHALL reject any role assignment that is not one of the three defined roles with HTTP 400 and error code `INVALID_ROLE`.
7. THE Auth_Service SHALL use the canonical lowercase role identifiers `student`, `faculty`, and `administrator` in the database, JWT `role` claim, and API request and response payloads, AND THE Auth_UI SHALL render capitalized labels (Student, Faculty, Administrator) only at the presentation layer.

### Requirement 4: Remember Me

**User Story:** As a User, I want to stay signed in across browser restarts, so that I do not have to log in every day on my personal device.

#### Acceptance Criteria

1. WHEN a User submits the Sign In form with the Remember_Me checkbox selected, THE Auth_Service SHALL issue a Refresh_Token with a lifetime of 30 days instead of the default 24 hours.
2. WHEN a User submits the Sign In form with Remember_Me selected, THE Auth_UI SHALL set the Refresh_Token cookie with a `Max-Age` matching the extended lifetime so the cookie survives browser restarts.
3. WHEN a User submits the Sign In form with Remember_Me not selected, THE Auth_UI SHALL set the Refresh_Token cookie as a session cookie with no `Max-Age`.
4. THE Auth_Service SHALL persist the Remember_Me selection on the Refresh_Token record so rotated Refresh_Tokens inherit the same effective lifetime.
5. WHEN Remember_Me is NOT selected, THE effective session lifetime SHALL be the minimum of (server-side Refresh_Token expiry: 24 hours) AND (browser session lifetime via session cookie); closing the browser SHALL end the session even though the server-side Refresh_Token may still be within its 24-hour window.
6. WHEN Remember_Me is selected, THE Auth_Service AND THE Auth_UI SHALL keep both the server-side Refresh_Token `expires_at` and the cookie `Max-Age` in sync at 30 days, including across every Refresh_Rotation, so that rotated descendants do not silently shorten or extend the effective session.

### Requirement 5: Password Set or Reset

**User Story:** As a User, I want a single email-driven flow that lets me set my initial password after Administrator approval and reset my password when I forget it, so that I can establish or recover account access without administrator intervention.

#### Acceptance Criteria

1. WHEN a User submits the Forgot Password form with an email, THE Auth_Service SHALL respond with HTTP 200 and a generic confirmation message regardless of whether the email matches a known account, to prevent account enumeration.
2. WHEN a Forgot Password submission matches an active User, THE Auth_Service SHALL generate a Reset_Token, store its SHA-256 hash in `password_reset_tokens` with an expiry of 30 minutes, and send a reset link to the User's email containing the plaintext token.
3. WHEN a User submits the Reset Password form with a valid, unexpired, unused Reset_Token and a new password meeting strength rules, THE Auth_Service SHALL update the User's `password_hash`, mark the Reset_Token as used, and revoke all existing Refresh_Tokens for that User.
4. IF a Reset_Token is expired, already used, or unknown, THEN THE Auth_Service SHALL return HTTP 400 with error code `INVALID_RESET_TOKEN`.
5. THE Auth_Service SHALL enforce that new passwords are at least 12 characters long and contain at least one letter and one digit.
6. WHEN a password reset succeeds, THE Auth_Service SHALL write an `auth.password.reset` event to the Audit_Log.
7. WHEN a User submits `POST /reset-password` with a valid Reset_Token, THE Auth_Service SHALL accept the submission whether or not the User currently has a `password_hash` (NULL allowed for newly provisioned accounts), AND SHALL set the new hash on success. This unified endpoint serves both first-password-set after Administrator approval and ordinary forgot-password recovery.

### Requirement 6: Institutional SSO Placeholder

**User Story:** As a stakeholder, I want a visible Institutional SSO entry point that is wired to a backend stub, so that a future SAML or OAuth provider can be integrated without changing the UI surface.

#### Acceptance Criteria

1. THE Auth_UI SHALL render the Institutional SSO button on the Sign In card in a visually disabled state with a tooltip reading "Coming Soon".
2. WHEN a User clicks the disabled Institutional SSO button, THE Auth_UI SHALL NOT issue any network request AND SHALL keep the User on the Sign In page.
3. WHEN `GET /sso/initiate` is called by any direct caller, THE Auth_Service SHALL return HTTP 501 with error code `SSO_NOT_CONFIGURED` and a `provider` field set to `null`.
4. WHEN `POST /sso/callback` is called by any direct caller, THE Auth_Service SHALL return HTTP 501 with error code `SSO_NOT_CONFIGURED`.
5. THE Auth_Service SHALL define the SSO stub in a dedicated module so that swapping in a real provider does not require changes to the login or token-issuance modules.

### Requirement 7: Request Access Workflow

**User Story:** As an unprovisioned User, I want to request an account by submitting a form, so that an Administrator can review and approve my access without me needing direct contact.

#### Acceptance Criteria

1. WHEN an unauthenticated User submits the Request Access form with first name, last name, Academic_Email, requested role, and justification, THE Auth_Service SHALL create an Access_Request record with status `pending`.
2. IF the submitted email already belongs to an active User, THEN THE Auth_Service SHALL reject the submission with HTTP 409 and error code `EMAIL_ALREADY_REGISTERED`.
3. IF the submitted email domain does not match the institutional pattern, THEN THE Auth_Service SHALL reject the submission with HTTP 400 and error code `INVALID_EMAIL_DOMAIN`.
4. IF an Access_Request with the same email and status `pending` already exists, THEN THE Auth_Service SHALL reject the submission with HTTP 409 and error code `DUPLICATE_REQUEST_PENDING`.
5. WHEN an Administrator approves a pending Access_Request, THE Auth_Service SHALL create a new active User with the requested role and a NULL `password_hash`, set the Access_Request status to `approved`, record `reviewed_by` and `reviewed_at`, and send an account activation email containing a Reset_Token. The activation link SHALL submit through the same `POST /reset-password` endpoint defined in Requirement 5 (the unified password-set/reset flow).
6. WHEN an Administrator denies a pending Access_Request, THE Auth_Service SHALL set status to `denied`, record `reviewed_by` and `reviewed_at`, and send a denial notification email.
7. WHEN an Administrator approves an Access_Request, THE Auth_Service SHALL write an `auth.access_request.approved` event to the Audit_Log; WHEN denied, THE Auth_Service SHALL write an `auth.access_request.denied` event.
8. THE Auth_Service SHALL reject any requested role that is not exactly `student` or `faculty` (canonical lowercase) with HTTP 400 and error code `INVALID_REQUESTED_ROLE`. The `administrator` role SHALL NOT be self-requestable.

### Requirement 8: Secure Password Hashing

**User Story:** As a security stakeholder, I want passwords to be hashed with a strong algorithm, so that a database compromise does not expose plaintext credentials.

#### Acceptance Criteria

1. THE Auth_Service SHALL hash all passwords using Argon2id as the primary algorithm, with PBKDF2-SHA256 (Django default with at least 600,000 iterations) as an acceptable fallback when Argon2id is unavailable.
2. THE Auth_Service SHALL never persist or log plaintext passwords or password hashes outside of the `users.password_hash` column.
3. WHEN a User authenticates successfully and the stored hash uses an outdated algorithm or parameter set, THE Auth_Service SHALL re-hash and store the password using the current algorithm and parameters during the same request.
4. FOR ALL passwords, hashing the same plaintext twice SHALL produce two different hash strings (salt uniqueness) AND verifying either hash against the original plaintext SHALL return true.

### Requirement 9: Session Handling, CSRF, Logout, and Idle Timeout

**User Story:** As a User, I want my session to be protected against common web attacks and to end automatically when I am inactive, so that my account remains safe on shared devices.

#### Acceptance Criteria

1. THE Auth_Service SHALL deliver Refresh_Tokens to the Auth_UI using an `HttpOnly`, `Secure`, `SameSite=Lax` cookie.
2. THE Auth_UI SHALL hold the Access_Token in memory only and SHALL NOT persist the Access_Token in `localStorage` or `sessionStorage`.
3. WHEN a state-changing request is made from the Auth_UI to a session-bearing Auth_Service endpoint, THE Auth_Service SHALL require a valid CSRF token bound to the session AND SHALL reject the request with HTTP 403 and error code `CSRF_FAILURE` when the token is missing or invalid.
4. THE Auth_Service SHALL EXEMPT `POST /login`, `POST /refresh`, `POST /forgot-password`, and `POST /reset-password` from session-bound CSRF (these endpoints have no established session at the time of the request) AND SHALL instead require an `Origin` header (or, when absent, a `Referer` header) that matches the configured Auth_UI origin, rejecting mismatches with HTTP 403 and error code `ORIGIN_NOT_ALLOWED`.
5. WHEN a User clicks Logout, THE Auth_UI SHALL call `POST /logout`, AND THE Auth_Service SHALL revoke the current Refresh_Token, clear its cookie, and write an `auth.logout` event to the Audit_Log.
6. WHEN `POST /logout` is called, THE Auth_Service SHALL accept the request even if the Access_Token is missing or expired, provided a Refresh_Token cookie is present, AND SHALL revoke that Refresh_Token and clear the cookie.
7. WHILE a User is signed in, IF no User_Initiated_Activity (defined as keyboard input, mouse movement, mouse click, touch event, or successful API request originating from the Auth_UI) occurs in the Auth_UI for 30 minutes, THEN THE Auth_UI SHALL clear the in-memory Access_Token and redirect to the Sign In page with reason `IDLE_TIMEOUT`.
8. WHEN a Refresh_Token is revoked for any reason, THE Auth_Service SHALL ensure subsequent uses of that token return HTTP 401 with error code `REFRESH_TOKEN_REVOKED`.

### Requirement 10: Rate Limiting

**User Story:** As a security stakeholder, I want login and password reset endpoints to be rate-limited, so that brute-force and enumeration attacks are mitigated.

#### Acceptance Criteria

1. WHEN more than 5 failed `POST /login` attempts are made for the same email within 15 minutes, THE Auth_Service SHALL respond to subsequent attempts with HTTP 429 and error code `RATE_LIMITED_LOGIN` for the remainder of the 15-minute window.
2. WHEN more than 10 `POST /login` attempts are made from the same IP address within 1 minute, THE Auth_Service SHALL respond with HTTP 429 and error code `RATE_LIMITED_IP`.
3. WHEN more than 3 `POST /forgot-password` requests are made for the same email within 1 hour, THE Auth_Service SHALL respond with HTTP 429 and error code `RATE_LIMITED_FORGOT_PASSWORD`.
4. WHEN a request is rejected due to rate limiting, THE Auth_Service SHALL include a `Retry-After` header indicating the remaining wait time in seconds.

### Requirement 11: Audit Logging

**User Story:** As an Administrator, I want authentication-related events to be recorded, so that I can investigate security incidents and access changes.

#### Acceptance Criteria

1. THE Auth_Service SHALL write an Audit_Log entry for every login success, login failure, logout, refresh-token failure (`auth.refresh.expired`, `auth.refresh.revoked`, `auth.refresh.reuse_detected`), password reset request, password reset completion, role change, access request submission, access request approval, and access request denial.
2. THE Auth_Service SHALL include the actor User id (when known), the event type, the target User id (when applicable), the source IP address, the user agent, a success boolean, and a JSON metadata field on every Audit_Log entry.
3. THE Auth_Service SHALL treat the Audit_Log as append-only and SHALL NOT expose endpoints that update or delete Audit_Log entries.
4. WHERE Audit_Log read endpoints exist, THE Auth_Service SHALL restrict access to Users with the Administrator role.

### Requirement 12: Landing Page UI

**User Story:** As a visitor, I want a Landing Page that introduces THESYS+ and gives me clear entry points, so that I understand the product and can begin a key task.

#### Acceptance Criteria

1. THE Auth_UI SHALL render a Landing Page with a hero section containing the headline "AI-Powered Thesis Intelligence" and a search bar.
2. THE Auth_UI SHALL render call-to-action buttons on the Landing Page labeled "Check Title Similarity" and "Explore Topic Trends".
3. THE Auth_UI SHALL render three stats cards on the Landing Page with the labels "320+ Theses Indexed", "98% Accuracy Rate", and "20+ Research Categories".
4. THE Auth_UI SHALL render a footer on the Landing Page with links labeled "Privacy Policy", "Terms of Service", and "Help Center", and SHALL render social media icons.
5. WHERE the Landing Page CTA buttons reference modules outside this spec's scope, THE Auth_UI SHALL render the buttons as visible UI controls that route to placeholder pages until the corresponding modules are implemented.

### Requirement 13: Sign In Card UI ("Welcome Back")

**User Story:** As a User on the Sign In page, I want a clear card with the fields and links I need, so that I can sign in, recover my password, request access, or use SSO.

#### Acceptance Criteria

1. THE Auth_UI SHALL render a Sign In card titled "Welcome Back" containing an Academic Email input, a Password input, a Remember Me checkbox, a "Forgot Password" link, a primary "Sign In" button, an Institutional SSO button, and a "No account? Request Access" link.
2. WHEN the Academic Email input loses focus with a value whose domain does not match the institutional pattern, THE Auth_UI SHALL display an inline error stating the email must be an institutional address.
3. WHEN the Sign In button is clicked while the form is invalid, THE Auth_UI SHALL prevent submission and SHALL display field-level validation messages.
4. WHILE the Sign In request is in flight, THE Auth_UI SHALL disable the Sign In button and display a loading indicator.
5. IF the Auth_Service returns `INVALID_CREDENTIALS`, THEN THE Auth_UI SHALL display a non-field error reading "Email or password is incorrect" without indicating which field was wrong.

### Requirement 14: Request Access Page UI

**User Story:** As an unprovisioned User, I want a Request Access page that mirrors the Figma design, so that I can submit my information for Administrator review.

#### Acceptance Criteria

1. THE Auth_UI SHALL render a Request Access page with inputs for first name, last name, Academic Email, requested role (selector with two options whose underlying values are `student` and `faculty` and whose displayed labels are "Student" and "Faculty"), and justification.
2. WHEN the Request Access form is submitted with all required fields valid, THE Auth_UI SHALL call `POST /request-access` and SHALL display a confirmation message on success.
3. IF the Auth_Service returns `EMAIL_ALREADY_REGISTERED` or `DUPLICATE_REQUEST_PENDING`, THEN THE Auth_UI SHALL display the corresponding user-friendly message inline on the form.
4. THE Auth_UI SHALL render a link from the Sign In card to the Request Access page and a link from the Request Access page back to the Sign In page.

### Requirement 15: Forgot Password Flow UI

**User Story:** As a User who forgot my password, I want a clear request-reset and set-new-password flow, so that I can recover access.

#### Acceptance Criteria

1. THE Auth_UI SHALL render a Forgot Password page with an Academic Email input and a "Send Reset Link" button.
2. WHEN the Forgot Password form is submitted, THE Auth_UI SHALL call `POST /forgot-password` and SHALL display a generic confirmation message that does not reveal whether the email matched an account.
3. WHEN a User opens a reset link, THE Auth_UI SHALL render a Reset Password page with new password and confirm password inputs and SHALL submit them with the Reset_Token to `POST /reset-password`.
4. IF the new password and confirm password fields do not match, THEN THE Auth_UI SHALL display an inline error and SHALL prevent submission.
5. IF the Auth_Service returns `INVALID_RESET_TOKEN`, THEN THE Auth_UI SHALL display a message indicating the link is invalid or expired and SHALL offer a link back to the Forgot Password page.

### Requirement 16: Theme Mode and Persistence

**User Story:** As a User, I want a Light Mode default with a Dark Mode toggle that remembers my choice, so that the interface matches my preference across visits.

#### Acceptance Criteria

1. WHEN a User visits the Auth_UI for the first time and no Theme preference is stored in `localStorage`, THE Auth_UI SHALL initialize the Theme based on the operating system's `prefers-color-scheme` setting (precedence: OS `prefers-color-scheme` wins on first visit), AND SHALL fall back to Light Mode when no preference is detectable from the OS.
2. WHEN a User toggles the Theme, THE Auth_UI SHALL apply the new Theme to the entire interface within the same render cycle and SHALL persist the selection in `localStorage` under a key named `thesys.theme`.
3. WHEN a User reloads the page or returns in a new session, THE Auth_UI SHALL apply the persisted Theme before the first paint to avoid a flash of incorrect theme.
4. THE Auth_UI SHALL apply Light Mode using the white and blue palette specified in Figma and Dark Mode using the dark navy and purple palette specified in Figma.
5. FOR ALL pages in scope (Landing, Sign In, Request Access, Forgot Password, Reset Password), toggling the Theme then toggling it again SHALL render the page in its original Theme (round-trip property over Theme application).

### Requirement 17: Responsive Layout and Accessibility

**User Story:** As a User on any supported device or with assistive technology, I want the authentication pages to be usable, so that I can complete my tasks regardless of viewport size or input method.

#### Acceptance Criteria

1. THE Auth_UI SHALL render correct layouts at the Figma breakpoints for mobile (<= 640px), tablet (641-1024px), and desktop (>= 1025px) without horizontal scrolling.
2. THE Auth_UI SHALL allow every interactive element on Landing, Sign In, Request Access, Forgot Password, and Reset Password pages to be reached and activated using keyboard navigation alone.
3. THE Auth_UI SHALL associate every input on the Sign In, Request Access, Forgot Password, and Reset Password forms with a visible label or an `aria-label` attribute.
4. THE Auth_UI SHALL render text and interactive controls with a contrast ratio of at least 4.5:1 against their background in both Light Mode and Dark Mode.
5. WHEN a form submission produces an error, THE Auth_UI SHALL move focus to the first invalid field or the form-level error and SHALL announce the error using `role="alert"` or an equivalent live region.

### Requirement 18: Pretty-Print and Round-Trip for Authentication Payloads

**User Story:** As an integrator, I want the authentication API request and response payloads to round-trip cleanly through JSON serialization, so that client and server stay in sync as the schema evolves.

#### Acceptance Criteria

1. FOR ALL authentication request and response payloads (login, refresh, me, request-access, forgot-password, reset-password), serializing a payload to JSON then parsing it back SHALL produce an equivalent payload (round-trip property).
2. THE Auth_Service SHALL define an explicit serializer for each request and response payload such that unknown fields are rejected with HTTP 400 and error code `UNKNOWN_FIELD`.
3. THE Auth_Service SHALL document the schema of each payload in code (Django REST Framework serializers) so that the design phase can derive a parser and pretty printer reference from a single source of truth.

## Cross-cutting Constraints

These requirements apply across multiple endpoints. They are recorded here to keep them visible without inflating the per-feature requirement sections.

### Requirement 19: Rate Limiting on Additional Endpoints

**User Story:** As a security stakeholder, I want abuse-prone unauthenticated endpoints beyond `/login` and `/forgot-password` to be rate-limited, so that automated abuse of the Request Access and password-set endpoints is mitigated.

#### Acceptance Criteria

1. WHEN more than 5 `POST /request-access` submissions are made from the same IP address within 1 hour, THE Auth_Service SHALL respond to subsequent submissions with HTTP 429 and error code `RATE_LIMITED_REQUEST_ACCESS` for the remainder of the 1-hour window.
2. WHEN more than 5 `POST /reset-password` attempts are made for the same Reset_Token OR from the same IP address within 15 minutes, THE Auth_Service SHALL respond to subsequent attempts with HTTP 429 and error code `RATE_LIMITED_RESET_PASSWORD` for the remainder of the 15-minute window.
3. WHEN a request is rejected under acceptance criterion 1 or 2 of this requirement, THE Auth_Service SHALL include a `Retry-After` header indicating the remaining wait time in seconds.

### Requirement 20: Reset_Token Entropy and Storage

**User Story:** As a security stakeholder, I want Reset_Tokens to be unguessable and unrecoverable from a database compromise, so that an attacker who reads `password_reset_tokens` cannot use the contents to reset passwords.

#### Acceptance Criteria

1. THE Auth_Service SHALL generate Reset_Tokens with at least 256 bits of cryptographic randomness (for example using `secrets.token_urlsafe(32)`).
2. THE Auth_Service SHALL persist only the SHA-256 hash of the Reset_Token in `password_reset_tokens.token_hash` AND SHALL NEVER persist the plaintext Reset_Token after the email has been dispatched.

### Requirement 21: Refresh_Token Format Cross-Reference

**User Story:** As a security stakeholder, I want Refresh_Token format and storage rules captured in one place, so that the rule cannot drift between Requirement 2 and the database schema.

#### Acceptance Criteria

1. THE Auth_Service SHALL implement Refresh_Tokens exactly as specified in Requirement 2 acceptance criteria 8 and 9 (opaque random strings of at least 256 bits, only the SHA-256 hash persisted, `family_id` UUID inherited across rotations). This requirement is a cross-reference and introduces no additional behavior.

### Requirement 22: Refresh_Token Cookie Scope

**User Story:** As a security stakeholder, I want the Refresh_Token cookie scoped narrowly, so that the cookie is not transmitted to unrelated endpoints in the same domain.

#### Acceptance Criteria

1. THE Auth_Service SHALL set the Refresh_Token cookie with `Path=/api/v1/auth`, `HttpOnly`, `Secure`, `SameSite=Lax`, AND `Domain` equal to the configured backend domain, so the cookie is sent only to authentication endpoints.

### Requirement 23: Cross-Origin Resource Sharing

**User Story:** As an integrator, I want CORS configured so the Auth_UI can call the Auth_Service with credentials, so that cookie-bearing authentication requests succeed only from the configured origin.

#### Acceptance Criteria

1. THE Auth_Service SHALL allow Cross-Origin Resource Sharing only from the configured Auth_UI origin AND SHALL set `Access-Control-Allow-Credentials: true` on responses to that origin so cookie-bearing requests succeed.
2. WHEN a request originates from an unconfigured origin, THE Auth_Service SHALL omit the `Access-Control-Allow-Origin` header so the browser blocks the response (no special error code is returned).

### Requirement 24: Email Backend Abstraction

**User Story:** As a developer, I want transactional emails routed through a single backend interface, so that local development uses a console backend and production uses real SMTP without code changes.

#### Acceptance Criteria

1. THE Auth_Service SHALL send all transactional emails (password reset, account activation, access-request denial) through an email backend interface that has at least two implementations: a console backend for local development AND an SMTP backend for production.
2. IF email delivery fails, THEN THE Auth_Service SHALL log the failure with an `auth.email.failure` Audit_Log event AND SHALL return a successful API response to the caller (delivery is best-effort; delivery failures SHALL NOT block the API response).

### Requirement 25: Authenticated Password Change Cross-Reference

**User Story:** As a User, I want to change my password while logged in. This capability is deferred to the future Settings module and is recorded here only to prevent accidental scope creep.

#### Acceptance Criteria

1. THE Auth_Service SHALL NOT expose an authenticated password-change endpoint within this module. WHEN the future Settings module implements authenticated password change (with current-password verification), THAT module SHALL revoke all Refresh_Tokens for the User except the one in use AND SHALL emit an `auth.password.changed` Audit_Log event.

### Requirement 26: PostgreSQL Extensions

**User Story:** As a database operator, I want required PostgreSQL extensions enabled at install time, so that case-insensitive email storage works from the first migration.

#### Acceptance Criteria

1. THE Database initial migration SHALL enable the `citext` PostgreSQL extension, which is required for case-insensitive `users.email` storage.

### Requirement 27: Secure Cookie in Development

**User Story:** As a developer, I want to test the authentication flow locally over plain HTTP, so that I do not have to configure TLS for `localhost`.

#### Acceptance Criteria

1. WHERE the deployment environment is `development` (as indicated by an environment variable, for example `DJANGO_ENV=development`), THE Auth_Service MAY omit the `Secure` flag on the Refresh_Token cookie so local HTTP development against `localhost` works.
2. WHERE the deployment environment is anything other than `development`, THE Auth_Service SHALL set the `Secure` flag on the Refresh_Token cookie.

## Design Phase Notes (Non-Normative)

This section is advisory and is intended for the design phase to consume. The bullets below capture architecture risks and trade-offs that surfaced during architecture validation. They are NOT acceptance criteria.

- Refresh-token reuse detection should revoke by `family_id` (single UUID assigned at first issuance and inherited by every rotated child) so the entire family is revoked in one UPDATE, avoiding chain-walking.
- Remember Me must propagate `expires_at` and the cookie `Max-Age` consistently across rotations so a long-lived session does not silently shorten or extend.
- Access tokens are not revocable mid-lifetime. Password reset revokes all Refresh_Tokens but leaves up to 15 minutes of valid Access_Tokens. This trade-off is accepted for the capstone scope.
- Argon2id depends on the `argon2-cffi` package; PBKDF2-SHA256 (Django default with at least 600,000 iterations) is the documented fallback when Argon2id is unavailable.
- The SPA's axios interceptor must serialize `POST /refresh` calls to avoid concurrent refresh attempts, which would otherwise trip reuse detection. A simple in-memory mutex or promise-singleton is sufficient.
- Idle-timeout coordination across multiple browser tabs is out of scope for the capstone. Each tab tracks its own idle state.
- Architecture stays explicitly modular monolithic: React Frontend → Django REST API → PostgreSQL → AI Modules. The AI Modules are downstream of authentication and out of scope for this Auth spec.
