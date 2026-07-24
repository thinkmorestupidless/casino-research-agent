"""The `casino-intel` Typer CLI app (contracts/cli-commands.md).

Global contract enforced here:
- every mutating command supports --dry-run
- every command accepts --ingestion-run-id (generated if omitted)
- credentials/config come only from environment variables, never CLI args
"""

from __future__ import annotations

import typer

from casino_intel.cli.context import AppContext
from casino_intel.logging import configure_logging

app = typer.Typer(
    name="casino-intel",
    help="Online Casino Competitive Intelligence Database — ingestion pipeline and CLI.",
    no_args_is_help=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview writes without committing them."
    ),
    ingestion_run_id: str = typer.Option(
        None, "--ingestion-run-id", help="Attach writes to a specific run (generated if omitted)."
    ),
) -> None:
    configure_logging()
    app_context = AppContext(dry_run=dry_run)
    if ingestion_run_id:
        app_context.ingestion_run_id = ingestion_run_id
    ctx.obj = app_context
    if ingestion_run_id is None:
        typer.echo(f"ingestion_run_id={app_context.ingestion_run_id}", err=True)


#: (module name, cli command name, function name in that module) — grown as
#: each phase's commands are implemented (tasks.md T026, T036, T058-T061,
#: T079, T086, T090, T092). `research-queue` is a sub-Typer group (list/run)
#: registered separately below since it has subcommands, not a single command.
_SIMPLE_COMMANDS: list[tuple[str, str, str]] = [
    ("initialise_workbook", "initialise-workbook", "initialise_workbook"),
    ("add_source", "add-source", "add_source"),
    ("fetch_source", "fetch-source", "fetch_source"),
    ("ingest_source", "ingest-source", "ingest_source"),
    ("import_file", "import-file", "import_file"),
    ("validate", "validate", "validate"),
    ("record_ux_audit", "record-ux-audit", "record_ux_audit"),
    ("record_brand_audit", "record-brand-audit", "record_brand_audit"),
    ("derive", "derive", "derive"),
    ("refresh_summary", "refresh-summary", "refresh_summary"),
    ("export", "export", "export"),
]


def _register_commands() -> None:
    """Wire each implemented command module's function onto `app`.

    A module not yet implemented in the current build phase is skipped
    (ModuleNotFoundError) rather than failing the whole CLI — this lets the
    app run correctly at every intermediate point during phased implementation.
    """
    import importlib

    for module_name, cli_name, func_name in _SIMPLE_COMMANDS:
        try:
            module = importlib.import_module(f"casino_intel.cli.commands.{module_name}")
        except ModuleNotFoundError:
            continue
        app.command(cli_name)(getattr(module, func_name))

    try:
        research_queue = importlib.import_module("casino_intel.cli.commands.research_queue")
    except ModuleNotFoundError:
        pass
    else:
        app.add_typer(research_queue.app, name="research-queue")


_register_commands()


if __name__ == "__main__":
    app()
