# Runbook

## Setup

1. Create a Google Cloud service account; enable the Sheets API and Drive API for its project.
2. Download the service-account JSON key; set `GOOGLE_APPLICATION_CREDENTIALS` to its path (see `.env.example`).
3. Create (or identify) a target Google Sheet and share it with the service account's email as an Editor.
4. Set `SPREADSHEET_ID` to that sheet's ID.
5. Install dependencies: `pip install -e ".[dev]"`.
6. Run `casino-intel initialise-workbook` to create/verify all tabs.

## Credential rotation

- Rotate the service-account key in Google Cloud Console; update `GOOGLE_APPLICATION_CREDENTIALS` to point at the new key file; delete the old key from disk and from Google Cloud once the new one is confirmed working (`casino-intel validate` should succeed).
- Credentials are never stored in the workbook, the repository, or any exported file (FR-050) — only referenced via environment variable.

## Ingestion run triage

1. `casino-intel research-queue list --status open` to see outstanding work.
2. `casino-intel research-queue run --limit N` to execute the highest-priority items.
3. Any task left with a non-empty `blocking_issue` needs manual attention (e.g. a paywalled source, an unparseable document).
4. `casino-intel ingest-source --source-id <id> --dry-run` to preview what a run would write before committing.

## Data Quality resolution workflow

1. Review new rows in the `Data Quality` sheet after each ingestion run.
2. For each issue, either fix the underlying source data mapping (metric registry, vocabulary) and re-run `casino-intel validate`, or mark the issue `wont_fix` with a reason if it is not actionable.
3. Never mark an issue `resolved` without either correcting the underlying record or confirming it was a false positive.

## Quickstart validation record

See `specs/001-casino-competitive-intelligence/quickstart.md` for the full end-to-end validation sequence.

**2026-07-24 — validated against the in-memory test harness, not yet against a live Google Sheet.** This development sandbox has no real Google Cloud project or service-account credentials available, so a live run against an actual spreadsheet has not been performed. What *was* executed and passed, exercising the exact same CLI command sequence a real operator would run (`tests/integration/test_quickstart_full_flow.py`, plus the per-user-story integration tests it complements):

- Steps 1-2 (workbook bootstrap, brand/operator registration): `initialise-workbook` creates all 23 tabs idempotently; operators/brands register and link correctly — `tests/integration/test_user_story_1.py`.
- Step 3 (register + ingest a regulator source): `add-source` + `import-file --importer ukgc` against the UKGC XLSX fixture produces observations with full provenance; re-running the identical import produces **zero duplicates** — `test_quickstart_full_flow.py`, `test_user_story_2.py`.
- Step 4 (three formats): HTML, PDF and XLSX/CSV fixtures all ingest correctly — `test_user_story_2.py`.
- Step 5 (Data Quality routing): an unknown-metric observation is routed to `Data Quality`, never silently accepted — `test_quickstart_full_flow.py`.
- Step 6 (review workflow): `unreviewed -> machine_checked -> human_reviewed -> approved` transitions work and are change-logged.
- Step 7 (derive): `derive` runs cleanly end-to-end (with this pilot-scale fixture set, most metric pairs are legitimately incompatible/absent, so derivation correctly computes nothing rather than fabricating a value — see `tests/unit/test_derivation.py` for the formula-level proof this works when compatible inputs exist).
- Step 8 (audits): rationale-required validation and the journey-safety stop points are enforced — `test_user_story_3.py`.
- Step 9 (summary): `refresh-summary` distinguishes operator- vs brand-level figures and flags gaps — `test_user_story_5.py`.
- Steps 10-11 (export, secrets hygiene): CSV export is byte-faithful to the live sheet; no credential ever appears in the workbook, an export, or a CLI option — `test_no_secrets_leak.py`.

**Finding from this exercise**: the first full run of `test_quickstart_full_flow.py` exposed a real idempotency gap — the local fingerprint/document-hash cache (`.cache/casino_intel.sqlite3`) is a pure performance cache, and a *cold* cache (fresh checkout, deleted `.cache/`, new machine) had no fallback, so re-ingesting an unchanged source on a cold cache would have created duplicate rows, violating SC-005. Fixed by warming the cache from the live `Observations`/`Documents` sheets on first access whenever it's empty (`src/casino_intel/services/cache_warmup.py`, wired into `AppContext.fingerprint_store`) — one bounded batch read, not a per-call cost. Regression-tested in `tests/unit/test_cache_warmup.py`.

**Before running against a real spreadsheet**, follow the Setup section above, then re-run `test_quickstart_full_flow.py`'s command sequence manually via the actual `casino-intel` CLI and update this record with the live result.
