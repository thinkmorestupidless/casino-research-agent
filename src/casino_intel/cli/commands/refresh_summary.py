"""`casino-intel refresh-summary` (contracts/cli-commands.md)."""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from casino_intel.cli.context import AppContext
from casino_intel.reporting.summary_generator import NoBrandsRegisteredError, refresh_summary_sheet


def refresh_summary(ctx: typer.Context) -> None:
    """Regenerate the `Summary` sheet from current active/approved data."""
    context: AppContext = ctx.obj

    try:
        completions = refresh_summary_sheet(
            context.sheets_client, now=datetime.now(UTC), dry_run=context.dry_run
        )
    except NoBrandsRegisteredError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=10) from None

    prefix = "[dry-run] Would refresh" if context.dry_run else "Refreshed"
    typer.echo(f"{prefix} Summary for {len(completions)} brand(s).")
