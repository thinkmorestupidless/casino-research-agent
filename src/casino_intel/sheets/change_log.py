"""Append-only Change Log writer (spec FR-038, source doc §9.20).

Every mutation elsewhere in the codebase must produce a corresponding entry
here — enforced by having `sheets/writer.py` call this module directly
rather than leaving it to individual callers (contracts/observation-write-contract.md §5).
"""

from __future__ import annotations

from datetime import UTC, datetime

from casino_intel.models.ids import new_id
from casino_intel.models.vocab import ChangeLogAction
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.safety import escape_row

SHEET_NAME = "Change Log"

#: record_id, timestamp, actor, action, sheet_name, record_id, field_name,
#: old_value, new_value, reason, source_id, ingestion_run_id
COLUMNS = [
    "change_id",
    "timestamp",
    "actor",
    "action",
    "sheet_name",
    "record_id",
    "field_name",
    "old_value",
    "new_value",
    "reason",
    "source_id",
    "ingestion_run_id",
]


class ChangeLogWriter:
    def __init__(self, client: SheetsClient, dry_run: bool = False) -> None:
        self.client = client
        self.dry_run = dry_run

    def log(
        self,
        *,
        actor: str,
        action: ChangeLogAction,
        sheet_name: str,
        record_id: str,
        field_name: str = "",
        old_value: str = "",
        new_value: str = "",
        reason: str = "",
        source_id: str | None = None,
        ingestion_run_id: str | None = None,
    ) -> dict[str, str]:
        """Append one Change Log row. Rows are never updated or deleted."""
        entry = {
            "change_id": new_id("change_log"),
            "timestamp": datetime.now(UTC).isoformat(),
            "actor": actor,
            "action": action.value if isinstance(action, ChangeLogAction) else action,
            "sheet_name": sheet_name,
            "record_id": record_id,
            "field_name": field_name,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "source_id": source_id or "",
            "ingestion_run_id": ingestion_run_id or "",
        }
        if not self.dry_run:
            row = escape_row([entry[col] for col in COLUMNS])
            self.client.append_rows(SHEET_NAME, [row])
        return entry
