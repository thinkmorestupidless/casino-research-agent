"""Research Task auto-creation on ingestion blockers (spec FR-040,
data-model.md "Entity: ResearchTask", `casino-intel research-queue`).

A paywalled/auth-required source, a parse failure, or an unresolved
high-confidence conflict becomes a queued, prioritised task rather than a
silently dropped gap — writes go to the `Research Queue` sheet via the
append-only `SheetsClient`, never overwritten in place.
"""

from __future__ import annotations

from datetime import UTC, datetime

from casino_intel.models.ids import new_id
from casino_intel.models.vocab import TaskStatus, TaskType
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.safety import escape_row
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

SHEET_NAME = "Research Queue"
COLUMNS = SHEET_HEADERS[SHEET_NAME]


class ResearchTaskService:
    def __init__(self, client: SheetsClient, dry_run: bool = False) -> None:
        self.client = client
        self.dry_run = dry_run

    def create_task(
        self,
        *,
        subject_type: str,
        subject_id: str,
        task_type: TaskType | str,
        priority: int = 3,
        requested_metric_ids: list[str] | None = None,
        suggested_sources: list[str] | None = None,
        blocking_issue: str = "",
        assigned_to: str = "",
    ) -> dict[str, object]:
        """Append a new, `open` `ResearchTask` row. Never overwrites a prior task."""
        now = datetime.now(UTC).isoformat()
        entry: dict[str, object] = {
            "task_id": new_id("research_task"),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "task_type": task_type.value if isinstance(task_type, TaskType) else task_type,
            "priority": priority,
            "requested_metric_ids": ", ".join(requested_metric_ids or []),
            "suggested_sources": ", ".join(suggested_sources or []),
            "assigned_to": assigned_to,
            "status": TaskStatus.OPEN.value,
            "attempt_count": 0,
            "last_attempt_at": "",
            "next_attempt_after": "",
            "blocking_issue": blocking_issue,
            "result_summary": "",
            "created_at": now,
            "completed_at": "",
        }
        if not self.dry_run:
            row = escape_row([entry[col] for col in COLUMNS])
            self.client.append_rows(SHEET_NAME, [row])
        return entry

    def flag_paywalled_source(
        self, *, source_id: str, url: str, requested_metric_ids: list[str] | None = None
    ) -> dict[str, object]:
        """A source flagged `paywalled`/`authentication_required` blocks
        automated fetch (FR-013) — queue it for manual capture instead of
        dropping the gap silently."""
        return self.create_task(
            subject_type="source",
            subject_id=source_id,
            task_type=TaskType.DOWNLOAD_DOCUMENT,
            priority=2,
            requested_metric_ids=requested_metric_ids,
            suggested_sources=[source_id],
            blocking_issue=f"Source {source_id} ({url}) is paywalled/authentication-required "
            "and must be captured manually.",
        )

    def flag_parse_failure(
        self, *, source_id: str, document_id: str, error: str
    ) -> dict[str, object]:
        return self.create_task(
            subject_type="source",
            subject_id=source_id,
            task_type=TaskType.PARSE_DOCUMENT,
            priority=2,
            suggested_sources=[source_id],
            blocking_issue=f"Failed to parse document {document_id}: {error}",
        )

    def flag_unresolved_conflict(
        self,
        *,
        subject_type: str,
        subject_id: str,
        metric_id: str,
        description: str,
    ) -> dict[str, object]:
        return self.create_task(
            subject_type=subject_type,
            subject_id=subject_id,
            task_type=TaskType.REVIEW_CONFLICT,
            priority=1,
            requested_metric_ids=[metric_id],
            blocking_issue=description,
        )
