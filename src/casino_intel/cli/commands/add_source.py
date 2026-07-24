"""`casino-intel add-source --url --type` (contracts/cli-commands.md)."""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from casino_intel.cli.context import AppContext
from casino_intel.models.ids import new_id
from casino_intel.models.source import Source
from casino_intel.models.vocab import SourceType
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.serialization import to_sheet_record

SOURCES_SHEET = "Sources"


def add_source(
    ctx: typer.Context,
    url: str = typer.Option(..., "--url"),
    type: str = typer.Option(
        ..., "--type", help="One of the source_type controlled vocabulary values."
    ),
) -> None:
    """Register a new Source without fetching it yet."""
    context: AppContext = ctx.obj

    try:
        source_type = SourceType(type)
    except ValueError:
        typer.echo(f"Invalid --type {type!r}. Must be one of: {[t.value for t in SourceType]}")
        raise typer.Exit(code=1) from None

    existing = context.sheets_client.batch_get_values([f"{SOURCES_SHEET}!A2:ZZ"]).get(
        f"{SOURCES_SHEET}!A2:ZZ", []
    )
    header = SHEET_HEADERS[SOURCES_SHEET]
    url_col = header.index("url")
    id_col = header.index("record_id")
    for row in existing:
        if len(row) > url_col and row[url_col] == url:
            typer.echo(f"Source already registered: {row[id_col]}")
            raise typer.Exit(code=4)

    now = datetime.now(UTC)
    source = Source(
        record_id=new_id("source"),
        created_at=now,
        created_by=context.actor,
        updated_at=now,
        source_type=source_type,
        url=url,
    )
    dumped = source.model_dump(mode="json")
    row_for_sheet = to_sheet_record(dumped, header)
    result = context.writer.append_record(
        SOURCES_SHEET, row_for_sheet, actor=context.actor, ingestion_run_id=context.ingestion_run_id
    )
    typer.echo(f"Registered source: {result.record_id}")
