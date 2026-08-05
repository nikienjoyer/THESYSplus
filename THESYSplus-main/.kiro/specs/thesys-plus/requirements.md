# Requirements Document

## Introduction

THESYS+ (AI-Powered Semantic-Based Thesis Retrieval and Topic Trend Analysis System) is a web-based thesis repository platform for Pampanga State University College of Computing Studies (PSU CCS). The platform enables students, faculty, and administrators to upload, search, validate, browse, and analyze thesis documents using Natural Language Processing (NLP). It integrates Sentence-BERT (SBERT) embeddings, cosine similarity, TF-IDF, and topic clustering to support four core academic workflows:

1. **Semantic retrieval** of related theses by meaning, not just keywords.
2. **Title similarity validation** to prevent duplicate or near-duplicate research topics.
3. **Topic trend analysis** to surface popular research areas, emerging topics, and research gaps over time.
4. **Repository management** including upload, browsing, analytics, researcher profiles, saved collections, and account settings.

This document defines functional requirements for all ten modules, role-based access controls for Student, Faculty, and Administrator roles, theming requirements (light/dark mode), Figma design compliance, and non-functional requirements covering modularity, extensibility, performance, and scalability. The requirements are intentionally solution-free where possible so that the subsequent design phase can determine folder structure, database schema, API endpoints, authentication architecture, the AI/NLP pipeline, the development roadmap, and scalability strategies.

## Glossary

- **THESYS+**: The complete web application, comprising the Frontend, the Backend, the AI Service, and the Database.
- **Frontend**: The ReactJS + Tailwind CSS single-page application (SPA) consumed by the browser.
- **Backend**: The Django REST Framework application that exposes HTTP/JSON endpoints to the Frontend.
- **AI_Service**: The logical component (callable in-process or as a separate worker) that performs SBERT embedding generation, cosine similarity computation, TF-IDF vectorization, and topic clustering.
- **Database**: The PostgreSQL instance that stores users, theses, embeddings, metadata, saved collections, audit logs, and configuration.
- **File_Storage**: The persistent store for uploaded PDF and DOCX files (filesystem or object storage).
- **Auth_Service**: The Backend subsystem that issues, validates, and revokes authentication tokens and enforces role-based access.
- **Search_Service**: The Backend subsystem that handles semantic search queries against stored thesis embeddings.
- **Upload_Service**: The Backend subsystem that ingests thesis documents, extracts text, persists files, and triggers AI processing.
- **Similarity_Validator**: The Backend subsystem that compares a candidate title against existing thesis titles and returns similarity scores.
- **Trend_Analyzer**: The Backend subsystem that aggregates topic clusters across the repository and computes trend and gap statistics over time.
- **Repository_Service**: The Backend subsystem that lists, filters, paginates, and exposes thesis records.
- **Analytics_Service**: The Backend subsystem that aggregates repository, user, and AI usage statistics for the dashboard.
- **Directory_Service**: The Backend subsystem that exposes researcher profiles and authored theses.
- **Collection_Service**: The Backend subsystem that manages each user's personal saved-thesis collection.
- **Settings_Service**: The Backend subsystem that persists per-user preferences, including theme, notification settings, and account details.
- **Thesis**: A record consisting of a metadata row (title, authors, year, program, abstract, keywords, status) and an associated uploaded file.
- **Embedding**: A fixed-length numerical vector produced by SBERT representing the semantic content of a thesis title and abstract.
- **Topic_Cluster**: A group of theses produced by clustering embeddings (or TF-IDF vectors) and labeled with representative terms.
- **Research_Gap**: A topic area with low or declining thesis count relative to other areas, computed by the Trend_Analyzer.
- **Student**: An authenticated user with role `student`, able to search, upload (subject to approval), validate titles, save collections, and view analytics.
- **Faculty**: An authenticated user with role `faculty`, with all Student capabilities plus the ability to review and approve student-submitted theses.
- **Administrator**: An authenticated user with role `administrator`, with all Faculty capabilities plus user management, repository moderation, and system configuration.
- **Role**: One of `student`, `faculty`, or `administrator`, assigned to each User.
- **Theme**: A visual mode of the Frontend, either `light` (default) or `dark`.
- **Figma_Design**: The provided Figma prototype for THESYS+, the authoritative reference for layout, typography, color, spacing, and interaction states.
- **Similarity_Score**: A value in the closed interval `[0.0, 1.0]` representing cosine similarity between two embeddings, where `1.0` is identical and `0.0` is unrelated.
- **High_Similarity_Threshold**: The configurable Similarity_Score above which a candidate title is flagged as a likely duplicate. Default value: `0.85`.
- **Moderate_Similarity_Threshold**: The configurable Similarity_Score above which a candidate title is flagged as related but not duplicate. Default value: `0.70`.
- **Module**: One of the ten functional units listed in section "Modules": Authentication, Semantic Search, Thesis Upload + AI Processing, Title Similarity Validation, Topic Trend Analysis, Repository, Analytics Dashboard, Researcher Directory, Saved Collection, Settings.
- **Audit_Log**: A persisted record of security-relevant events (login, role change, thesis approval, deletion, configuration change).

## Requirements

### Requirement 1: Authentication and Role-Based Access

**User Story:** As a PSU CCS user, I want to register, sign in, and access features appropriate to my role, so that the system protects research data and enforces academic workflows.

#### Acceptance Criteria

1. WHEN a visitor submits a registration form with a valid PSU institutional email, full name, role request, and password meeting complexity rules, THE Auth_Service SHALL create a User record with status `pending_verification` and dispatch a verification message.
2. IF a registration submission contains an email already associated with a User, THEN THE Auth_Service SHALL reject the submission with an error indicating the email is already registered.
3. IF a registration password is shorter than 8 characters, lacks at least one letter, or lacks at least one digit, THEN THE Auth_Service SHALL reject the submission with a message identifying which rule failed.
4. WHEN a User submits valid email and password credentials at the login screen, THE Auth_Service SHALL issue an authentication token bound to the User's Role and return the token to the Frontend.
5. IF a login attempt provides an unknown email or an incorrect password, THEN THE Auth_Service SHALL reject the attempt with a generic invalid-credentials message that does not disclose whether the email exists.
6. WHEN the same email fails authentication five consecutive times within a 15-minute window, THE Auth_Service SHALL temporarily lock the account for 15 minutes and record the lockout in the Audit_Log.
7. WHEN an authenticated User requests a Backend endpoint that requires a Role the User does not hold, THE Auth_Service SHALL deny the request with HTTP status 403 and SHALL NOT execute the underlying handler.
8. WHEN a User requests password reset for a registered email, THE Auth_Service SHALL send a single-use, time-limited reset link valid for 60 minutes.
9. WHEN a User submits a logout request, THE Auth_Service SHALL invalidate the User's current token within 5 seconds such that subsequent requests with that token are rejected.
10. THE Auth_Service SHALL support exactly three Roles: `student`, `faculty`, and `administrator`.
11. WHERE a User holds the `administrator` Role, THE Auth_Service SHALL permit the User to change another User's Role and SHALL record the change in the Audit_Log with actor, target, previous Role, new Role, and timestamp.
12. THE Frontend SHALL render the login, registration, and password-reset screens to match the corresponding Figma_Design screens in both light and dark Theme.

### Requirement 2: Semantic Search

**User Story:** As a researcher, I want to search the repository by meaning rather than exact keywords, so that I can discover relevant prior work even when it uses different terminology.

#### Acceptance Criteria

1. WHEN an authenticated User submits a free-text query of at least 3 characters to the search endpoint, THE Search_Service SHALL compute an Embedding of the query and return the top N matching Thesis records ranked by Similarity_Score in descending order, where N is configurable with a default of 20.
2. THE Search_Service SHALL return, for each matched Thesis, at minimum the Thesis identifier, title, authors, year, program, abstract excerpt, keywords, and Similarity_Score.
3. IF a search query is empty or shorter than 3 characters after trimming whitespace, THEN THE Search_Service SHALL reject the request with a validation error and SHALL NOT execute a similarity computation.
4. WHEN a User applies filters for year range, program, or keywords alongside a query, THE Search_Service SHALL restrict results to Thesis records satisfying the filter conjunction before similarity ranking.
5. WHEN a search returns zero results, THE Frontend SHALL render an empty-state matching the Figma_Design and SHALL offer the User the option to broaden filters.
6. THE Search_Service SHALL respond to a search request over a repository of up to 10,000 Thesis records within 2 seconds at the 95th percentile under nominal load.
7. WHERE a search request includes a `page` and `page_size` parameter, THE Search_Service SHALL return paginated results with total count, current page, and total pages metadata.
8. THE Frontend SHALL render the semantic search screen, result cards, filters, and pagination controls to match the Figma_Design in both light and dark Theme.

### Requirement 3: Thesis Upload and AI Processing

**User Story:** As a Student or Faculty member, I want to upload a thesis document and have the system extract metadata and generate embeddings automatically, so that the work becomes searchable without manual indexing.

#### Acceptance Criteria

1. WHEN an authenticated Student or Faculty submits a thesis upload form containing a PDF or DOCX file no larger than 25 MB and required metadata (title, authors, year, program, abstract, keywords), THE Upload_Service SHALL persist the file to File_Storage and create a Thesis record with status `pending_review` if the uploader is a Student, or `approved` if the uploader is a Faculty or Administrator.
2. IF an uploaded file is not a PDF or DOCX, exceeds 25 MB, or fails MIME-type validation, THEN THE Upload_Service SHALL reject the upload with a specific error message and SHALL NOT create a Thesis record.
3. IF a required metadata field is missing or empty after trimming whitespace, THEN THE Upload_Service SHALL reject the upload with a field-level validation error.
4. WHEN a Thesis record is created, THE AI_Service SHALL extract text content from the file, generate an SBERT Embedding from the title and abstract, compute a TF-IDF representation, and persist both with the Thesis identifier.
5. IF text extraction or Embedding generation fails for a Thesis, THEN THE Upload_Service SHALL mark the Thesis with status `processing_failed` and record the error in the Audit_Log without deleting the uploaded file.
6. WHEN a Thesis enters status `processing_failed`, THE Backend SHALL permit an Administrator to retry AI processing without re-uploading the file.
7. WHILE AI processing is in progress for a newly uploaded Thesis, THE Frontend SHALL display a non-blocking progress indicator matching the Figma_Design.
8. WHEN a Faculty or Administrator approves a Thesis with status `pending_review`, THE Upload_Service SHALL transition the Thesis to status `approved` and SHALL record the approver and timestamp in the Audit_Log.
9. WHEN a Faculty or Administrator rejects a Thesis with status `pending_review`, THE Upload_Service SHALL transition the Thesis to status `rejected`, persist the rejection reason, and notify the uploader.
10. THE Upload_Service SHALL only expose Thesis records with status `approved` to non-uploader, non-Faculty, non-Administrator queries against the Repository_Service and Search_Service.
11. THE Frontend SHALL render the upload screen, drag-and-drop area, metadata fields, and progress states to match the Figma_Design in both light and dark Theme.

### Requirement 4: Title Similarity Validation

**User Story:** As a Student proposing a thesis, I want to validate my candidate title against existing theses, so that I can avoid duplicating prior work and refine my topic.

#### Acceptance Criteria

1. WHEN an authenticated User submits a candidate title of at least 5 characters to the validation endpoint, THE Similarity_Validator SHALL compute a Similarity_Score between the candidate and every approved Thesis title and return the top 10 most similar titles with their scores in descending order.
2. WHEN the highest Similarity_Score returned exceeds the High_Similarity_Threshold, THE Similarity_Validator SHALL include a verdict of `likely_duplicate` in the response.
3. WHEN the highest Similarity_Score is greater than the Moderate_Similarity_Threshold and less than or equal to the High_Similarity_Threshold, THE Similarity_Validator SHALL include a verdict of `related` in the response.
4. WHEN the highest Similarity_Score is less than or equal to the Moderate_Similarity_Threshold, THE Similarity_Validator SHALL include a verdict of `distinct` in the response.
5. IF a candidate title is empty or shorter than 5 characters after trimming whitespace, THEN THE Similarity_Validator SHALL reject the request with a validation error.
6. THE Similarity_Validator SHALL respond to a validation request over a repository of up to 10,000 Thesis records within 1.5 seconds at the 95th percentile under nominal load.
7. WHERE an Administrator updates High_Similarity_Threshold or Moderate_Similarity_Threshold, THE Settings_Service SHALL persist the new values and THE Similarity_Validator SHALL apply them to subsequent validations.
8. THE Frontend SHALL render the title-validation screen, score visualization, verdict badge, and matched-titles list to match the Figma_Design in both light and dark Theme.

### Requirement 5: Topic Trend Analysis

**User Story:** As a researcher or administrator, I want to see how thesis topics evolve over time and where research is sparse, so that I can identify trends and gaps for future research.

#### Acceptance Criteria

1. WHEN an authenticated User opens the topic trend screen, THE Trend_Analyzer SHALL return Topic_Cluster summaries for all approved Thesis records, including each cluster's label, representative keywords, member count, and per-year counts.
2. WHEN a User selects a year range filter, THE Trend_Analyzer SHALL restrict cluster computation or aggregation to Thesis records whose year falls within the selected range.
3. WHEN a User selects a program filter, THE Trend_Analyzer SHALL restrict cluster aggregation to Thesis records whose program matches the filter.
4. THE Trend_Analyzer SHALL classify a Topic_Cluster as a Research_Gap when the cluster's three-year rolling member count is in the bottom quartile of all clusters.
5. WHEN the Trend_Analyzer computes Topic_Cluster results, THE Backend SHALL cache the result for at least 15 minutes per filter combination and serve cached results on subsequent matching requests.
6. WHEN a new Thesis is approved, THE Backend SHALL invalidate the affected Trend_Analyzer cache entries within 60 seconds.
7. THE Trend_Analyzer SHALL respond to a trend request over a repository of up to 10,000 Thesis records within 3 seconds at the 95th percentile under nominal load when a cached result is unavailable.
8. THE Frontend SHALL render the trend chart, cluster list, gap indicators, and filter controls to match the Figma_Design in both light and dark Theme.

### Requirement 6: Research Repository

**User Story:** As any authenticated user, I want to browse, filter, and open theses in the repository, so that I can read and reference prior work.

#### Acceptance Criteria

1. WHEN an authenticated User opens the repository screen, THE Repository_Service SHALL return a paginated list of approved Thesis records sorted by upload date in descending order by default.
2. WHEN a User applies filters for year, program, keywords, or author, THE Repository_Service SHALL restrict results to records satisfying the filter conjunction.
3. WHEN a User selects an alternate sort (title ascending, year descending, year ascending), THE Repository_Service SHALL return results in the requested order.
4. WHEN a User opens a Thesis detail view, THE Repository_Service SHALL return the full metadata, authors, abstract, keywords, status, and a download link to the file.
5. WHEN a User clicks the download link of an approved Thesis, THE Backend SHALL stream the original file to the User and SHALL record the download event with User identifier, Thesis identifier, and timestamp.
6. WHERE a User holds the `student` Role, THE Repository_Service SHALL hide Thesis records with status other than `approved` unless the Student is the uploader.
7. WHERE a User holds the `faculty` or `administrator` Role, THE Repository_Service SHALL include Thesis records with status `pending_review` so that the User can review or approve them.
8. WHERE a User holds the `administrator` Role, THE Repository_Service SHALL permit the User to edit metadata of any Thesis or delete a Thesis, recording the action in the Audit_Log.
9. THE Frontend SHALL render the repository list, filter sidebar, sort controls, detail view, and pagination to match the Figma_Design in both light and dark Theme.

### Requirement 7: Analytics Dashboard

**User Story:** As an Administrator or Faculty member, I want a dashboard summarizing repository activity, so that I can monitor adoption and content health.

#### Acceptance Criteria

1. WHEN an authenticated User opens the analytics dashboard, THE Analytics_Service SHALL return aggregated metrics including total approved Thesis count, theses uploaded in the last 30 days, registered User count by Role, top 10 keywords by frequency, top 10 programs by Thesis count, and Thesis count per year for the last 10 years.
2. WHEN a User selects a date range filter, THE Analytics_Service SHALL recompute time-bounded metrics over the selected range.
3. WHERE a User holds the `student` Role, THE Analytics_Service SHALL omit User-count and User-management metrics from the response.
4. WHERE a User holds the `faculty` or `administrator` Role, THE Analytics_Service SHALL include User-count and pending-review metrics in the response.
5. THE Analytics_Service SHALL respond to a dashboard request within 2 seconds at the 95th percentile under nominal load, using cached aggregates with a refresh interval of at most 5 minutes.
6. THE Frontend SHALL render dashboard cards, charts, tables, and Role-conditional sections to match the Figma_Design in both light and dark Theme.

### Requirement 8: Researcher Directory

**User Story:** As a researcher, I want to browse profiles of other researchers and the theses they have authored, so that I can identify collaborators and follow specific authors.

#### Acceptance Criteria

1. WHEN an authenticated User opens the researcher directory, THE Directory_Service SHALL return a paginated list of Users who have at least one approved Thesis, including the User's display name, program, role, and authored Thesis count.
2. WHEN a User opens a researcher profile, THE Directory_Service SHALL return the researcher's display name, program, role, profile bio, and the list of their approved Thesis records.
3. WHEN a User submits a search query against the directory, THE Directory_Service SHALL match the query against User display name, program, and authored Thesis titles and return matching profiles.
4. WHERE a User holds the `administrator` Role, THE Directory_Service SHALL include all registered Users regardless of authored Thesis count.
5. WHEN a User edits their own profile bio or display name, THE Directory_Service SHALL persist the change and reflect it in the directory within 60 seconds.
6. THE Frontend SHALL render the directory list, profile detail, search box, and pagination to match the Figma_Design in both light and dark Theme.

### Requirement 9: Saved Collection

**User Story:** As an authenticated user, I want to save theses to a personal collection, so that I can revisit relevant work without searching again.

#### Acceptance Criteria

1. WHEN an authenticated User clicks "Save" on an approved Thesis, THE Collection_Service SHALL add the Thesis identifier to the User's saved collection and confirm the save in the Frontend.
2. WHEN an authenticated User clicks "Unsave" on a saved Thesis, THE Collection_Service SHALL remove the Thesis identifier from the User's saved collection.
3. WHEN a User opens the saved collection screen, THE Collection_Service SHALL return the list of saved Thesis records with full metadata, sorted by save date in descending order by default.
4. IF a User attempts to save a Thesis identifier that is already in the User's saved collection, THEN THE Collection_Service SHALL treat the operation as idempotent and return the existing collection state without creating a duplicate entry.
5. IF a User attempts to save a Thesis whose status is not `approved`, THEN THE Collection_Service SHALL reject the operation with a validation error.
6. WHEN a Thesis in a User's saved collection is deleted by an Administrator, THE Collection_Service SHALL remove the corresponding entry from the saved collection within 60 seconds.
7. THE Frontend SHALL render the saved-collection screen, save/unsave controls, and empty state to match the Figma_Design in both light and dark Theme.

### Requirement 10: Settings

**User Story:** As an authenticated user, I want to manage my account preferences, including theme and notification settings, so that the system fits my working style.

#### Acceptance Criteria

1. THE Settings_Service SHALL persist per-User preferences including Theme (`light` or `dark`), language, email-notification opt-in flags, and display name.
2. WHEN a User changes Theme in the settings screen, THE Frontend SHALL apply the new Theme immediately without a full page reload and THE Settings_Service SHALL persist the new Theme within 5 seconds.
3. WHEN a User updates their password from the settings screen, THE Auth_Service SHALL require the current password, validate the new password against complexity rules from Requirement 1.3, and on success invalidate all other active tokens for the User.
4. WHERE a User holds the `administrator` Role, THE Settings_Service SHALL expose system-wide configuration including High_Similarity_Threshold, Moderate_Similarity_Threshold, search default page size, and analytics cache refresh interval.
5. WHEN an Administrator changes a system-wide configuration value, THE Backend SHALL apply the new value to subsequent operations and SHALL record the change in the Audit_Log.
6. WHEN a User opens the settings screen for the first time after registration, THE Frontend SHALL default Theme to `light`.
7. THE Frontend SHALL render the settings screen, tabs, toggles, and Role-conditional sections to match the Figma_Design in both light and dark Theme.

### Requirement 11: Theming and Figma Design Compliance

**User Story:** As any user of THESYS+, I want the interface to match the approved Figma design in both light and dark mode, so that the experience is consistent with the academic brand and the prototype.

#### Acceptance Criteria

1. THE Frontend SHALL implement exactly two Themes: `light` (default) and `dark`.
2. WHEN a User toggles Theme from any screen that exposes the toggle, THE Frontend SHALL apply the new Theme to all rendered components within 200 ms.
3. THE Frontend SHALL source colors, typography, spacing, border radii, shadows, and iconography from a centralized theme token set derived from the Figma_Design.
4. THE Frontend SHALL render every screen listed in the Figma_Design (landing, login, registration, semantic search, upload, title similarity validation, topic trend analysis, research repository, repository detail, analytics dashboard, researcher directory, researcher profile, saved collection, settings) with layouts, components, states (default, hover, focus, disabled, loading, empty, error), and copy that match the Figma_Design.
5. WHERE the Figma_Design specifies a particular component variant for a Role, THE Frontend SHALL render the variant matching the active User's Role.
6. THE Frontend SHALL achieve a Lighthouse accessibility score of at least 90 in both light and dark Theme on each Figma-defined screen.
7. THE Frontend SHALL render correctly without horizontal scroll at viewport widths from 1280 px down to 360 px on the screens that the Figma_Design specifies as responsive.

### Requirement 12: Modular and Extensible Architecture

**User Story:** As a maintainer, I want the system to be organized into independent modules with clear interfaces, so that future modules can be added without rewriting existing ones.

#### Acceptance Criteria

1. THE Backend SHALL organize each Module from the Glossary into an independently deployable Django app or package with its own models, serializers, views, URL routes, services, and tests.
2. THE Frontend SHALL organize each Module into an independent feature folder containing its components, hooks, API client, and routes.
3. THE Backend SHALL expose all Module functionality through versioned REST endpoints under a path prefix (for example `/api/v1/`) and SHALL preserve backward compatibility within a major version.
4. THE AI_Service SHALL expose a stable internal interface (for example `embed(text)`, `similarity(a, b)`, `cluster(corpus)`) that hides the choice of model and library, so that SBERT can be replaced or augmented without changing callers.
5. WHEN a new Module is added, THE Backend SHALL allow registration without modifying unrelated Modules, except for routing registration in a single composition root.
6. THE Frontend SHALL load Module routes via code-splitting so that adding a new Module does not increase the initial JavaScript bundle of unrelated screens.
7. THE Backend SHALL define database migrations per Module, and migrations of one Module SHALL NOT depend on internal tables of another Module beyond documented foreign-key relationships.

### Requirement 13: Performance and Scalability

**User Story:** As a user, I want the system to remain fast as the repository grows, so that semantic search, validation, and trend analysis stay responsive at scale.

#### Acceptance Criteria

1. THE Backend SHALL persist Embedding vectors in a form that supports indexed nearest-neighbor lookup (for example pgvector or an equivalent index), and SHALL NOT require full-table scans for similarity queries on repositories larger than 1,000 Thesis records.
2. THE Search_Service, Similarity_Validator, and Trend_Analyzer SHALL meet the per-Module 95th-percentile latency targets in Requirements 2.6, 4.6, and 5.7 at a repository size of 10,000 Thesis records.
3. THE Backend SHALL execute SBERT Embedding generation asynchronously (for example via a task queue) when the synchronous request would exceed 2 seconds, and SHALL return an acknowledgement response with a job identifier.
4. WHEN concurrent upload requests arrive, THE Backend SHALL process them without losing files or metadata up to 20 concurrent uploads on the reference deployment.
5. THE Backend SHALL paginate every list endpoint with a configurable page size, with a default of 20 and a maximum of 100 records per page.
6. THE Backend SHALL cache idempotent read endpoints (search, repository list, analytics dashboard, trend analysis) with a configurable TTL and SHALL invalidate caches on relevant write events as specified in module-level requirements.
7. THE Backend SHALL run AI Embedding and clustering workloads on a process or worker that can be scaled horizontally and independently of the request-serving Backend process.
8. THE Database SHALL define indexes on Thesis(year, program), Thesis(status), User(email), and saved-collection(user_id, thesis_id), and on Embedding lookup keys.

### Requirement 14: Security, Privacy, and Auditability

**User Story:** As an administrator, I want sensitive data protected and meaningful actions audited, so that the system is trustworthy and recoverable.

#### Acceptance Criteria

1. THE Auth_Service SHALL store User passwords using a salted, adaptive hash function (for example Argon2 or bcrypt) and SHALL NOT store plaintext passwords.
2. THE Backend SHALL serve all endpoints exclusively over HTTPS in production and SHALL reject plaintext HTTP requests with a redirect or rejection.
3. THE Backend SHALL validate and sanitize all User-supplied input on every endpoint to prevent SQL injection, command injection, and stored cross-site scripting.
4. THE Backend SHALL set Cross-Origin Resource Sharing rules that allow only the configured Frontend origin in production.
5. WHEN any of the following events occurs, THE Backend SHALL append a record to the Audit_Log with actor, action, target, and timestamp: login success, login failure, password change, Role change, Thesis approval, Thesis rejection, Thesis deletion, configuration change.
6. THE Backend SHALL retain Audit_Log entries for at least 12 months and SHALL expose a query interface restricted to the `administrator` Role.
7. WHERE a User requests deletion of their account, THE Backend SHALL anonymize the User's personal data (name, email, bio) while preserving the integrity of authored Thesis records and Audit_Log entries.

### Requirement 15: Observability and Operability

**User Story:** As an operator, I want logs, metrics, and health checks, so that I can detect, diagnose, and resolve issues.

#### Acceptance Criteria

1. THE Backend SHALL expose a health-check endpoint that returns the status of the Database, File_Storage, and AI_Service dependencies.
2. THE Backend SHALL emit structured logs for every HTTP request including method, path, User identifier when authenticated, status code, and duration in milliseconds.
3. WHEN an unhandled exception occurs in the Backend, THE Backend SHALL log the exception with stack trace and SHALL return an error response that does not include the stack trace.
4. THE Backend SHALL emit a metric for AI_Service operation duration (embedding, similarity, clustering) per operation type.
5. THE Frontend SHALL surface a user-friendly error state for any Backend response with status 5xx, matching the Figma_Design error states.

### Requirement 16: Internationalization and Localization Readiness

**User Story:** As a future maintainer, I want the Frontend prepared for additional languages, so that the system can be localized without refactoring components.

#### Acceptance Criteria

1. THE Frontend SHALL externalize all user-facing strings into a translation resource accessed through a translation function rather than hard-coding strings inside components.
2. WHERE a User selects a language in Settings, THE Frontend SHALL load the corresponding translation resource and apply it to all rendered components.
3. THE Frontend SHALL default to English when no language preference is set or the selected language resource is unavailable.
