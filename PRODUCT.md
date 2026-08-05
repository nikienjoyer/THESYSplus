# Product

## Register

product

---

## Project Identity

**Name:** THESYS+
**Full Title:** THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend Analysis System
**Institution:** Pampanga State University — College of Computing Studies (CCS)
**Scope:** CCS undergraduate thesis management, retrieval, and research intelligence
**Repository size:** 115 theses, 104 semantic-ready, 8 research clusters (as of prototype defense)

---

## Product Vision

THESYS+ is the institutional research memory of PampangaStateU CCS. It preserves every undergraduate thesis, makes them findable by meaning rather than exact keywords, and turns the accumulated body of student research into actionable intelligence: which topics have been exhausted, which are emerging, and which remain unexplored.

It is a tool for intellectual work. It should feel rigorous, trustworthy, and at home in an academic environment — not like a consumer app or a SaaS startup dashboard.

---

## Users

### Student (Primary)
- BSIS, BSIT, BSCS, or ACT undergraduate student at PampangaStateU CCS
- Arriving at the beginning of a thesis proposal, needing to verify their topic is original
- Using Title Similarity Validation before investing months in a direction already explored
- Browsing the Repository to find related literature and build their own context
- Uploading a completed thesis once approved by their panel and adviser
- **Job to be done:** "Make sure my thesis topic hasn't been done before, find what has been done, and submit my work when it's ready."
- **Context:** Often on a phone, sometimes on a slow campus connection, under deadline pressure, unfamiliar with academic database tools

### Faculty (Secondary)
- Thesis adviser or panel member at CCS
- Reviewing submitted theses in the approval workflow
- Using Trend Analysis to advise students away from saturated topics
- Using Analytics to understand the research output of their department over time
- **Job to be done:** "Guide students to original research directions and maintain the quality of the institutional repository."
- **Context:** Desktop or laptop, working during office hours, needs to trust the system's methodology to make advising decisions with confidence

### Administrator (Tertiary)
- CCS department staff or IT administrator
- Managing user accounts, approving access requests, overseeing repository health
- Monitoring pending submissions and embedding status
- **Job to be done:** "Keep the system's data clean, users properly provisioned, and the repository current."
- **Context:** Desktop, low frequency of use, needs efficient batch management

---

## Product Purpose

THESYS+ solves three problems that PampangaStateU CCS previously had no systematic answer to:

1. **Topic duplication.** Students proposed and researched topics that had already been completed, wasting time and supervisor effort. Title Similarity Validation prevents this with a semantic check against the full thesis corpus.

2. **Inaccessible institutional knowledge.** Completed theses were physically archived or scattered. The Repository makes every approved thesis searchable by semantic meaning, not just exact title matches.

3. **Invisible research patterns.** Faculty had no way to see which research areas the department had exhausted and which were underserved. Topic Trend Analysis surfaces this from the corpus automatically.

Success is: a student can arrive at THESYS+, check whether their thesis title has semantic overlap with existing work, browse related studies, and submit their final thesis — all within a session — without needing institutional intermediaries.

---

## Brand Personality

**Three words:** Rigorous. Precise. Grounded.

**Tone:** Authoritative without being cold. Clear without being sparse. The system should feel like a well-maintained institutional library, not a consumer app.

**Voice:**
- Factual and specific. When a semantic score is 78.4%, say 78.4%, not "highly similar." When a cluster has 12 theses, name the count.
- Supportive without being chatty. Guidance is there when needed; it does not narrate the obvious.
- Never promotional. THESYS+ does not "empower researchers" or "unlock insights." It indexes theses, compares titles, and clusters topics. That is enough.

**Emotional goal for students:** Confidence that their proposed topic is original, and that they have seen the full landscape before committing.

**Emotional goal for faculty:** Trust that the system's AI outputs are methodologically sound and current.

**Emotional goal for administrators:** Reliability — the system works, the data is clean, edge cases are handled.

---

## Academic and Institutional Positioning

THESYS+ is a departmental system before it is a software product. It belongs to PampangaStateU CCS the way the library catalogue belongs to the library. This positioning has visual and UX implications:

- The institution's identity should be visible and legible. PampangaStateU CCS is not a footnote.
- The system's AI methodology should be documented and credible, not marketed. Researchers distrust black boxes.
- The approval workflow exists for academic quality control, not bureaucracy. The UI should communicate its purpose, not just its mechanics.
- Data provenance matters. Users should know when the corpus was last updated and how many theses are searchable.

THESYS+ occupies the intersection of library science, academic integrity, and research intelligence. Its aesthetic should acknowledge all three.

---

## What THESYS+ Is

- A thesis repository with semantic full-text search powered by SBERT
- A title originality checker that compares proposed topics against the full institutional corpus
- A research trend analyzer that surfaces saturated, emerging, and underexplored topic areas
- A structured submission and approval workflow for new theses
- A departmental analytics tool for understanding research output over time
- An institutional system — owned, operated, and trusted by PampangaStateU CCS

---

## What THESYS+ Is Not

- A general-purpose academic search engine (it covers CCS undergraduate theses only)
- A plagiarism checker (it compares semantic topic overlap, not content duplication)
- A citation manager or reference organizer
- A document collaboration or commenting tool
- A publication or preprint system
- A social platform (no public profiles, no following, no engagement metrics)
- A marketing product (there are no conversion goals, no upsells, no growth metrics)

---

## Key Workflows

### Student: Validate a thesis title before proposing
1. Navigate to Title Similarity Validation
2. Enter proposed title or upload a proposal document
3. Review the similarity score and the list of semantically related existing theses
4. Inspect the term analysis (shared vs. distinctive terms)
5. Decide to proceed with the title, revise it, or choose a different direction

### Student: Browse and retrieve relevant literature
1. Navigate to the Repository
2. Enter a conceptual search query (or browse without a query)
3. Set a similarity threshold appropriate for the search intent
4. Open a thesis detail page
5. Read the abstract, review keywords, and download the document if needed

### Student: Submit a completed thesis
1. Navigate to Upload Thesis
2. Fill in metadata (title, abstract, authors, keywords, program, year, adviser)
3. Attach the thesis document (PDF or DOCX)
4. Submit; receive confirmation that the thesis is awaiting faculty review

### Faculty: Review and approve a submitted thesis
1. Access the pending review queue (Django Admin or repository filter)
2. Review the submitted metadata and document
3. Approve (thesis becomes searchable) or reject with a written reason
4. Approved theses automatically receive SBERT embeddings

### Faculty/Student: Identify research gaps
1. Navigate to Trend Analysis
2. Review topic clusters and their saturation status
3. Identify UNDEREXPLORED (🟢) clusters as potential research directions
4. Identify SATURATED (🔴) clusters to advise students away from
5. Cross-reference with the Analytics Dashboard for program- and year-level breakdowns

### Administrator: Provision a new user
1. Review a submitted access request
2. Approve or reject with appropriate role assignment
3. User receives credentials and can log in

---

## Success Metrics

**For students:**
- A student can complete a title similarity check within 2 minutes of arriving at the page
- A student receives a clear recommendation (proceed / revise / reconsider) without needing to interpret a raw score
- A student's thesis upload succeeds on first attempt with correctly formatted metadata

**For faculty:**
- A faculty member can identify the top 3 saturated research areas in 30 seconds from the Trend Analysis page
- A faculty adviser can locate a specific submitted thesis by student name or keyword in under one search interaction

**For the repository:**
- 100% of approved theses have semantic embeddings (embedding coverage = semantic ready count / approved count)
- Repository contents are discoverable within one day of approval
- No duplicate thesis records exist (enforced by SHA256 + title deduplication)

**For the defense:**
- Semantic search returns topically relevant results for research-domain queries (e.g., "RFID attendance monitoring" retrieves RFID-related theses above a 60% threshold)
- Title similarity correctly flags near-duplicate titles at ≥ 65% cosine similarity
- Trend analysis clusters visibly reflect year-over-year topic evolution in the seeded corpus

---

## Design Principles

### 1. Show the methodology, earn the trust
Every AI output — a similarity score, a cluster label, a trend classification — should be accompanied by enough context for an academic to evaluate it. Scores without explanation are marketing. Scores with threshold definitions, term analysis, and methodology notes are scholarship.

### 2. The corpus is the product
THESYS+ is only as valuable as the theses it contains. The UI should surface corpus health (total indexed, semantic-ready count, last updated, coverage years) rather than hiding it. Administrators and faculty should never wonder whether the data they are seeing is current.

### 3. Simplicity for students, depth for faculty
Students need to accomplish a single task quickly and confidently. Faculty need to dig into data and make comparative judgments. The same interface must serve both without forcing students through layers designed for faculty, or stripping faculty of the depth they need.

### 4. Institutional ownership, not product identity
Every visual decision should reinforce that this system belongs to PampangaStateU CCS. The institution is not a footnote. Its name, its department, its academic context are the frame within which everything else operates.

### 5. Precision in language
The system deals with academic work. Copy must be exact. "Highly Similar" means ≥ 85% cosine similarity — say so. "Saturated" means 5 or more theses in a cluster — say so. Approximations and vague qualifiers undermine academic credibility.

---

## Anti-References

These are specific patterns and aesthetics that THESYS+ must not evoke:

- **Generic AI SaaS landing pages** — pulsing badge + giant clamp-scaled product name + grid background with radial glow + hero metric counters + 2×2 identical feature cards. This is the default AI product template of 2024–2025. THESYS+ is an institutional academic tool, not a startup.
- **Tailwind UI starter templates** — the blue-600 button, slate-50 background, white card, gray-500 muted text combination. Zero brand identity; signals "tutorial project" to anyone who recognizes it.
- **Consumer app aesthetics** — gamification, engagement streaks, celebration animations, social proof counters. Academic tools operate on different trust mechanics.
- **Dark-mode-with-purple-gradients** — the developer tool aesthetic (purple accent on deep navy with gradient glow). Looks like a code editor, not a research platform.
- **Dashboard-as-default** — treating every page as a metrics dashboard with stat card grids, progress rings, and KPI counters. Most pages in THESYS+ are research and reading interfaces, not monitoring dashboards.
- **Overly minimal academic portals** — the 2010-era university system aesthetic: white background, Times New Roman, gray table borders, no visual hierarchy. Functional but conveys institutional neglect, not institutional quality.

The right aesthetic is closer to a well-designed institutional digital library: disciplined, legible, typographically considered, clearly organized, and obviously maintained.

---

## Accessibility and Inclusion

- **Target:** WCAG 2.1 AA compliance
- **Known risk areas:** Text contrast in dark mode (currently text-gray-500 on #080d24 fails AA for body-size text), chart accessibility (SVG charts currently lack role="img" and aria-label), mobile focus trapping on the navigation drawer
- **Population:** Students using mobile devices on campus Wi-Fi; faculty on desktop; potential users with reading difficulties (academic text is already demanding — the interface should not add cognitive load)
- **Motion:** Respect `prefers-reduced-motion` for all transitions and skeleton animations
- **Color:** Do not rely on color alone to convey status (the existing emoji + color chip pattern for 🔴/🟡/🟢 is correct — maintain it)
- **Touch targets:** Mobile nav items and action buttons must meet 44×44px minimum
- **Language:** Philippine English is the primary language. Technical terminology (SBERT, cosine similarity, TF-IDF) should be explained on first use for student-facing surfaces

---

## Technology Constraints

These are fixed and must not be changed by design decisions:

- SBERT model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU-friendly)
- Cosine similarity as the ranking metric — no dot-product shortcuts or approximate nearest neighbor at current scale
- TF-IDF + K-Means for topic clustering — algorithm is not replaceable without new training data
- Django REST Framework backend — API contract is stable
- JWT authentication (access + refresh tokens)
- PostgreSQL — JSONB for embedding vectors (no pgvector dependency at current scale)
- React + Vite + Tailwind frontend — no framework migration
- No external chart libraries — inline SVG charts only (established pattern)
- Thesis files: PDF and DOCX only, max 25 MB
- Program options are fixed: BSIS, BSIT, BSCS, ACT (no free-text program field)
