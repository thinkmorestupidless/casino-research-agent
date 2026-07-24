"""`casino-intel fetch-source --source-id SOURCE_ID` (contracts/cli-commands.md)."""

from __future__ import annotations

import typer

from casino_intel.cli.context import AppContext
from casino_intel.fetching.archiver import DocumentArchiver
from casino_intel.fetching.fetcher import Fetcher, FetchError, RobotsDisallowedError
from casino_intel.models.source import AccessDeniedError, Source
from casino_intel.services.research_task_service import ResearchTaskService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

SOURCES_SHEET = "Sources"


def _load_source(context: AppContext, source_id: str) -> Source:
    header = SHEET_HEADERS[SOURCES_SHEET]
    rows = context.sheets_client.batch_get_values([f"{SOURCES_SHEET}!A2:ZZ"]).get(
        f"{SOURCES_SHEET}!A2:ZZ", []
    )
    id_col = header.index("record_id")
    for row in rows:
        if len(row) > id_col and row[id_col] == source_id:
            record = dict(zip(header, row, strict=False))
            record.pop("record_id")
            return Source(record_id=source_id, **{k: v for k, v in record.items() if v != ""})
    raise LookupError(f"source_id {source_id!r} not found in {SOURCES_SHEET!r}")


def fetch_source(
    ctx: typer.Context,
    source_id: str = typer.Option(..., "--source-id"),
) -> None:
    """Download the source's content, archive to Drive, and create/update a Document row."""
    context: AppContext = ctx.obj

    try:
        source = _load_source(context, source_id)
    except LookupError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from None

    fetcher = Fetcher()
    try:
        fetch_result = fetcher.fetch(source)
    except (AccessDeniedError, RobotsDisallowedError) as exc:
        research_tasks = ResearchTaskService(context.sheets_client, dry_run=context.dry_run)
        research_tasks.flag_paywalled_source(source_id=source_id, url=source.url)
        typer.echo(f"Fetch blocked by access-policy check: {exc}")
        raise typer.Exit(code=5) from None
    except FetchError as exc:
        typer.echo(f"Fetch failed after retries: {exc}")
        raise typer.Exit(code=6) from None
    finally:
        fetcher.close()

    archiver = DocumentArchiver(context.drive_client, context.fingerprint_store, context.writer)
    result = archiver.archive_fetch(
        source_id=source_id,
        filename=source.url.rsplit("/", 1)[-1] or "document",
        content=fetch_result.content,
        mime_type=fetch_result.content_type or "application/octet-stream",
        actor=context.actor,
        ingestion_run_id=context.ingestion_run_id,
    )
    if result.is_new_version:
        typer.echo(f"New document archived: {result.document_id}")
    else:
        typer.echo(f"No content change — existing document retained: {result.document_id}")
