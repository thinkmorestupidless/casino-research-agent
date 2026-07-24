"""`casino-intel export --output DIR` (contracts/cli-commands.md).

Full, byte-faithful CSV export of every tab — no data loss relative to the
live workbook (spec FR-043, SC-011).
"""

from __future__ import annotations

import csv
from pathlib import Path

import typer

from casino_intel.cli.context import AppContext
from casino_intel.sheets.schema_definitions import TAB_NAMES

_SAFE_FILENAMES = {name: name.lower().replace(" ", "_") + ".csv" for name in TAB_NAMES}


def export(
    ctx: typer.Context,
    output: Path = typer.Option(..., "--output", help="Directory to write one CSV per tab into."),
) -> None:
    """Export every tab to `output/<tab>.csv`."""
    context: AppContext = ctx.obj

    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        typer.echo(f"Cannot write to {output}: {exc}")
        raise typer.Exit(code=11) from None

    ranges = [f"{name}!A1:ZZ" for name in TAB_NAMES]
    all_values = context.sheets_client.batch_get_values(ranges)

    written = []
    for name in TAB_NAMES:
        rows = all_values.get(f"{name}!A1:ZZ", [])
        file_path = output / _SAFE_FILENAMES[name]
        if not context.dry_run:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
        written.append(file_path.name)

    typer.echo(f"Exported {len(written)} tabs to {output}: {', '.join(written)}")
