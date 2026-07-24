# Phase 0 Research: Online Casino Competitive Intelligence Database

All Technical Context items in `plan.md` are resolved below — no `NEEDS CLARIFICATION` markers remain. Where the source requirements document (`online-casino-competitive-intelligence-requirements.md`) already gives a direct recommendation, that recommendation is adopted as the primary decision, since the user explicitly directed this plan to follow it; remaining engineering choices it leaves open ("the coding agent may choose alternatives") are resolved here with rationale.

## 1. Language and runtime

- **Decision**: Python 3.12+.
- **Rationale**: Directly specified in source doc §11.2. Mature ecosystem for HTTP fetching, HTML/PDF/XLSX parsing, and both the Google Sheets and Drive client libraries are first-class in Python. Team-neutral choice for a data/ingestion tool that other coding agents will also need to extend.
- **Alternatives considered**: Node.js/TypeScript (weaker native PDF/table-extraction ecosystem for this use case); Go (fast, but far thinner ecosystem for HTML/PDF parsing and no direct benefit here since this is not a high-concurrency service).

## 2. Sheets/Drive access library

- **Decision**: `google-api-python-client` + `google-auth` (service-account credentials) for direct Sheets API v4 (`spreadsheets.batchUpdate`, `values.batchGet`/`batchUpdate`) and Drive API v3 access, wrapped in a thin internal client (`casino_intel.sheets`, `casino_intel.drive`).
- **Rationale**: The spec requires named ranges, data validation, protected ranges/columns, conditional formatting, and frozen headers/filters (FR-041, FR-042; source doc §17.1) — these are native Sheets API v4 features. The higher-level `gspread` library wraps only a subset of them comfortably and would still require raw API calls for formatting/protection/validation, so using the raw client directly avoids a leaky abstraction.
- **Alternatives considered**: `gspread` (simpler day-one ergonomics for basic reads/appends, but insufficient coverage of validation/protection/formatting features without dropping to raw API anyway — rejected to avoid two overlapping access paths).

## 3. Identifier scheme

- **Decision**: ULIDs (`python-ulid`), formatted with the entity-type prefix shown in the source doc (`brand_01J...`, `operator_01J...`, `source_01J...`, `obs_01J...`, `audit_01J...`, etc.).
- **Rationale**: Matches the exact ID shape given in source doc §6. ULIDs are lexicographically sortable by creation time (useful for change-log ordering and cache invalidation) and collision-resistant across concurrent local runs, satisfying FR-002's "stable, unique, immutable" requirement without a central sequence.
- **Alternatives considered**: UUIDv4 (also explicitly allowed by the doc, but not time-sortable, which is useful for cache/log ordering); auto-incrementing integers (explicitly prohibited — spec forbids row-number-like keys).

## 4. HTML parsing

- **Decision**: `beautifulsoup4` with the `lxml` parser backend as the default HTML/table extractor.
- **Rationale**: Named directly in source doc §11.2 as a first option. Mature, forgiving of malformed regulator/operator markup, and integrates cleanly with `pandas.read_html` for tabular regulator data (e.g. UKGC HTML tables).
- **Alternatives considered**: `selectolax` (faster, also named in the doc as an alternative) — rejected as the default because its stricter/faster parser is less forgiving of the inconsistent markup expected from a long tail of brand/affiliate sites; kept as a documented fallback for high-volume, well-formed pages if performance becomes an issue post-pilot.

## 5. PDF parsing

- **Decision**: `PyMuPDF` (`fitz`) for native text extraction; `pdfplumber` for table extraction where annual reports present tabular KPI data. OCR (e.g. `pytesseract`) is not included in the MVP dependency set and is invoked only as an explicit, manually-triggered last resort per source doc §11.2 ("OCR should be a last resort").
- **Rationale**: PyMuPDF is fast and reliable for native (non-scanned) PDF text, which covers the large majority of regulator statistics and listed-operator annual reports. `pdfplumber` has stronger table-structure detection than PyMuPDF alone, matching the doc's guidance to select "a table extraction library... per document" (§11.2) while keeping the default toolchain small.
- **Alternatives considered**: `pypdf` (also named in the doc; lighter-weight but weaker layout/table fidelity than PyMuPDF — kept as a fallback dependency, not the default); Camelot/Tabula (heavier Java/ghostscript dependencies for marginal gain over pdfplumber at pilot scale — rejected for MVP).

## 6. Structured file parsing (CSV/XLSX)

- **Decision**: `pandas` + `openpyxl` engine for XLSX; `pandas.read_csv` for CSV.
- **Rationale**: Directly specified in source doc §11.2; handles UKGC downloadable spreadsheets, traffic-tool exports, and Google Trends CSV exports with one consistent toolchain feeding the same downstream `normalisation`/`validation` modules as HTML/PDF extraction.
- **Alternatives considered**: `polars` (faster on large files, but the pilot's file sizes do not warrant the added dependency/API surface; `pandas` has broader `openpyxl`/ecosystem compatibility for the doc's XLSX ingestion requirement).

## 7. Dynamic page capture (screenshots, rendered brand journeys)

- **Decision**: Playwright, used only for the human-guided UX/brand audit capture flow (homepage, lobby, promotions, registration-up-to-stop-point, footer/licence, responsible-gambling screenshots) and only where permitted by source terms.
- **Rationale**: Directly specified in source doc §11.2 ("Playwright for permitted dynamic-page capture"). Needed because brand-website UX auditing requires rendering JavaScript-heavy casino lobby pages that static fetchers cannot capture faithfully.
- **Alternatives considered**: Selenium (heavier, older API, no material benefit for this scope); manual screenshot capture only (rejected as the sole method — insufficiently repeatable across the 15–20 brand pilot and quarterly re-audits, though manual capture remains supported as a fallback per FR-032).

## 8. HTTP fetching, retries and rate limiting

- **Decision**: `httpx` for HTTP requests, `tenacity` for retry/exponential-backoff policies, with a per-domain rate limiter and an explicit robots/terms check step before any fetch.
- **Rationale**: Both named directly in source doc §11.2. `httpx` supports both sync and async use if the fetcher needs to parallelise across many due sources later, and `tenacity`'s declarative retry decorators match the doc's "implement retries with exponential backoff" requirement (§17.1) for both HTTP fetches and Sheets API calls.
- **Alternatives considered**: `requests` (no native async path, would need a separate async fetcher later if throughput becomes a concern — `httpx` avoids that migration).

## 9. CLI framework

- **Decision**: Typer.
- **Rationale**: The source doc specifies a `casino-intel <command> [options]` CLI surface (§19) with structured subcommands (`initialise-workbook`, `add-source`, `fetch-source`, `ingest-source`, `import-file`, `validate`, `derive`, `refresh-summary`, `export`, `research-queue list|run`) and a mandatory `--dry-run` mode on mutating commands. Typer gives typed, self-documenting subcommands with minimal boilerplate and built-in `--help` generation, and composes cleanly with Pydantic models already used for the data layer.
- **Alternatives considered**: `argparse` (stdlib-only, but far more boilerplate for a ~10-command nested CLI with shared options like `--dry-run`); `click` directly (Typer is built on Click and gets the same capability with better ergonomics for this size of CLI).

## 10. Local run-state cache

- **Decision**: A local, disposable SQLite database storing observation fingerprints (per §11.4) and document content hashes, used purely to make idempotency/dedup checks fast without re-reading the full `Observations` sheet on every run. It is rebuildable at any time from the Sheets workbook and Drive archive and is never treated as authoritative.
- **Rationale**: Source doc explicitly allows "optional SQLite cache for local execution state" (§11.2) and requires idempotent re-ingestion (§11.4, FR-018). Without a local index, checking "has this exact fingerprint already been written?" against a growing Sheets-based fact table would require increasingly expensive full-sheet reads as the pilot scales toward the stated 50k–100k row migration trigger (§23).
- **Alternatives considered**: No cache, re-reading `Observations` via the Sheets API on every run (simpler, but does not scale even within pilot volumes once monthly ingestion accumulates history, and burns API quota); a hosted cache/queue (unjustified operational overhead for an MVP whose explicit design principle is "low operational overhead," §1).

## 11. Controlled-vocabulary and metric-definition authority

- **Decision**: Versioned YAML files in `config/` (`vocabularies.yaml`, `metrics.yaml`, `audit-rubrics.yaml`, `sources.yaml`) are the repository-tracked baseline, loaded into the `Config` sheet by `initialise-workbook`. After initialisation, the `Config` sheet is the runtime source of truth that ingestion and validation read from directly (satisfying FR-009's "must expose them for inspection and amendment" in the workbook itself); an `export-config` path allows syncing human edits back to the repository for version history.
- **Rationale**: Source doc §8 requires vocabularies to be inspectable/amendable in the workbook, not hidden in code — but also implies a need for versioned, reviewable definitions (metric definitions carry `formula_version`/rubric version fields throughout). A repo-seeded, sheet-authoritative-at-runtime model satisfies both: humans edit in the workbook day-to-day, while the repo retains a diffable historical baseline.
- **Alternatives considered**: Code-only enums (explicitly prohibited by §8); Sheet-only with no repo seed (would leave no versioned baseline for `initialise-workbook` on a fresh workbook, and no diffable history for schema/metric changes as required by §17.3).

## 12. Secrets and credentials

- **Decision**: Google service-account JSON key referenced via an environment variable (`GOOGLE_APPLICATION_CREDENTIALS`) loaded from a local `.env` (excluded from version control; `.env.example` documents required variables), never written into the workbook or repository.
- **Rationale**: Directly required by FR-050 and source doc §16 ("use service-account or OAuth credentials stored outside the workbook," "avoid storing secrets in Sheets"). Service-account auth (vs. interactive OAuth) suits an unattended/CLI-triggered pipeline better since there is no interactive user present for OAuth consent on every run.
- **Alternatives considered**: OAuth2 user-consent flow (better fits a human interactively using the CLI on their own account, but adds token-refresh complexity for a tool meant to also run unattended for scheduled ingestion later; rejected for MVP simplicity, may be added later as an alternative auth mode).

## 13. Testing strategy

- **Decision**: pytest for unit and integration tests; golden fixtures under `tests/fixtures/` (UKGC XLSX, an operator annual-report PDF excerpt, promotion-terms HTML, a traffic-tool CSV export, a Google Trends CSV export, an app-store capture, and a UX-audit JSON payload) so parser/extractor tests do not depend on live network access, per source doc §20.3.
- **Rationale**: Directly specified in source doc §11.2 and §20. Golden fixtures make ingestion determinism testable even as external pages change over time, directly supporting SC-004/SC-005 (multi-format ingestion, zero-duplicate re-runs).
- **Alternatives considered**: Live-network integration tests only (rejected — explicitly warned against in §20.3 since "external pages may change").

## 14. Formula-injection protection

- **Decision**: Any text value written to a cell that starts with `=`, `+`, `-`, or `@` is prefixed with a leading apostrophe (or written via the Sheets API's `USER_ENTERED`→`RAW` value-input distinction, forcing literal string interpretation) before being sent through the Sheets client wrapper — enforced centrally in the `sheets` write path, not per-caller.
- **Rationale**: Directly required by FR-042 and source doc §17.1. Centralising the escape in the write path (rather than in each ingestion/extraction module) guarantees no caller can bypass it, which is important given the extraction module is regularly writing untrusted third-party text (offer headlines, review themes, brand descriptions).
- **Alternatives considered**: Escaping at extraction time only (rejected — leaves a gap for any future write path that does not go through extraction, e.g. manual corrections or the audit workflow).

## 15. Idempotency / deduplication fingerprint

- **Decision**: Adopt the fingerprint fields specified in source doc §11.4 verbatim — `subject_id, metric_id, period_start, period_end, as_of_date, geography, segment, source_id, raw_value` hashed (SHA-256) into a single fingerprint stored alongside each observation and indexed in the local SQLite cache.
- **Rationale**: This is an explicit, already-well-specified design decision in the source document; adopting it directly satisfies FR-004/FR-018/SC-005 and keeps ingestion runs idempotent against unchanged sources without inventing a competing scheme.
- **Alternatives considered**: None — the source document's fingerprint definition is adopted as-is.

## 16. Derived-metric calculation scope for MVP

- **Decision**: Implement exactly the calculations enumerated in source doc §9.18 ("Initial calculations"): revenue per active customer, GGY per average monthly active account, marketing expense as % of revenue, adjusted EBITDA margin, traffic growth YoY, share of search, and indicative CPA range (multi-input, assumption-driven, no single mandatory formula).
- **Rationale**: These map directly to FR-035–FR-037 and are the only derived metrics the spec commits to for MVP acceptance; scope creep into a general-purpose formula engine is not justified by the spec's stated acceptance criteria.
- **Alternatives considered**: A generic, user-configurable formula engine over arbitrary metric combinations (rejected as premature — spec's Assumptions explicitly scope this to a fixed initial set, and comparability/definition-compatibility checks are easier to keep correct over a small, known formula set).

## 17. Future PostgreSQL migration alignment

- **Decision**: Design `data-model.md` entities to map 1:1 onto the table list given in source doc §23 (`operators`, `brands`, `brand_operator_relationships`, `licences`, `sources`, `documents`, `metric_definitions`, `observations`, `offers`, `audits`, `research_tasks`, `ingestion_runs`, `data_quality_issues`, `change_events`), even though PostgreSQL itself is out of scope for this feature.
- **Rationale**: Explicit, non-negotiable design principle in the spec (design principle §3.6, "Design for migration") and source doc §23. Verifying the mapping now avoids a costly reshape later and costs nothing extra in the MVP.
- **Alternatives considered**: Designing the Sheets schema independently and reconciling with a relational schema at migration time (rejected — directly contradicts the stated design principle and risks accumulating Sheets-specific modeling shortcuts that are expensive to unwind later).
