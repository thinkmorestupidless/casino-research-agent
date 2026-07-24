# Quickstart: Validating the Casino Competitive Intelligence Database

This is a runnable validation guide, not a build guide. It proves the feature works end-to-end against the acceptance criteria in `spec.md` (SC-001–SC-013) and the acceptance criteria in the source requirements document (§21). Full command flags are documented in `contracts/cli-commands.md`; this guide only sequences them.

## Prerequisites

1. Python 3.12+ installed; project dependencies installed (`pyproject.toml` — see `research.md` for the pinned stack).
2. A Google Cloud service account with the Sheets API and Drive API enabled.
3. A target Google Sheet created (or left to `initialise-workbook` to create) and **shared with the service account's email** as an Editor.
4. Environment variables set (see `.env.example`):
   - `GOOGLE_APPLICATION_CREDENTIALS` → path to the service-account JSON key
   - `SPREADSHEET_ID` → target workbook ID
5. `config/vocabularies.yaml`, `config/metrics.yaml`, `config/sources.yaml`, `config/audit-rubrics.yaml` populated (initial versions checked into the repo per source doc §18).

## Step 1 — Stand up the workbook (validates FR-041, FR-009, SC-002 groundwork)

```bash
casino-intel initialise-workbook
```

**Expected outcome**: All 23 tabs exist with frozen headers, data validation dropdowns sourced from `Config`, and the `README` tab shows a schema version and target market. Re-running the command is a no-op on already-created tabs (idempotency check).

## Step 2 — Register the pilot brand set (validates User Story 1, FR-001–FR-010, SC-002)

Manually (or via a seed script) add at least 15 `Operator` rows and 15–20 `Brand` rows to the workbook, each with a `sampling_rationale` populated, per the stratified-sampling criteria in spec §14/Assumptions.

**Expected outcome**: Every brand has a stable `brand_id`, links to a valid `operator_id`, and no two brands share a `brand_id`. Manually add one traffic-estimate observation twice, on two different dates, for the same brand — confirm both rows persist in `Observations` (append-only, FR-004).

## Step 3 — Register and ingest a known regulator source (validates User Story 2, FR-011, FR-015–FR-020, SC-004, SC-005)

```bash
casino-intel add-source --url "<UKGC statistics page URL>" --type regulator_statistics
casino-intel fetch-source --source-id <returned source_id>
casino-intel ingest-source --source-id <returned source_id>
```

**Expected outcome**: New `Document` and `Observation` rows appear, each `Observation` carrying `evidence_type=reported_primary` (or as appropriate), a `source_locator`, and `review_status=unreviewed`. Re-run `ingest-source` against the same, unchanged source:

```bash
casino-intel ingest-source --source-id <same source_id>
```

**Expected outcome**: Zero new `Observation` rows are created (idempotency — SC-005). Confirm via `Change Log` that no duplicate write occurred.

## Step 4 — Ingest one PDF and one XLSX/CSV source (validates SC-004's "three formats")

Repeat Step 3's `add-source`/`fetch-source`/`ingest-source` sequence against:
- one operator annual-report PDF, and
- one structured traffic/search-interest CSV or XLSX export.

**Expected outcome**: Candidate observations appear for both formats, each correctly tagged `evidence_type` (e.g. `reported_primary` for the annual report, `third_party_estimate` for the traffic export) and linked to the correct `Document`.

## Step 5 — Force a validation failure and confirm it surfaces (validates FR-020, SC-010)

Ingest (or manually insert) one record missing a `source_id`, and one percentage-typed metric with a value outside 0–100.

**Expected outcome**: Both appear as rows in `Data Quality` with `issue_type=missing_source` and `issue_type=percentage_outside_0_100` respectively — neither silently enters `Observations` as `active`.

## Step 6 — Human review and approval (validates FR-021)

Mark several ingested observations `review_status=human_reviewed` then `approved` (via the review workflow / manual edit).

**Expected outcome**: Only `approved` observations are eligible as derived-metric inputs in Step 7.

## Step 7 — Run a derived-metric calculation (validates User Story 4, FR-035–FR-037, SC-009)

Ensure one brand/operator has both an approved revenue observation and an approved active-customer observation for compatible periods, then:

```bash
casino-intel derive
```

**Expected outcome**: A new `Derived Metrics` row for `revenue_per_active_customer` appears, showing the formula, the exact `input_observation_ids`, and the resulting value. For a second brand where only an incompatible-period pair exists, confirm **no** fabricated derived value is produced — the gap remains visible.

## Step 8 — Conduct one UX audit and one brand audit (validates User Story 3, FR-031–FR-034, SC-007)

Following the standard capture environment (spec §13.1: GB geography, defined viewport, logged-out, consistent cookie state), complete one `UX Audit` and one `Brand Audit` row for a single brand, stopping before any account creation, deposit, wager, ID submission, or withdrawal (FR-033, FR-046).

**Expected outcome**: Every populated `*_score` field has a non-empty paired `*_score_rationale` (attempt to save one without a rationale and confirm it is rejected — Edge Case validation). Homepage, lobby, promotions and footer/licence screenshots are attached and retrievable via their Drive references.

## Step 9 — Refresh the summary view (validates User Story 5, FR-041, SC-001, SC-008, SC-013)

```bash
casino-intel refresh-summary
```

**Expected outcome**: The `Summary` sheet shows, per brand, the latest tracked figures with visible confidence/evidence-type markers, an explicit operator-vs-brand-level label on any group-sourced financial figure, the age of the latest observation, and a visible list of remaining research gaps for brands with incomplete coverage.

## Step 10 — Export and verify no data loss (validates FR-043, SC-011)

```bash
casino-intel export --output exports/
```

**Expected outcome**: One CSV per tab is written to `exports/`; spot-check that row counts match the live sheet for `Brands`, `Observations`, and `Data Quality`.

## Step 11 — Confirm secrets hygiene (validates FR-050, SC-012)

Inspect the workbook (`README`, `Config`, and any other tab) and the exported CSVs.

**Expected outcome**: No API keys, service-account contents, or credentials appear anywhere in the workbook or exports.

---

Passing all eleven steps demonstrates the full spec is satisfied end-to-end at pilot scale, corresponding directly to source doc §21's MVP acceptance criteria.
