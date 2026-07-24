"""`casino-intel initialise-workbook` (contracts/cli-commands.md)."""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from casino_intel.cli.context import AppContext
from casino_intel.sheets.config_loader import ConfigLoader
from casino_intel.sheets.schema import (
    apply_confidence_conditional_formatting,
    ensure_tabs_and_headers,
)
from casino_intel.sheets.schema_version import CURRENT_SCHEMA_VERSION

DEFAULT_TARGET_MARKET = "Great Britain"


def _run(context: AppContext, owner: str, repository_url: str, runbook_url: str) -> list[str]:
    client = context.sheets_client
    created = ensure_tabs_and_headers(client, dry_run=context.dry_run)
    if not context.dry_run:
        apply_confidence_conditional_formatting(client)

    loader = ConfigLoader(client, dry_run=context.dry_run)
    loader.seed_vocabularies("config/vocabularies.yaml")
    loader.seed_metric_ids("config/metrics.yaml")

    if not context.dry_run:
        readme_row = [
            "0.1.0",
            CURRENT_SCHEMA_VERSION,
            datetime.now(UTC).isoformat(),
            "",
            DEFAULT_TARGET_MARKET,
            owner,
            repository_url,
            runbook_url,
        ]
        existing_readme = client.batch_get_values(["README!A2"]).get("README!A2", [])
        if not existing_readme or not existing_readme[0]:
            client.append_rows("README", [readme_row])

    return created


def initialise_workbook(
    ctx: typer.Context,
    owner: str = typer.Option("", help="Workbook owner to record in README."),
    repository_url: str = typer.Option("", help="Link to the code repository."),
    runbook_url: str = typer.Option("", help="Link to docs/runbook.md or its hosted equivalent."),
) -> None:
    """Create/verify the workbook: all 23 tabs, headers, validation, README."""
    context: AppContext = ctx.obj
    created = _run(context, owner, repository_url, runbook_url)
    if created:
        typer.echo(f"Created tabs: {', '.join(created)}")
    else:
        typer.echo("All tabs already present — verified headers and vocabularies only.")
