"""The append-only write layer every fact-writing code path must use
(contracts/observation-write-contract.md).

Guarantees enforced here, centrally, so no caller can bypass them:

1. Append-only semantics — new rows only; the one allowed mutation is a
   `status` transition on an existing row (never any other field).
2. Idempotency/dedup for canonical Observations via the fingerprint store.
3. Formula-injection escaping on every cell.
4. A paired Change Log entry for every write.
"""

from __future__ import annotations

from dataclasses import dataclass

from casino_intel.cache.fingerprint_store import FingerprintStore
from casino_intel.models.base import InvalidStatusTransition
from casino_intel.models.vocab import RECORD_STATUS_TRANSITIONS, ChangeLogAction, RecordStatus
from casino_intel.sheets.change_log import ChangeLogWriter
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.safety import escape_row
from casino_intel.validation.fingerprint import fingerprint as compute_fingerprint


@dataclass(frozen=True)
class AppendResult:
    written: bool
    record_id: str
    duplicate: bool = False


def _column_letter(index: int) -> str:
    """Convert a 0-based column index to an A1-style column letter."""
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


class SheetsWriter:
    """Append-only writer with idempotency, escaping, and change logging."""

    def __init__(
        self,
        client: SheetsClient,
        fingerprint_store: FingerprintStore,
        change_log: ChangeLogWriter,
        dry_run: bool = False,
    ) -> None:
        self.client = client
        self.fingerprint_store = fingerprint_store
        self.change_log = change_log
        self.dry_run = dry_run
        self._header_cache: dict[str, list[str]] = {}

    def _header(self, sheet_name: str) -> list[str]:
        if sheet_name not in self._header_cache:
            values = self.client.batch_get_values([f"{sheet_name}!1:1"])
            rows = values.get(f"{sheet_name}!1:1", [])
            self._header_cache[sheet_name] = rows[0] if rows else []
        return self._header_cache[sheet_name]

    def append_record(
        self,
        sheet_name: str,
        record: dict[str, object],
        *,
        actor: str,
        ingestion_run_id: str | None = None,
    ) -> AppendResult:
        """Append a new row. Never call this to modify an existing record."""
        header = self._header(sheet_name)
        row = escape_row([record.get(col, "") for col in header])
        if not self.dry_run:
            self.client.append_rows(sheet_name, [row])
        self.change_log.log(
            actor=actor,
            action=ChangeLogAction.CREATE,
            sheet_name=sheet_name,
            record_id=str(record.get("record_id", "")),
            source_id=record.get("source_id"),  # type: ignore[arg-type]
            ingestion_run_id=ingestion_run_id,
        )
        return AppendResult(written=not self.dry_run, record_id=str(record.get("record_id", "")))

    def append_records(
        self,
        sheet_name: str,
        records: list[dict[str, object]],
        *,
        actor: str,
        ingestion_run_id: str | None = None,
    ) -> list[AppendResult]:
        """Append many rows to one sheet in a SINGLE append call, with all
        their Change Log entries written in a single second call.

        For bulk, non-Observation writes (e.g. seeding Operators/Brands) this
        keeps the whole batch to two API requests instead of two-per-record,
        staying well under the Sheets per-minute write quota. Not for
        canonical Observations — those must go through ``append_observation``
        for fingerprint dedup.
        """
        if not records:
            return []
        header = self._header(sheet_name)
        rows = [escape_row([record.get(col, "") for col in header]) for record in records]
        if not self.dry_run:
            self.client.append_rows(sheet_name, rows)
        self.change_log.log_many(
            [
                {
                    "actor": actor,
                    "action": ChangeLogAction.CREATE,
                    "sheet_name": sheet_name,
                    "record_id": str(record.get("record_id", "")),
                    "source_id": record.get("source_id"),
                    "ingestion_run_id": ingestion_run_id,
                }
                for record in records
            ]
        )
        return [
            AppendResult(written=not self.dry_run, record_id=str(record.get("record_id", "")))
            for record in records
        ]

    def append_observation(
        self,
        sheet_name: str,
        observation: dict[str, object],
        *,
        actor: str,
        ingestion_run_id: str | None = None,
    ) -> AppendResult:
        """Append a canonical Observation row, deduplicating by fingerprint
        per contracts/observation-write-contract.md §2."""
        fp = compute_fingerprint(observation)
        existing_id = self.fingerprint_store.has_fingerprint(fp)
        if existing_id:
            return AppendResult(written=False, record_id=existing_id, duplicate=True)

        record = {**observation, "fingerprint": fp}
        result = self.append_record(
            sheet_name, record, actor=actor, ingestion_run_id=ingestion_run_id
        )
        if not self.dry_run:
            self.fingerprint_store.record_fingerprint(fp, result.record_id)
        return result

    def transition_status(
        self,
        sheet_name: str,
        record_id: str,
        new_status: RecordStatus,
        *,
        actor: str,
        current_status: RecordStatus,
        id_column: str = "record_id",
        status_column: str = "status",
        reason: str = "",
        ingestion_run_id: str | None = None,
        action: ChangeLogAction = ChangeLogAction.UPDATE,
    ) -> None:
        """Transition an existing row's `status` field — the one field that
        may be mutated in place. No other field may ever be changed this way.
        """
        allowed = RECORD_STATUS_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise InvalidStatusTransition(
                f"Cannot transition status from {current_status!r} to {new_status!r}"
            )

        header = self._header(sheet_name)
        id_idx = header.index(id_column)
        status_idx = header.index(status_column)

        if not self.dry_run:
            id_range = f"{sheet_name}!{_column_letter(id_idx)}2:{_column_letter(id_idx)}"
            values = self.client.batch_get_values([id_range]).get(id_range, [])
            row_number = None
            for offset, row in enumerate(values, start=2):
                if row and row[0] == record_id:
                    row_number = offset
                    break
            if row_number is None:
                raise LookupError(f"record_id {record_id!r} not found in {sheet_name!r}")

            target_range = f"{sheet_name}!{_column_letter(status_idx)}{row_number}"
            self.client.batch_update_values(
                [{"range": target_range, "values": [[new_status.value]]}]
            )

        self.change_log.log(
            actor=actor,
            action=action,
            sheet_name=sheet_name,
            record_id=record_id,
            field_name=status_column,
            old_value=current_status.value,
            new_value=new_status.value,
            reason=reason,
            ingestion_run_id=ingestion_run_id,
        )
