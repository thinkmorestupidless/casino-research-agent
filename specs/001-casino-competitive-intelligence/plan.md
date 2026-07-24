# Implementation Plan: Online Casino Competitive Intelligence Database

**Branch**: `001-casino-competitive-intelligence` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-casino-competitive-intelligence/spec.md`

## Summary

Build a source-backed competitive intelligence dataset for GB-facing online casino brands, delivered as a Google Sheets workbook (the primary storage and interface) plus a Python CLI/ingestion pipeline that fetches, parses, extracts, normalises, validates and writes time-indexed observations into that workbook with full source provenance, evidence typing and confidence. The pipeline runs as on-demand CLI commands (no scheduler in the MVP), archives raw documents to Google Drive, maintains an append-only change log and a data-quality queue, computes a small set of derived metrics with recorded lineage, and supports human-authored UX/brand audits. The technical approach follows the stack and architecture recommended in the source requirements document (`online-casino-competitive-intelligence-requirements.md`, §11.2, §18–19): Python 3.12+, Pydantic models, the Google Sheets and Drive APIs, `httpx`/BeautifulSoup/pandas/PyMuPDF for fetching and parsing, and a Typer-based CLI, with an explicitly designed future migration path to PostgreSQL.

## Technical Context

**Language/Version**: Python 3.12+ (per source doc §11.2; async-capable stdlib features and modern typing used throughout)

**Primary Dependencies**: Pydantic v2 (schemas/validation), `google-api-python-client` + `google-auth` (Sheets API v4 + Drive API v3), `httpx` (HTTP fetching, with `tenacity` for retry/backoff), `beautifulsoup4` + `lxml` (HTML parsing), `pandas` + `openpyxl` (CSV/XLSX parsing), `PyMuPDF` (PDF text extraction) + `pdfplumber` (PDF table extraction), `python-ulid` (ID generation), Playwright (permitted dynamic-page capture only, e.g. rendered brand-website screenshots), Typer (CLI), `structlog` (structured JSON logging)

**Storage**: Google Sheets (system of record for all entities, observations and views) + Google Drive (archived documents, screenshots, extracted-text/JSON artifacts) + a local, rebuildable SQLite cache (observation fingerprints and document hashes only, to avoid re-reading the full `Observations` sheet on every ingestion run — never a second system of record)

**Testing**: pytest (unit + integration), golden fixtures under `tests/fixtures/` for parser/extractor determinism (per source doc §20.3), contract tests for CLI command behavior and the extraction output schema

**Target Platform**: Locally- or server-run CLI tool (Linux/macOS), invoked manually or via external scheduling (e.g. cron) outside the MVP's own scope; no hosted web application or long-running service

**Project Type**: Single project — a Python CLI/library (`casino_intel`) with no separate frontend; the Google Sheets workbook is the user-facing surface, not a web app this codebase serves

**Performance Goals**: Not latency-sensitive; ingestion is batch/on-demand. Google Sheets API usage must use batch reads/writes (never cell-by-cell) and stay within standard Sheets API quotas via exponential backoff, comfortably supporting a 15–20 brand pilot generating a low-thousands row count across all sheets

**Constraints**: Must respect Google Sheets practical limits (cell count, per-sheet row growth) per source doc §17.2; must never store large raw text/HTML/images in sheet cells (Drive + reference only); must protect against spreadsheet formula injection on any imported text; must never bypass paywalls, authentication or anti-bot controls; must not collect personal data about individual gamblers; automated journeys must stop before account creation, KYC submission, deposit, wager or withdrawal

**Scale/Scope**: Pilot scope of 15–20 brands and their operators; expected observation volume in the low thousands for the pilot; the source document defines an explicit migration trigger to PostgreSQL at roughly 50,000–100,000 observation rows or when concurrent multi-agent writes/scheduled ingestion become routine (§23) — out of scope for this plan, but the data model is designed to map cleanly onto that future schema

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` in this repository is still the unfilled template (placeholder principle names/descriptions, no ratified version) — there is no ratified project constitution to gate against yet. No constitution-derived gates apply to this plan. If a constitution is ratified later, this plan should be re-checked against it before implementation proceeds.

No violations to record; **Complexity Tracking** below is not applicable.

*Post-Phase 1 re-check (2026-07-24): `research.md`, `data-model.md`, and `contracts/` were generated without introducing any additional project, service, or architectural layer beyond the single-project CLI structure declared above — no new gate evaluation is triggered by the design phase. Still no ratified constitution to check against.*

## Project Structure

### Documentation (this feature)

```text
specs/001-casino-competitive-intelligence/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── cli-commands.md
│   ├── extraction-record.schema.json
│   └── observation-write-contract.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
casino-intelligence/
├── README.md
├── pyproject.toml
├── .env.example
├── config/
│   ├── metrics.yaml            # metric-definition registry (seeds Config sheet)
│   ├── vocabularies.yaml       # controlled vocabularies (seeds Config sheet)
│   ├── sources.yaml            # known/seed source list (regulators, operators)
│   └── audit-rubrics.yaml      # UX/brand audit rubric definitions + versions
├── src/
│   └── casino_intel/
│       ├── models/             # Pydantic models: Brand, Operator, Licence, Source,
│       │                       # Document, Observation, DerivedMetric, ResearchTask,
│       │                       # ChangeLogEntry, DataQualityIssue, audit/domain views
│       ├── sheets/              # Sheets API client, batch read/write, formula-injection
│       │                       # escaping, named ranges, data validation, protected ranges
│       ├── drive/               # Drive API client, archive path management, content hashing
│       ├── fetching/            # httpx-based fetcher, robots/terms checks, rate limiting
│       ├── parsing/             # HTML (bs4), PDF (PyMuPDF/pdfplumber), CSV/XLSX (pandas)
│       ├── extraction/          # candidate-fact extraction, source locators, excerpting
│       ├── normalisation/       # date/currency/percentage/unit parsing, FX normalisation
│       ├── validation/          # schema + business-rule validation, Data Quality routing
│       ├── derivation/          # derived-metric formulas, lineage recording
│       ├── reporting/           # Summary sheet generation, completeness/gap scoring
│       └── cli/                 # Typer app wiring the commands in contracts/cli-commands.md
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/                # golden fixtures: UKGC XLSX, annual-report PDF, promo HTML,
│                                 # traffic CSV, Google Trends CSV, app-store capture, UX audit JSON
├── scripts/
│   ├── initialise_workbook.py
│   ├── ingest_source.py
│   ├── import_ukgc.py
│   ├── validate_workbook.py
│   ├── refresh_summary.py
│   └── export_csv.py
└── docs/
    ├── requirements.md          # copy of the source requirements document
    ├── runbook.md
    ├── source-policy.md
    └── metric-definitions.md
```

**Structure Decision**: Single project (Option 1). This is a CLI/library codebase with the Google Sheets workbook as its user-facing surface — there is no separate frontend to justify a web-application layout. The layout mirrors the repository structure specified in the source requirements document (§18) directly, since it already matches the pipeline components in this plan's Technical Context and keeps design and requirements documentation in sync.

## Complexity Tracking

Not applicable — no Constitution Check violations were identified (see above).
