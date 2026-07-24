"""`casino-intel derive` (contracts/cli-commands.md).

Recalculates derived metrics (FR-035-FR-037) from currently `approved`
observations only. New `Derived Metrics` rows are appended for
newly-possible or changed calculations; existing rows are never edited in
place, and calculations are skipped (not fabricated) wherever inputs are
insufficiently comparable.
"""

from __future__ import annotations

import typer

from casino_intel.cli.context import AppContext
from casino_intel.derivation.engine import DerivationEngine


def derive(ctx: typer.Context) -> None:
    """Recalculate derived metrics from approved observations."""
    context: AppContext = ctx.obj

    try:
        engine = DerivationEngine(context.sheets_client, context.writer)
    except Exception as exc:  # formula-registry / engine construction failure
        typer.echo(f"Failed to load the derived-metric formula registry: {exc}", err=True)
        raise typer.Exit(code=9) from exc

    outcome = engine.run(actor=context.actor, ingestion_run_id=context.ingestion_run_id)

    for derived_metric_id in outcome.calculated:
        typer.echo(f"Calculated: {derived_metric_id}")
    for reason in outcome.skipped:
        typer.echo(f"Skipped: {reason}", err=True)
    typer.echo(
        f"Derivation complete: {len(outcome.calculated)} calculated, "
        f"{len(outcome.skipped)} skipped."
    )
