"""Human review workflow (spec FR-017, data-model.md `review_status` state
machine): approve / reject / correct a record.

`review_status` carries its own transition graph
(`REVIEW_STATUS_TRANSITIONS` in `models/vocab.py`), separate from the
`status` field `SheetsWriter.transition_status` mutates in place. This
service performs the one in-place mutation `review_status` permits,
directly through `SheetsClient` (mirroring `SheetsWriter.transition_status`'s
approach) — never any other field — and pairs every transition with a
Change Log entry (contracts/observation-write-contract.md §1/§5).

A "correction" is never an in-place edit of a fact's values: it rejects the
existing row's `review_status` and appends a brand-new row through the
normal append-only write path, so the audit trail is preserved.
"""

from __future__ import annotations

from casino_intel.models.base import InvalidStatusTransition
from casino_intel.models.ids import entity_type_of, new_id
from casino_intel.models.vocab import REVIEW_STATUS_TRANSITIONS, ChangeLogAction, ReviewStatus
from casino_intel.sheets.change_log import ChangeLogWriter
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.safety import escape_cell_value
from casino_intel.sheets.writer import SheetsWriter, _column_letter

_REVIEW_ACTION_FOR: dict[ReviewStatus, ChangeLogAction] = {
    ReviewStatus.APPROVED: ChangeLogAction.APPROVE,
    ReviewStatus.REJECTED: ChangeLogAction.REJECT,
}


class ReviewService:
    def __init__(
        self, client: SheetsClient, change_log: ChangeLogWriter, dry_run: bool = False
    ) -> None:
        self.client = client
        self.change_log = change_log
        self.dry_run = dry_run
        self._header_cache: dict[str, list[str]] = {}

    def _header(self, sheet_name: str) -> list[str]:
        if sheet_name not in self._header_cache:
            values = self.client.batch_get_values([f"{sheet_name}!1:1"])
            rows = values.get(f"{sheet_name}!1:1", [])
            self._header_cache[sheet_name] = rows[0] if rows else []
        return self._header_cache[sheet_name]

    def _find_row(
        self, sheet_name: str, record_id: str, id_column: str = "record_id"
    ) -> tuple[int, dict[str, str]]:
        header = self._header(sheet_name)
        id_idx = header.index(id_column)
        id_range = f"{sheet_name}!{_column_letter(id_idx)}2:{_column_letter(id_idx)}"
        id_values = self.client.batch_get_values([id_range]).get(id_range, [])
        for offset, row in enumerate(id_values, start=2):
            if row and row[0] == record_id:
                full_range = f"{sheet_name}!{offset}:{offset}"
                full_row = self.client.batch_get_values([full_range]).get(full_range, [[]])
                data = full_row[0] if full_row else []
                return offset, dict(zip(header, data, strict=False))
        raise LookupError(f"record_id {record_id!r} not found in {sheet_name!r}")

    def transition_review_status(
        self,
        sheet_name: str,
        record_id: str,
        new_review_status: ReviewStatus,
        *,
        actor: str,
        reason: str = "",
        ingestion_run_id: str | None = None,
        review_status_column: str = "review_status",
    ) -> None:
        row_number, record = self._find_row(sheet_name, record_id)
        current = ReviewStatus(record.get(review_status_column) or ReviewStatus.UNREVIEWED.value)
        allowed = REVIEW_STATUS_TRANSITIONS.get(current, set())
        if new_review_status not in allowed:
            raise InvalidStatusTransition(
                f"Cannot transition review_status from {current!r} to {new_review_status!r}"
            )

        header = self._header(sheet_name)
        col_idx = header.index(review_status_column)
        if not self.dry_run:
            target_range = f"{sheet_name}!{_column_letter(col_idx)}{row_number}"
            self.client.batch_update_values(
                [{"range": target_range, "values": [[escape_cell_value(new_review_status.value)]]}]
            )

        self.change_log.log(
            actor=actor,
            action=_REVIEW_ACTION_FOR.get(new_review_status, ChangeLogAction.UPDATE),
            sheet_name=sheet_name,
            record_id=record_id,
            field_name=review_status_column,
            old_value=current.value,
            new_value=new_review_status.value,
            reason=reason,
            ingestion_run_id=ingestion_run_id,
        )

    def approve(
        self,
        sheet_name: str,
        record_id: str,
        *,
        actor: str,
        reason: str = "",
        ingestion_run_id: str | None = None,
    ) -> None:
        self.transition_review_status(
            sheet_name,
            record_id,
            ReviewStatus.APPROVED,
            actor=actor,
            reason=reason,
            ingestion_run_id=ingestion_run_id,
        )

    def reject(
        self,
        sheet_name: str,
        record_id: str,
        *,
        actor: str,
        reason: str = "",
        ingestion_run_id: str | None = None,
    ) -> None:
        self.transition_review_status(
            sheet_name,
            record_id,
            ReviewStatus.REJECTED,
            actor=actor,
            reason=reason,
            ingestion_run_id=ingestion_run_id,
        )

    def mark_machine_checked(
        self, sheet_name: str, record_id: str, *, actor: str, ingestion_run_id: str | None = None
    ) -> None:
        self.transition_review_status(
            sheet_name,
            record_id,
            ReviewStatus.MACHINE_CHECKED,
            actor=actor,
            ingestion_run_id=ingestion_run_id,
        )

    def mark_human_reviewed(
        self, sheet_name: str, record_id: str, *, actor: str, ingestion_run_id: str | None = None
    ) -> None:
        self.transition_review_status(
            sheet_name,
            record_id,
            ReviewStatus.HUMAN_REVIEWED,
            actor=actor,
            ingestion_run_id=ingestion_run_id,
        )

    def correct(
        self,
        sheet_name: str,
        record_id: str,
        *,
        writer: SheetsWriter,
        corrected_fields: dict[str, object],
        actor: str,
        reason: str = "",
        ingestion_run_id: str | None = None,
    ) -> str:
        """Reject `record_id`'s review_status and append a brand-new
        corrected row carrying `corrected_fields` merged over the original
        (a correction is a new row, never an in-place edit — see module
        docstring). Returns the new row's `record_id`."""
        _, record = self._find_row(sheet_name, record_id)
        self.reject(
            sheet_name,
            record_id,
            actor=actor,
            reason=reason or "superseded by correction",
            ingestion_run_id=ingestion_run_id,
        )

        entity_type = entity_type_of(record_id)
        new_record_id = new_id(entity_type) if entity_type else record_id
        corrected = {
            **record,
            **corrected_fields,
            "record_id": new_record_id,
            "review_status": ReviewStatus.UNREVIEWED.value,
        }
        result = writer.append_record(
            sheet_name, corrected, actor=actor, ingestion_run_id=ingestion_run_id
        )
        return result.record_id
