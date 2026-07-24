"""`casino-intel research-queue list|run` (contracts/cli-commands.md).

A sub-Typer group (registered by `cli/app.py` via `add_typer`) since it has
two subcommands rather than being a single command.
"""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from casino_intel.cli.context import AppContext
from casino_intel.models.vocab import ChangeLogAction, TaskStatus, TaskType
from casino_intel.sheets.change_log import ChangeLogWriter
from casino_intel.sheets.safety import escape_row
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

app = typer.Typer(help="Inspect and run the Research Queue.")

SHEET_NAME = "Research Queue"
HEADER = SHEET_HEADERS[SHEET_NAME]

#: Task types this command can dispatch automatically, and the CLI command
#: each maps to. Everything else (audits, licence verification, source
#: discovery, conflict review) requires a human and is only ever noted, per
#: FR-031/FR-049 ("automated scoring is not a substitute for human review").
_FETCH_TASK_TYPES = {TaskType.DOWNLOAD_DOCUMENT}
_INGEST_TASK_TYPES = {
    TaskType.PARSE_DOCUMENT,
    TaskType.EXTRACT_METRIC,
    TaskType.CAPTURE_TRAFFIC,
    TaskType.CAPTURE_SEARCH_TRENDS,
    TaskType.CAPTURE_OFFER,
}


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


class _CtxShim:
    """Lets us call another Typer command function directly (in-process)
    without going through Click's CLI-invocation machinery."""

    def __init__(self, obj: AppContext) -> None:
        self.obj = obj


def _read_tasks(context: AppContext) -> list[dict[str, str]]:
    last_col = _column_letter(len(HEADER) - 1)
    rows = context.sheets_client.batch_get_values([f"{SHEET_NAME}!A2:{last_col}"]).get(
        f"{SHEET_NAME}!A2:{last_col}", []
    )
    tasks = []
    for row_number, row in enumerate(rows, start=2):
        record = dict(zip(HEADER, row, strict=False))
        record["_row_number"] = row_number
        tasks.append(record)
    return tasks


def _update_task(
    context: AppContext, task_id: str, row_number: int, updates: dict[str, str]
) -> None:
    if context.dry_run:
        return
    data = []
    for field_name, value in updates.items():
        col_idx = HEADER.index(field_name)
        data.append(
            {
                "range": f"{SHEET_NAME}!{_column_letter(col_idx)}{row_number}",
                "values": [escape_row([value])],
            }
        )
    context.sheets_client.batch_update_values(data)
    ChangeLogWriter(context.sheets_client).log(
        actor=context.actor,
        action=ChangeLogAction.UPDATE,
        sheet_name=SHEET_NAME,
        record_id=task_id,
        field_name=", ".join(updates.keys()),
        reason="research-queue run",
        ingestion_run_id=context.ingestion_run_id,
    )


@app.command("list")
def list_tasks(
    ctx: typer.Context,
    status: str = typer.Option(None, "--status"),
    priority: int = typer.Option(None, "--priority"),
) -> None:
    """Read-only listing of Research Queue tasks. Never mutates."""
    context: AppContext = ctx.obj
    tasks = _read_tasks(context)
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if priority is not None:
        tasks = [t for t in tasks if str(t.get("priority")) == str(priority)]

    if not tasks:
        typer.echo("No matching tasks.")
        return
    for task in tasks:
        typer.echo(
            f"{task.get('task_id')}\t{task.get('task_type')}\t"
            f"priority={task.get('priority')}\tstatus={task.get('status')}\t"
            f"{task.get('blocking_issue', '')}"
        )


@app.command("run")
def run_tasks(
    ctx: typer.Context,
    limit: int = typer.Option(10, "--limit"),
) -> None:
    """Execute up to `limit` open, highest-priority tasks by dispatching to
    fetch-source/ingest-source, or noting audit/manual tasks as such."""
    context: AppContext = ctx.obj
    tasks = [t for t in _read_tasks(context) if t.get("status") == TaskStatus.OPEN.value]
    tasks.sort(key=lambda t: int(t.get("priority") or 3))
    tasks = tasks[:limit]

    if not tasks:
        typer.echo("No open tasks to run.")
        return

    any_failed = False
    for task in tasks:
        task_id = task["task_id"]
        row_number = task["_row_number"]
        task_type = task.get("task_type", "")
        now = datetime.now(UTC).isoformat()

        outcome = _dispatch(context, task)
        attempt_count = int(task.get("attempt_count") or 0) + 1

        if outcome.completed:
            _update_task(
                context,
                task_id,
                row_number,
                {
                    "status": TaskStatus.DONE.value,
                    "attempt_count": str(attempt_count),
                    "last_attempt_at": now,
                    "completed_at": now,
                    "result_summary": outcome.message,
                },
            )
            typer.echo(f"[done] {task_id} ({task_type}): {outcome.message}")
        elif outcome.deferred:
            typer.echo(f"[deferred - manual] {task_id} ({task_type}): {outcome.message}")
        else:
            any_failed = True
            _update_task(
                context,
                task_id,
                row_number,
                {
                    "status": TaskStatus.BLOCKED.value,
                    "attempt_count": str(attempt_count),
                    "last_attempt_at": now,
                    "blocking_issue": outcome.message,
                },
            )
            typer.echo(f"[failed] {task_id} ({task_type}): {outcome.message}")

    if any_failed:
        raise typer.Exit(code=12)


class _DispatchOutcome:
    def __init__(self, completed: bool = False, deferred: bool = False, message: str = "") -> None:
        self.completed = completed
        self.deferred = deferred
        self.message = message


def _dispatch(context: AppContext, task: dict[str, str]) -> _DispatchOutcome:
    task_type_value = task.get("task_type", "")
    subject_type = task.get("subject_type", "")
    subject_id = task.get("subject_id", "")

    try:
        task_type = TaskType(task_type_value)
    except ValueError:
        return _DispatchOutcome(message=f"Unknown task_type {task_type_value!r}")

    if task_type in (TaskType.PERFORM_UX_AUDIT, TaskType.PERFORM_BRAND_AUDIT):
        return _DispatchOutcome(
            deferred=True,
            message="Subjective audits require a human auditor (FR-031/FR-049) — "
            "run `casino-intel record-ux-audit`/`record-brand-audit` manually.",
        )
    if task_type in (
        TaskType.DISCOVER_SOURCE,
        TaskType.VERIFY_LICENCE,
        TaskType.REVIEW_CONFLICT,
        TaskType.HUMAN_VALIDATION,
    ):
        return _DispatchOutcome(
            deferred=True, message=f"{task_type.value} requires human research/judgement."
        )

    if subject_type != "source" or not subject_id:
        return _DispatchOutcome(
            deferred=True,
            message=f"No source subject_id to act on for task_type={task_type.value}.",
        )

    from casino_intel.cli.commands import fetch_source as fetch_source_module
    from casino_intel.cli.commands import ingest_source as ingest_source_module

    try:
        if task_type in _FETCH_TASK_TYPES:
            fetch_source_module.fetch_source(_CtxShim(context), source_id=subject_id)
            return _DispatchOutcome(completed=True, message=f"Fetched source {subject_id}")
        if task_type in _INGEST_TASK_TYPES:
            ingest_source_module.ingest_source(_CtxShim(context), source_id=subject_id)
            return _DispatchOutcome(completed=True, message=f"Ingested source {subject_id}")
    except typer.Exit as exc:
        return _DispatchOutcome(message=f"Underlying command exited with code {exc.exit_code}")
    except Exception as exc:  # noqa: BLE001 - surfaced as a blocked task, not a crash
        return _DispatchOutcome(message=str(exc))

    return _DispatchOutcome(deferred=True, message=f"No automated handler for {task_type.value}")
