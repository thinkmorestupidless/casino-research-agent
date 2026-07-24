---

description: "Task list for Online Casino Competitive Intelligence Database"
---

# Tasks: Online Casino Competitive Intelligence Database

**Input**: Design documents from `/specs/001-casino-competitive-intelligence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Not explicitly requested as TDD in the spec. Automated tests are included only where research.md/plan.md already commit to them as an explicit design decision (pytest + golden fixtures, decision #13) or where a correctness guarantee (idempotency, formula-injection, append-only) is otherwise unverifiable — these appear as regular implementation tasks, not a test-first gate.

**Organization**: Tasks are grouped by user story (from spec.md) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Maps the task to US1–US5 from spec.md
- File paths are relative to the repository root, per the structure in `plan.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository scaffolding and seed configuration

- [X] T001 Create the repository structure exactly as specified in `plan.md` (`src/casino_intel/{models,sheets,drive,fetching,parsing,extraction,normalisation,validation,derivation,reporting,cli}/`, `tests/{unit,integration,fixtures}/`, `scripts/`, `config/`, `docs/`)
- [X] T002 Initialize `pyproject.toml` for Python 3.12+ with dependencies: `pydantic>=2`, `google-api-python-client`, `google-auth`, `httpx`, `tenacity`, `beautifulsoup4`, `lxml`, `pandas`, `openpyxl`, `PyMuPDF`, `pdfplumber`, `python-ulid`, `playwright`, `typer`, `structlog`, `pytest`
- [X] T003 [P] Configure linting/formatting (`ruff`, `black`) in `pyproject.toml` and add a pre-commit config
- [X] T004 [P] Create `.env.example` documenting `GOOGLE_APPLICATION_CREDENTIALS` and `SPREADSHEET_ID`
- [X] T005 [P] Create `config/vocabularies.yaml` seeding all controlled vocabularies from spec §8/FR-009 (countries, currencies, evidence types, confidence values, review statuses, source types, product verticals, acquisition channels, offer types, device types, audit score range, operator ownership type, brand status, licence status, comparability status, units)
- [X] T006 [P] Create `config/metrics.yaml` seeding the initial metric-definition registry (all metrics listed in `data-model.md`'s Observation section: market, operator-financial, customer, traffic/awareness, app, reputation and UX metric catalogues), each with `metric_id`, `display_name`, `subject_types`, `data_type`, `allowed_units`, `comparability_group`, `aggregation` behaviour, and `caveats`
- [X] T007 [P] Create `config/audit-rubrics.yaml` seeding the UX and brand audit 1–5 rubric definitions (per-dimension scoring criteria, e.g. the `promotion_clarity_score` rubric in source doc §9.14) with an initial `rubric_version`
- [X] T008 [P] Create `config/sources.yaml` seeding known regulator/operator source entries (UKGC annual industry statistics, market overview, gambling business data pages per source doc §10.2)
- [X] T009 [P] Scaffold `docs/requirements.md` (copy of the source requirements document), `docs/runbook.md`, `docs/source-policy.md`, `docs/metric-definitions.md` with section headers to be filled during Polish
- [X] T010 [P] Set up `tests/fixtures/` directory with placeholder README describing each golden fixture to be added later (UKGC XLSX, operator annual-report PDF excerpt, promotion-terms HTML, traffic CSV, Google Trends CSV, app-store capture, UX audit JSON) per `research.md` decision #13

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure every user story depends on — identity, schema, Sheets/Drive access, write-safety guarantees, CLI skeleton

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T011 [P] Implement prefixed-ULID ID generator (`brand_`, `operator_`, `source_`, `document_`, `obs_`, `audit_`, `derived_`, `task_`, `change_`, `issue_`, `run_`) in `src/casino_intel/models/ids.py`
- [X] T012 [P] Implement the common base Pydantic model (`record_id`, `created_at`, `created_by`, `updated_at`, `status`, `notes`, `source_id`, `document_id`, `evidence_type`, `confidence`, `review_status`, `captured_at`, `valid_from`/`valid_to`, `period_start`/`period_end`) with the `status` and `review_status` state-transition rules from `data-model.md` in `src/casino_intel/models/base.py`
- [X] T013 [P] Implement controlled-vocabulary enums (evidence type, confidence, review status, brand/licence/source status, comparability status, etc.) loaded from `config/vocabularies.yaml` in `src/casino_intel/models/vocab.py`
- [X] T014 Implement the Sheets API client wrapper (`spreadsheets.values.batchGet`/`batchUpdate`, `tenacity`-based exponential-backoff retry on quota errors) in `src/casino_intel/sheets/client.py`
- [X] T015 Implement formula-injection escaping for any text starting with `=`, `+`, `-`, or `@` per `contracts/observation-write-contract.md` §3, in `src/casino_intel/sheets/safety.py` (depends on T014)
- [X] T016 Implement the append-only write layer (row append; `active`→`superseded`/`rejected` status transition only; no other in-place field edits; batched calls; paired Change Log write) per `contracts/observation-write-contract.md` §1 and §4–5, in `src/casino_intel/sheets/writer.py` (depends on T014, T015)
- [X] T017 Implement Sheets schema bootstrap: create all 23 tabs from source doc §5 with headers, frozen header rows, named ranges for `Config` vocabularies, data-validation dropdowns, and conditional formatting for confidence/quality columns, in `src/casino_intel/sheets/schema.py` (depends on T014)
- [X] T018 [P] Implement the Drive API client (file upload/archive, SHA-256 content hashing, `archive_path` construction per the Drive hierarchy in source doc §9.6) in `src/casino_intel/drive/client.py`
- [X] T019 [P] Implement the local, rebuildable SQLite fingerprint/document-hash cache in `src/casino_intel/cache/fingerprint_store.py`
- [X] T020 [P] Implement the observation fingerprint function (`sha256(subject_id | metric_id | period_start | period_end | as_of_date | geography | segment | source_id | raw_value)`) per `contracts/observation-write-contract.md` §2, in `src/casino_intel/validation/fingerprint.py`
- [X] T021 [P] Implement structured JSON logging setup in `src/casino_intel/logging.py`
- [X] T022 Implement the Config/vocab loader that seeds the `Config` sheet from `config/*.yaml` on first run and thereafter treats the `Config` sheet as the runtime authority, in `src/casino_intel/sheets/config_loader.py` (depends on T014, T005–T008)
- [X] T023 [P] Implement the Change Log write helper (append-only; actor, action, `record_id`, field diff or JSON-diff reference, `source_id`, `ingestion_run_id`) in `src/casino_intel/sheets/change_log.py` (depends on T016)
- [X] T024 [P] Implement the Data Quality issue writer covering all 18 issue types from source doc §9.21 (missing source, missing reporting period, invalid ID, duplicate entity, duplicate observation, unsupported currency, percentage outside 0–100, negative value where prohibited, normalised value without raw value, derived metric without inputs, subjective score without rationale, stale observation, conflicting high-confidence observations, group figure mislabelled as brand figure, unreachable source URL, changed content hash, unknown metric definition, invalid controlled-vocabulary value) in `src/casino_intel/validation/data_quality.py` (depends on T016)
- [X] T025 Implement the Typer CLI app skeleton with global `--dry-run`, `--ingestion-run-id`, and credential loading strictly from environment variables per `contracts/cli-commands.md` "Global contract", in `src/casino_intel/cli/app.py` (depends on T014)
- [X] T026 Implement `casino-intel initialise-workbook` (idempotent — creates missing tabs/headers/vocab only, never duplicates or overwrites existing data) per `contracts/cli-commands.md`, in `src/casino_intel/cli/commands/initialise_workbook.py` (depends on T017, T022, T025)

**Checkpoint**: Foundation ready — workbook can be created/verified; Sheets/Drive access, write-safety, IDs, logging, and CLI skeleton all exist. User story work can begin.

---

## Phase 3: User Story 1 - Trustworthy foundation of brands, operators and sourced facts (Priority: P1) 🎯 MVP

**Goal**: Register operators, brands, licences and sources, and record facts as append-only, fully-traced, evidence-typed, currency-normalised observations that never overwrite history.

**Independent Test**: Register one operator, one brand, one source, and two dated observations for the same brand/metric; confirm both persist, each traces to its source, and evidence type/confidence/comparability are visible (quickstart.md Steps 1–2).

### Implementation for User Story 1

- [X] T027 [P] [US1] Create the `Operator` model in `src/casino_intel/models/operator.py`
- [X] T028 [P] [US1] Create the `Brand` model (including `sampling_rationale`) in `src/casino_intel/models/brand.py`
- [X] T029 [P] [US1] Create the `Licence` model in `src/casino_intel/models/licence.py`
- [X] T030 [P] [US1] Create the `Source` model, enforcing that `paywalled`/`authentication_required` sources are flagged for manual-only access, in `src/casino_intel/models/source.py`
- [X] T031 [P] [US1] Create the `Document` model in `src/casino_intel/models/document.py`
- [X] T032 [US1] Create the canonical `Observation` model with all fields from `data-model.md` (including FX fields) in `src/casino_intel/models/observation.py` (depends on T012, T020)
- [X] T033 [US1] Implement currency/FX normalisation (retain original value+currency, compute normalised GBP value, `fx_rate`, `fx_rate_date`, calculation method) in `src/casino_intel/normalisation/currency.py`
- [X] T034 [US1] Implement date/percentage/unit normalisation helpers in `src/casino_intel/normalisation/units.py`
- [X] T035 [US1] Implement the observation append service enforcing append-only semantics, conflicting-source retention (no silent merge/average), and comparability-field population, in `src/casino_intel/services/observation_service.py` (depends on T016, T020, T032, T033, T034)
- [X] T036 [US1] Implement `casino-intel add-source --url --type` per `contracts/cli-commands.md`, in `src/casino_intel/cli/commands/add_source.py` (depends on T030, T016)
- [X] T037 [US1] Implement the brand/operator/licence registration service, including bulk-load from a seed file, in `src/casino_intel/services/registry_service.py` (depends on T027–T029, T016)
- [X] T038 [US1] Create the pilot seed data file (15–20 brands and their operators, stratified per spec §14: scale, proposition, sentiment, traffic-scale variety, one crypto-native comparator, documented `sampling_rationale`) and loader script `scripts/seed_pilot_brands.py` (depends on T037)
- [X] T039 [US1] Implement core validation rules for FR-001–FR-010 (identity/ID format, required evidence/confidence, comparability fields, controlled-vocabulary enforcement, "no interchangeable customer-metric terms") in `src/casino_intel/validation/rules_core.py` (depends on T013, T024)
- [X] T040 [US1] Wire Brand/Operator/Licence/Source/Observation writes through the Change Log (T023) and Data Quality (T024/T039) paths
- [X] T041 [US1] Add unit tests for fingerprint uniqueness, append-only behaviour on repeated writes, and FX-normalisation field retention in `tests/unit/test_observation_service.py`
- [X] T042 [US1] Add an integration test registering one operator, one brand, one source and two dated observations for the same brand/metric, asserting both persist without overwrite and both display evidence type/confidence/source linkage, in `tests/integration/test_user_story_1.py`

**Checkpoint**: User Story 1 is fully functional and independently testable — brands/operators/sources/observations can be created, traced and never overwritten.

---

## Phase 4: User Story 2 - Automated ingestion of public documents into reviewable facts (Priority: P2)

**Goal**: Fetch, parse, extract, normalise, validate and idempotently append observations from HTML, PDF and CSV/XLSX sources, plus the traffic/search-interest/app-presence/offer/product/reputation/acquisition domain views that follow the same ingestion pipeline.

**Independent Test**: Ingest a known regulator HTML/XLSX page, an operator PDF, and a structured CSV/XLSX export; confirm reviewable observations with source locators appear, and a second run against the same unchanged documents creates zero duplicates (quickstart.md Steps 3–6).

### Implementation for User Story 2

- [X] T043 [P] [US2] Implement the extraction-record model matching `contracts/extraction-record.schema.json` in `src/casino_intel/extraction/schema.py`
- [X] T044 [US2] Implement the generic HTTP fetcher (`httpx` + `tenacity` retries, robots/terms check, per-domain rate limiting, hard refusal of paywalled/authentication-required sources) in `src/casino_intel/fetching/fetcher.py`
- [X] T045 [US2] Implement fetch archiving: Drive upload, content hash, and `Document` row creation/versioning (preserve prior document, new hash → new row, hold for review before supersede) in `src/casino_intel/fetching/archiver.py` (depends on T018, T031, T044)
- [X] T046 [P] [US2] Implement the HTML parser (`beautifulsoup4`+`lxml`, `pandas.read_html` for tables) in `src/casino_intel/parsing/html_parser.py`
- [X] T047 [P] [US2] Implement the PDF parser (`PyMuPDF` text, `pdfplumber` tables) in `src/casino_intel/parsing/pdf_parser.py`
- [X] T048 [P] [US2] Implement the CSV/XLSX parser (`pandas`/`openpyxl`) in `src/casino_intel/parsing/tabular_parser.py`
- [X] T049 [US2] Implement the extractor mapping parsed content to metric definitions, capturing source locator and short excerpt, always emitting `review_status=unreviewed` records conforming to T043's schema, in `src/casino_intel/extraction/extractor.py` (depends on T043, T046, T047, T048, T022)
- [X] T050 [US2] Wire currency/date/percentage/unit normalisation (T033, T034) into the extraction pipeline output in `src/casino_intel/normalisation/pipeline.py`
- [X] T051 [US2] Implement the ingestion-time business-rule validator, routing failures to the T024 Data Quality writer, in `src/casino_intel/validation/rules_ingestion.py` (depends on T024, T039, T050)
- [X] T052 [US2] Implement the idempotent dedup check against the fingerprint cache before any append, per `contracts/observation-write-contract.md` §2, in `src/casino_intel/services/dedup_service.py` (depends on T019, T020)
- [X] T053 [US2] Implement source-changed-at-same-URL handling (new `Document` + hash, hold resulting observation changes for human review before superseding) in `src/casino_intel/services/document_versioning_service.py` (depends on T045)
- [X] T054 [US2] Implement the ingestion orchestrator wiring fetch → archive → parse → extract → normalise → validate → dedup → append-unreviewed → data-quality-issue-creation, per source doc §11.3, in `src/casino_intel/services/ingestion_run.py` (depends on T044–T053, T035)
- [X] T055 [US2] Implement the UKGC HTML/XLSX importer (annual industry statistics, market overview, gambling business data) in `src/casino_intel/parsing/ukgc_importer.py` and `scripts/import_ukgc.py` (depends on T046, T048, T054)
- [X] T056 [US2] Implement the operator annual-report PDF importer targeting the KPI search terms from source doc §10.4 (active customers, GGR/NGR/GGY, marketing/S&M expense, CPA, retention/churn, ARPU, bonuses, affiliate) in `src/casino_intel/parsing/operator_report_importer.py` (depends on T047, T054)
- [X] T057 [US2] Implement the human review workflow (approve / reject / correct; `review_status` transitions) in `src/casino_intel/services/review_service.py` (depends on T016)
- [X] T058 [US2] Implement `casino-intel fetch-source --source-id` per `contracts/cli-commands.md` in `src/casino_intel/cli/commands/fetch_source.py` (depends on T044, T045)
- [X] T059 [US2] Implement `casino-intel ingest-source --source-id` per `contracts/cli-commands.md` in `src/casino_intel/cli/commands/ingest_source.py` (depends on T054)
- [X] T060 [US2] Implement `casino-intel import-file --path --source-id` per `contracts/cli-commands.md` in `src/casino_intel/cli/commands/import_file.py` (depends on T054)
- [X] T061 [US2] Implement `casino-intel validate` (re-run validation across existing records, refresh Data Quality, no data mutation) in `src/casino_intel/cli/commands/validate.py` (depends on T051)
- [X] T062 [US2] Implement Research Task auto-creation on ingestion blockers (paywalled source, parse failure, unresolved conflict) in `src/casino_intel/services/research_task_service.py` (depends on T054)
- [X] T063 [P] [US2] Implement the brand traffic-provider CSV/XLSX import (provider-tagged, never merged across providers) in `src/casino_intel/parsing/traffic_importer.py`
- [X] T064 [P] [US2] Implement the Google Trends CSV import (`comparison_set_id`, `anchor_term`, never compared across unrelated comparison sets) in `src/casino_intel/parsing/trends_importer.py`
- [X] T065 [P] [US2] Implement app-store presence capture (rating/review counts, version recency, rank, download estimate kept distinct from active-user counts) in `src/casino_intel/parsing/app_store_importer.py`
- [X] T066 [US2] Implement offer capture from brand promotion pages and their full terms pages (never headline-only), with screenshot archival via T045, in `src/casino_intel/parsing/offer_capture.py`
- [X] T067 [P] [US2] Implement product/game-catalogue observation capture (lobby page parsing: vertical coverage, providers, discovery features) in `src/casino_intel/parsing/product_capture.py`
- [X] T068 [US2] Implement reputation aggregation import (aggregate scores + paraphrased recurring themes only — never raw review text or usernames, per FR-030/FR-047) in `src/casino_intel/parsing/reputation_importer.py`
- [X] T069 [US2] Implement the acquisition/CPA-range estimator combining reported figures, affiliate offer terms, and paid-search cost data, explicitly labelling any group-marketing-expense-derived figure as a group-level proxy (FR-024), in `src/casino_intel/services/acquisition_estimator.py`
- [X] T070 [US2] Add golden fixtures (UKGC XLSX, operator annual-report PDF excerpt, promotion-terms HTML, traffic CSV, Google Trends CSV) to `tests/fixtures/`, replacing the T010 placeholders
- [X] T071 [US2] Add unit tests for extraction-record schema conformance and validation-rule routing to Data Quality in `tests/unit/test_validation_rules.py`
- [X] T072 [US2] Add an integration test proving idempotent re-ingestion (zero duplicates on a second run against an unchanged fixture) and versioned re-ingestion (a changed fixture creates a new `Document` and holds pending review) in `tests/integration/test_user_story_2.py`

**Checkpoint**: User Stories 1 AND 2 both work independently — the fact base can now be populated automatically from real documents, idempotently.

---

## Phase 5: User Story 3 - Manual UX and brand audits with photographic evidence (Priority: P3)

**Goal**: Capture rubric-scored UX and brand audits, each score backed by a mandatory rationale and screenshot evidence, with automated/guided journeys stopping before any account-creation, KYC, deposit, wager or withdrawal action.

**Independent Test**: Complete one UX audit and one brand audit for a single brand; confirm every score has a rationale, screenshots are attached, and the journey stops at the required safety boundary (quickstart.md Step 8).

### Implementation for User Story 3

- [X] T073 [P] [US3] Create the `UXAudit` model (rubric score+rationale field pairs, journey-safety fields) in `src/casino_intel/models/ux_audit.py`
- [X] T074 [P] [US3] Create the `BrandAudit` model (visual/tone/positioning score+rationale field pairs) in `src/casino_intel/models/brand_audit.py`
- [X] T075 [US3] Implement the audit-rubric loader (`rubric_version`, 1–5 scale definitions) from `config/audit-rubrics.yaml` in `src/casino_intel/services/rubric_service.py` (depends on T007)
- [X] T076 [US3] Implement score-requires-rationale validation (reject the save if any populated `*_score` field lacks a non-empty paired `*_score_rationale`) in `src/casino_intel/validation/audit_validation.py` (depends on T073, T074)
- [X] T077 [US3] Implement the journey-safety guard preventing any recorded step from representing a completed KYC submission, deposit, wager, or withdrawal (FR-033, FR-046) in `src/casino_intel/services/journey_safety.py`
- [X] T078 [US3] Implement Playwright-based permitted dynamic capture (homepage, lobby, promotions, registration up to the stop point, footer/licence, responsible-gambling screenshots) archived via T018, gated by T077, in `src/casino_intel/fetching/audit_capture.py`
- [X] T079 [US3] Implement `casino-intel` audit-recording entry points (`record-ux-audit`, `record-brand-audit`) supporting both the Playwright-assisted flow and a manual/hand-entered fallback, in `src/casino_intel/cli/commands/record_ux_audit.py` and `record_brand_audit.py` (depends on T075–T078)
- [X] T080 [P] [US3] Implement the standard capture-environment metadata model (geography, viewport, device, logged-in/cookie state, date/time) per source doc §13.1 in `src/casino_intel/models/capture_environment.py`
- [X] T081 [US3] Add an integration test completing one UX audit and one brand audit end-to-end, asserting a missing rationale is rejected and no restricted-action step is ever recorded as completed, in `tests/integration/test_user_story_3.py`

**Checkpoint**: All three of User Stories 1–3 are independently functional.

---

## Phase 6: User Story 4 - Derived metrics with transparent formulas and lineage (Priority: P4)

**Goal**: Calculate the initial derived-metric set from approved observations only, always recording formula, inputs and assumptions, and never fabricating a value when definitions/periods are incompatible.

**Independent Test**: With two compatible approved observations, trigger derivation and confirm the formula/inputs/value are recorded; confirm an incompatible pair produces no fabricated value (quickstart.md Step 7).

### Implementation for User Story 4

- [X] T082 [P] [US4] Create the `DerivedMetric` model in `src/casino_intel/models/derived_metric.py`
- [X] T083 [US4] Implement the formula registry (`revenue_per_active_customer`, `ggy_per_average_monthly_active_account`, `marketing_pct_revenue`, `adjusted_ebitda_margin`, `traffic_growth_yoy`, `share_of_search`, `indicative_cpa_range`) with `formula_version`, per source doc §9.18, in `src/casino_intel/derivation/formulas.py`
- [X] T084 [US4] Implement the comparability/compatibility gate that skips (rather than fabricates) a calculation when input periods or definitions are insufficiently compatible in `src/casino_intel/derivation/compatibility.py`
- [X] T085 [US4] Implement the derived-metric engine: read only `approved` observations, evaluate T083 formulas gated by T084, write new rows via T016 (never overwrite prior results), recording lineage, in `src/casino_intel/derivation/engine.py` (depends on T082, T083, T084, T016)
- [X] T086 [US4] Implement `casino-intel derive` per `contracts/cli-commands.md` in `src/casino_intel/cli/commands/derive.py` (depends on T085)
- [X] T087 [US4] Add unit tests per formula (correct calculation, correct skip-on-incompatibility, correct lineage/formula-version recording, no overwrite on recalculation) in `tests/unit/test_derivation.py`

**Checkpoint**: User Stories 1–4 are independently functional.

---

## Phase 7: User Story 5 - Comparative summary across the brand set (Priority: P5)

**Goal**: Generate a single comparative view across brands showing latest values, confidence/evidence markers, operator-vs-brand-level labelling, observation age, and visible research gaps.

**Independent Test**: With brands of varying data completeness, generate the summary and confirm every figure is labelled with confidence/evidence-type, operator-vs-brand level (where relevant), and missing signals are visibly flagged (quickstart.md Step 9).

### Implementation for User Story 5

- [X] T088 [US5] Implement per-brand completeness/gap scoring (latest-value lookup per tracked signal, confidence/evidence-marker propagation, operator-vs-brand-level marker, observation-age calculation) in `src/casino_intel/reporting/completeness.py`
- [X] T089 [US5] Implement the Summary sheet generator (pilot brand coverage, completeness by domain, latest traffic/search-interest/revenue/active-customer figures, revenue-per-active-customer, marketing % of revenue, current welcome offer, UX score, brand-positioning scores, reputation score, confidence indicator, observation age, research gaps) in `src/casino_intel/reporting/summary_generator.py` (depends on T088)
- [X] T090 [US5] Implement `casino-intel refresh-summary` per `contracts/cli-commands.md` in `src/casino_intel/cli/commands/refresh_summary.py` (depends on T089)
- [X] T091 [US5] Add an integration test generating the summary across brands with mixed data completeness, asserting confidence/evidence and operator-vs-brand-level labels appear and missing signals are flagged (never silently blank or backfilled), in `tests/integration/test_user_story_5.py`

**Checkpoint**: All five user stories are independently functional — the full spec is implemented.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Remaining CLI surface, documentation, and hardening that spans multiple user stories

- [X] T092 [P] Implement `casino-intel export --output` (full CSV export of all 23 tabs, no data loss) per `contracts/cli-commands.md` in `src/casino_intel/cli/commands/export.py`
- [X] T093 [P] Implement `casino-intel research-queue list` and `casino-intel research-queue run --limit` per `contracts/cli-commands.md` in `src/casino_intel/cli/commands/research_queue.py` (depends on T062)
- [X] T094 [P] Implement schema-version tracking and a migration log in the `README` tab and `docs/`, per source doc §17.3, in `src/casino_intel/sheets/schema_version.py`
- [X] T095 [P] Write `docs/runbook.md` (setup, credential rotation, ingestion-run triage, Data Quality resolution workflow)
- [X] T096 [P] Write `docs/source-policy.md` (access policy: paywall/authentication refusal, robots/terms respect, rate limits)
- [X] T097 [P] Write `docs/metric-definitions.md` (human-readable mirror of `config/metrics.yaml`)
- [X] T098 [P] Add unit tests for formula-injection escaping (`=`, `+`, `-`, `@`-leading values) in `tests/unit/test_sheets_safety.py`
- [X] T099 [P] Add unit tests for ID generation uniqueness and prefix correctness in `tests/unit/test_ids.py`
- [X] T100 Add an automated secrets-hygiene check confirming no credentials ever appear in the workbook or CSV exports, in `tests/integration/test_no_secrets_leak.py`
- [X] T101 Execute the full `quickstart.md` validation sequence end-to-end against a real test spreadsheet and record the outcome in `docs/runbook.md`
- [X] T102 Add a test asserting all Sheets writes go through batched calls (never cell-by-cell) in `tests/unit/test_batch_writes.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion (needs `config/*.yaml` from T005–T008) — BLOCKS all user stories
- **User Stories (Phase 3–7)**: All depend on Foundational completion
  - US1 has no dependency on any other user story
  - US2 depends on US1's `Observation`/`Source`/`Document` models and `observation_service` (T032, T035) but is otherwise independently testable once those exist
  - US3 depends only on Foundational + Brand existing (US1) — independent of US2
  - US4 depends on approved observations existing, i.e. functionally exercised after US1 (and ideally US2) have produced data, but the derivation code itself has no US2/US3 code dependency
  - US5 depends on data existing across US1–US4 to be meaningfully tested, but the summary-generation code itself only reads what other stories wrote
- **Polish (Phase 8)**: Depends on the user stories it touches (export/research-queue depend on earlier phases' writers/services existing)

### Parallel Opportunities

- All Setup tasks marked [P] (T003–T010) can run in parallel once T001–T002 exist
- Foundational tasks marked [P] (T011–T013, T018–T021, T023–T024) can run in parallel; T014–T017, T022, T025–T026 have sequential dependencies as noted
- Once Foundational completes, US1 and US3 can start in parallel (both depend only on Foundational); US2 can start in parallel with US3 but its later tasks depend on US1's Observation model; US4 and US5 are best started once US1–US2 have produced approved data, but their code can be written in parallel with US3
- Within US1: T027–T031 (all distinct models) are parallel; within US2: T043, T046–T048, T063–T065, T067 are parallel; within US3: T073, T074, T080 are parallel

---

## Parallel Example: User Story 1

```bash
# Launch all independent models for User Story 1 together:
Task: "Create the Operator model in src/casino_intel/models/operator.py"
Task: "Create the Brand model in src/casino_intel/models/brand.py"
Task: "Create the Licence model in src/casino_intel/models/licence.py"
Task: "Create the Source model in src/casino_intel/models/source.py"
Task: "Create the Document model in src/casino_intel/models/document.py"
```

## Parallel Example: User Story 2 (domain-view capture)

```bash
# Launch the independent domain-view importers together (all reuse the same
# fetch/parse/extract/validate/dedup pipeline built earlier in Phase 4):
Task: "Implement the brand traffic-provider CSV/XLSX import in src/casino_intel/parsing/traffic_importer.py"
Task: "Implement the Google Trends CSV import in src/casino_intel/parsing/trends_importer.py"
Task: "Implement app-store presence capture in src/casino_intel/parsing/app_store_importer.py"
Task: "Implement product/game-catalogue observation capture in src/casino_intel/parsing/product_capture.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything else)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE** using quickstart.md Steps 1–2: a small, fully-traceable, non-overwriting fact base with confidence/evidence visible
5. This is a legitimate, demonstrable MVP even before any automated ingestion exists

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add User Story 1 → validate independently (quickstart Steps 1–2) → MVP
3. Add User Story 2 → validate independently (quickstart Steps 3–6) → automated ingestion at pilot scale
4. Add User Story 3 → validate independently (quickstart Step 8) → structured human audits
5. Add User Story 4 → validate independently (quickstart Step 7) → transparent derived metrics
6. Add User Story 5 → validate independently (quickstart Step 9) → comparative analysis payoff view
7. Phase 8 Polish → export, research-queue automation, documentation, hardening (quickstart Steps 10–11)

### Suggested Team Split (if parallelised)

- Developer/agent A: Foundational (Phase 2) first, then User Story 1
- Developer/agent B: User Story 3 (depends only on Foundational + Brand model from US1's early models)
- Developer/agent C: User Story 2's parser/fetcher modules (can be built and unit-tested against fixtures before US1's observation_service is finished, then wired together)
- User Stories 4 and 5 are best picked up once US1/US2 are producing approved data to calculate over and summarise

---

## Notes

- [P] tasks touch different files with no unmet dependency
- [Story] labels map every user-story-phase task back to spec.md for traceability
- Every fact-writing task must route through the Phase 2 write layer (T016) so append-only, idempotency, formula-injection and change-log guarantees apply uniformly — no user-story task should call the Sheets API directly
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently before continuing
- Avoid: bypassing the shared write layer, cross-story code dependencies that would prevent independent testing, and silently expanding derived-metric scope beyond source doc §9.18's initial calculation set
