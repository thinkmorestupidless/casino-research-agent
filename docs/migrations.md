# Schema migration log

Append-only record of workbook schema changes (source doc §17.3). Never rewrite a prior entry — add a new one, even to describe a correction.

## (none) -> 0.1.0

- Date: 2026-07-24
- Initial schema: all 23 tabs created per `specs/001-casino-competitive-intelligence/data-model.md` and `src/casino_intel/sheets/schema_definitions.py`. No prior version existed.
