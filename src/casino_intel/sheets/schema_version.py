"""Schema versioning (spec source doc §17.3): a single current version
constant, a reader for the version currently recorded in a live workbook's
`README` tab, and an append-only file-based migration log (`docs/migrations.md`)
— there is no dedicated sheet tab for this (the workbook has a fixed set of
23 tabs; a migration log is repository-tracked, like migration scripts).

Column additions are backward-compatible by construction: `SHEET_HEADERS`
(schema_definitions.py) is additive-only in practice — never rename or
remove a column without bumping `CURRENT_SCHEMA_VERSION` and adding a
migration log entry here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from casino_intel.sheets.client import SheetsClient

CURRENT_SCHEMA_VERSION = "0.1.0"
MIGRATIONS_LOG_PATH = Path("docs/migrations.md")

README_SHEET = "README"


def get_recorded_schema_version(client: SheetsClient) -> str | None:
    """Read the `schema_version` value currently recorded in `README!B2`
    (column order: workbook_version, schema_version, ...)."""
    values = client.batch_get_values([f"{README_SHEET}!B2"]).get(f"{README_SHEET}!B2", [])
    if values and values[0]:
        return values[0][0]
    return None


def is_up_to_date(client: SheetsClient) -> bool:
    """True if the workbook's recorded schema_version matches the code's
    `CURRENT_SCHEMA_VERSION` (or nothing has been recorded yet — a fresh
    workbook is brought up to date by `initialise-workbook` itself)."""
    recorded = get_recorded_schema_version(client)
    return recorded is None or recorded == CURRENT_SCHEMA_VERSION


def record_migration(
    from_version: str, to_version: str, description: str, path: Path = MIGRATIONS_LOG_PATH
) -> None:
    """Append a migration entry to the repository-tracked migration log.

    This is a file write, not a sheet write — migrations are a
    repository/versioning concern, not a fact requiring the evidence model.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "# Schema migration log\n\n"
            "Append-only record of workbook schema changes "
            "(source doc §17.3). Never rewrite a prior entry.\n\n"
        )
    entry = (
        f"## {from_version} -> {to_version}\n\n"
        f"- Date: {datetime.now(UTC).date().isoformat()}\n"
        f"- {description}\n\n"
    )
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
