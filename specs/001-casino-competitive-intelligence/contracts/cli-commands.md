# CLI Command Contracts

The `casino-intel` CLI (Typer app, see `research.md` §9) is the operational interface onto the pipeline described in the spec. This document is the contract other tooling (tests, runbooks, future scheduling) can rely on: exact command names, arguments, exit codes, and side effects. Full flag lists and help text are implementation detail; behavioral guarantees below are not.

## Global contract

- Every command that can mutate the workbook, Drive archive, or local cache MUST support `--dry-run`, which performs all read/fetch/parse/validate steps and prints/logs the writes it *would* make, without making them.
- Every command MUST exit `0` on success, a non-zero code on failure, and MUST NOT leave partially-written multi-row batches in the workbook on failure (batch writes are all-or-nothing per Sheets API call, per source doc §17.1).
- Every command MUST accept `--ingestion-run-id` to attach its writes to a specific run for audit purposes; if omitted, a new run ID is generated and printed to stdout.
- Credentials are read only from environment variables (`GOOGLE_APPLICATION_CREDENTIALS`, `SPREADSHEET_ID`) — never accepted as CLI arguments (avoids secrets in shell history/process listings).

## Commands

### `casino-intel initialise-workbook`

- **Purpose**: Create the workbook (or verify an existing one referenced by `SPREADSHEET_ID`) with all 23 tabs (source doc §5), headers, frozen header rows, data validation, named ranges for `Config` vocabularies, and conditional formatting for confidence/quality columns.
- **Preconditions**: `GOOGLE_APPLICATION_CREDENTIALS` valid; service account has edit access to the target spreadsheet (or Drive create permission if creating new).
- **Postconditions**: All 23 tabs exist with correct headers; `Config` populated from `config/vocabularies.yaml`, `config/metrics.yaml`, `config/audit-rubrics.yaml`; `README` populated with workbook/schema version and target market.
- **Idempotency**: Safe to re-run against an existing workbook — MUST NOT duplicate tabs or overwrite existing data rows; only adds missing tabs/headers/vocab entries.
- **Exit codes**: `0` success; `2` spreadsheet unreachable/permission denied; `3` partial-initialisation detected requiring manual review.

### `casino-intel add-source --url URL --type TYPE`

- **Purpose**: Register a new `Source` record (FR-011) without fetching it yet.
- **Preconditions**: `TYPE` must be a value from the `source_type` controlled vocabulary; command fails with a validation error otherwise (never silently accepts an unknown type).
- **Postconditions**: One new `Source` row, `status=active`, `accessed_at` unset until first fetch.
- **Exit codes**: `0` success; `1` invalid `TYPE`; `4` duplicate `url` already registered (prints existing `source_id`).

### `casino-intel fetch-source --source-id SOURCE_ID`

- **Purpose**: Download the source's content (respecting robots/terms/paywall flags — FR-013), archive to Drive, compute content hash, create/update a `Document` row.
- **Preconditions**: `Source.paywalled=false` and `Source.authentication_required=false`; command refuses to fetch and exits non-zero otherwise, directing the operator to a manual capture path.
- **Postconditions**: New `Document` row if content hash differs from the most recent `Document` for this source; no new row if unchanged (logged as a no-op).
- **Exit codes**: `0` success (including no-op-unchanged case); `5` fetch blocked by access-policy check; `6` network/HTTP failure after retry budget exhausted.

### `casino-intel ingest-source --source-id SOURCE_ID`

- **Purpose**: Run the full pipeline for one source: fetch (if needed) → parse → extract → normalise → validate → deduplicate → append as unreviewed `Observation` rows → raise `DataQualityIssue` rows for anything invalid (source doc §11.3 workflow).
- **Postconditions**: Zero or more new `Observation` rows, all `review_status=unreviewed`; zero duplicate rows for any fingerprint already `active` (FR-018); any invalid candidate fact appears in `Data Quality`, never silently dropped and never silently accepted.
- **Exit codes**: `0` success (even if zero new observations — e.g. unchanged source); `7` parse failure; `8` validation-layer internal error (distinct from individual record validation failures, which are not command failures).

### `casino-intel import-file --path FILE`

- **Purpose**: Same pipeline as `ingest-source`, entry point for a manually-supplied local file (CSV/XLSX/PDF/HTML) not yet fetched from a live URL — still requires an associated `--source-id` to satisfy FR-011/FR-020's "missing source" rule.
- **Exit codes**: `1` if `--source-id` omitted or does not exist; otherwise as `ingest-source`.

### `casino-intel validate`

- **Purpose**: Re-run business-rule validation (FR-020) across existing records without re-ingesting, e.g. after a manual edit in the workbook. Refreshes `Data Quality`.
- **Postconditions**: `Data Quality` reflects current state; no `Observation`/`Brand`/etc. rows are modified.
- **Exit codes**: `0` always on successful run (issues found are reported, not command failures); non-zero only on a run-level error (e.g. workbook unreachable).

### `casino-intel derive`

- **Purpose**: Recalculate derived metrics (FR-035–FR-037) from currently `approved` observations only.
- **Postconditions**: New `DerivedMetric` rows for newly-possible or changed calculations; existing `DerivedMetric` rows are never edited in place (FR-037); calculations skipped (not fabricated) where inputs are insufficiently comparable, logged as skipped with reason.
- **Exit codes**: `0` success; `9` formula-registry load error.

### `casino-intel refresh-summary`

- **Purpose**: Regenerate the `Summary` sheet from current `active`/`approved` data.
- **Postconditions**: `Summary` shows, per brand, latest value per tracked signal, evidence/confidence marker, operator-vs-brand-level marker, observation age, and research gaps (FR-041, SC-013). Never hides operator-vs-brand level (spec §9.22 rule).
- **Exit codes**: `0` success; `10` required upstream data (e.g. no brands registered) missing.

### `casino-intel export --output DIR`

- **Purpose**: Full CSV export of every sheet (FR-043, SC-011).
- **Postconditions**: One CSV per tab written to `DIR`, byte-faithful to current sheet contents (no data loss).
- **Exit codes**: `0` success; `11` write-permission failure on `DIR`.

### `casino-intel research-queue list [--status STATUS] [--priority N]`

- **Purpose**: Read-only listing of `ResearchTask` rows (FR-040). Never mutates.
- **Exit codes**: `0` always (empty list is not an error).

### `casino-intel research-queue run [--limit N]`

- **Purpose**: Execute up to `N` open, highest-priority `ResearchTask` rows by dispatching to the appropriate pipeline command (`fetch-source`, `ingest-source`, or a manual-task notice for audit-type tasks, which cannot be automated per FR-031/FR-049).
- **Postconditions**: Each executed task's `status`, `attempt_count`, `last_attempt_at` updated; `blocking_issue` set on failure rather than silently retried indefinitely.
- **Exit codes**: `0` if all attempted tasks completed or were correctly deferred; `12` if one or more attempted tasks failed (individual task failures listed in output; command failure ≠ silent skip).

## Extraction/normalisation internal contract

See `extraction-record.schema.json` for the JSON contract between the `parsing`/`extraction` stage and the `normalisation`/`validation` stage (source doc §11.5). This is an internal module boundary, not a public CLI surface, but is treated as a contract because independent parser implementations (HTML/PDF/XLSX) must all emit it identically.

## Sheets write contract

See `observation-write-contract.md` for the idempotency, deduplication, and formula-injection-escaping guarantees that every write path (CLI commands above, plus any future direct API use) must uphold.
