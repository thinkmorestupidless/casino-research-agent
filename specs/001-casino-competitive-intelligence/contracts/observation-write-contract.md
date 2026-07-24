# Observation Write Contract

Every code path that writes to the `Observations` sheet (or any domain-specific view sheet) — CLI ingestion, manual-correction tooling, the derived-metric job, the audit-recording flow — MUST go through the `casino_intel.sheets` write layer and MUST uphold the guarantees below. This is what makes FR-004 ("append, never overwrite"), FR-018 ("idempotent re-ingestion"), and FR-042 ("formula-injection protection") true regardless of which pipeline stage is calling in.

## 1. Append-only semantics

- A write path MAY create a new row with `status=active`.
- A write path MAY change an existing row's `status` from `active` to `superseded` or `rejected` — but MUST NOT alter any other field on that row once written (no in-place value correction; a correction is a new row plus a status change on the old one, both logged to `Change Log`).
- No write path may perform a raw cell overwrite of a previously-written data cell in `Observations`, `Financials`, `Traffic`, `Search Interest`, `Acquisition`, `Offers`, `Products`, `UX Audits`, `Brand Audits`, `Reputation`, `App Presence`, or `Derived Metrics`.

## 2. Idempotency / deduplication

- Before appending a new `Observation`, the write layer computes `fingerprint = sha256(subject_id | metric_id | period_start | period_end | as_of_date | geography | segment | source_id | raw_value)` (source doc §11.4) and checks it against the local SQLite fingerprint index.
- If the fingerprint matches an existing `active` row: **no write occurs**; the call returns the existing `observation_id` and a `duplicate=true` flag.
- If the fingerprint is new: the row is appended and the fingerprint is added to the index.
- The fingerprint index MUST be rebuildable from the workbook alone (it is a cache, not a second system of record) — a `rebuild-fingerprint-cache` internal operation re-derives it by reading all `active` `Observation` rows.

## 3. Formula-injection protection

- Before any string value is sent to the Sheets API, the write layer inspects the first character. If it is one of `= + - @`, the value is written using the API's raw/string value type (not `USER_ENTERED` formula-evaluated type) so Sheets treats it as literal text, not a formula — regardless of source (extracted text, manual entry, audit rationale, offer headline).
- This check applies to every text-bearing field, with no per-field opt-out.

## 4. Batch behavior and quota respect

- Writes for a single logical operation (e.g. one ingestion run's worth of new observations) are grouped into one `spreadsheets.values.batchUpdate` (or `batchUpdate` for formatting) call wherever the Sheets API size limits allow, never issued as N individual per-row API calls.
- On a `429`/quota-exceeded response, the write layer retries with exponential backoff (via `tenacity`) up to a bounded attempt count before surfacing a hard failure — it never silently drops rows on quota failure.
- A batch call either fully succeeds or the operation reports failure and writes nothing for that batch (no partial-row corruption within one batch).

## 5. Change logging

- Every row creation and every `status` transition MUST also produce a corresponding `Change Log` entry (append-only) recording the actor, action, affected `record_id`, and `ingestion_run_id` — the write layer enforces this as a paired operation, not an optional follow-up.

## 6. Validation gate

- The write layer never accepts a record that has not already passed the `validation` stage's business rules (FR-020). Records failing validation are instead routed to `Data Quality` creation, which is itself a write (governed by the same append-only/batch/logging rules above) but targets the `Data Quality` sheet, not the fact sheets.
