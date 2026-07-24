"""`casino-intel ingest-source --source-id SOURCE_ID` (contracts/cli-commands.md).

Runs the full pipeline for one source: fetch (if needed) -> parse ->
extract -> normalise -> validate -> deduplicate -> append as unreviewed
Observation rows -> raise Data Quality rows for anything invalid.
"""

from __future__ import annotations

import typer

from casino_intel.cli.context import AppContext
from casino_intel.fetching.archiver import DocumentArchiver
from casino_intel.fetching.fetcher import Fetcher, FetchError
from casino_intel.models.source import AccessDeniedError, Source
from casino_intel.services.ingestion_run import IngestionRun, build_extract_fn
from casino_intel.services.observation_service import ObservationService
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


def ingest_source(
    ctx: typer.Context,
    source_id: str = typer.Option(..., "--source-id"),
    importer: str = typer.Option(
        "generic", "--importer", help="Domain importer to use: ukgc, operator_report, or generic."
    ),
    subject_id: str = typer.Option(
        "", "--subject-id", help="Subject (market/operator) record_id for the domain importer."
    ),
    period_start: str = typer.Option("", "--period-start"),
    period_end: str = typer.Option("", "--period-end"),
) -> None:
    context: AppContext = ctx.obj

    try:
        source = _load_source(context, source_id)
    except LookupError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from None

    fetcher = Fetcher()
    archiver = DocumentArchiver(context.drive_client, context.fingerprint_store, context.writer)
    observation_service = ObservationService(
        context.writer, context.data_quality, context.metric_registry
    )
    orchestrator = IngestionRun(
        fetcher=fetcher,
        archiver=archiver,
        observation_service=observation_service,
        data_quality=context.data_quality,
        metric_registry=context.metric_registry,
    )
    extract_fn = build_extract_fn(
        importer,
        source_id=source_id,
        subject_id=subject_id,
        period_start=period_start,
        period_end=period_end,
    )

    try:
        outcome = orchestrator.run(
            source=source,
            extract_fn=extract_fn,
            actor=context.actor,
            ingestion_run_id=context.ingestion_run_id,
        )
    except AccessDeniedError as exc:
        research_tasks = ResearchTaskService(context.sheets_client, dry_run=context.dry_run)
        research_tasks.flag_paywalled_source(source_id=source_id, url=source.url)
        typer.echo(f"Ingestion blocked by access-policy check: {exc}")
        raise typer.Exit(code=5) from None
    except FetchError as exc:
        typer.echo(f"Fetch failed after retries: {exc}")
        raise typer.Exit(code=6) from None
    finally:
        fetcher.close()

    if outcome.errors:
        research_tasks = ResearchTaskService(context.sheets_client, dry_run=context.dry_run)
        for error in outcome.errors:
            research_tasks.flag_parse_failure(
                source_id=source_id, document_id=outcome.document_id or "", error=error
            )
        typer.echo(f"Parse failure: {'; '.join(outcome.errors)}")
        raise typer.Exit(code=7)

    typer.echo(
        f"Ingested {source_id}: {outcome.new_observations} new, "
        f"{outcome.duplicate_observations} duplicate, "
        f"{outcome.data_quality_issues} data-quality issues "
        f"(document={outcome.document_id}, "
        f"unchanged={outcome.skipped_no_content_change})"
    )
