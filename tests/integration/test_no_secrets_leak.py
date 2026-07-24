"""Secrets-hygiene check (spec FR-050, SC-012): credentials must never be
accepted as CLI arguments, and must never appear in any sheet cell or CSV
export, even incidentally."""

from __future__ import annotations

import csv

import pytest
import typer.main
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.sheets.schema import ensure_tabs_and_headers

runner = CliRunner()

FAKE_CREDENTIAL_PATH = "/tmp/fake-service-account-super-secret-key.json"
FAKE_CREDENTIAL_MARKER = "super-secret-key"

_FORBIDDEN_OPTION_SUBSTRINGS = ("credential", "secret", "password", "api-key", "apikey", "token")


@pytest.fixture(autouse=True)
def _setup(monkeypatch, sheets_client, fake_service):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", ":memory:")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", FAKE_CREDENTIAL_PATH)
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )
    return fake_service


def _iter_click_commands(click_command, prefix=""):
    """Recursively yield (full_name, click.Command) for every command,
    including subcommands of a click.Group like `research-queue`."""
    import click

    yield prefix or click_command.name, click_command
    if isinstance(click_command, click.Group):
        for name, sub in click_command.commands.items():
            yield from _iter_click_commands(sub, f"{prefix} {name}".strip())


def test_no_cli_command_accepts_a_credential_like_argument():
    """contracts/cli-commands.md: credentials are read only from environment
    variables, never accepted as CLI arguments."""
    click_app = typer.main.get_command(app)
    violations = []
    for command_name, command in _iter_click_commands(click_app):
        for param in command.params:
            for opt in getattr(param, "opts", []):
                lowered = opt.lower()
                if any(bad in lowered for bad in _FORBIDDEN_OPTION_SUBSTRINGS):
                    violations.append(f"{command_name} {opt}")
    assert not violations, f"CLI options that could accept a secret: {violations}"


def test_no_secret_appears_in_workbook_after_a_full_workflow(fake_service, sheets_client):
    ensure_tabs_and_headers(sheets_client)

    runner.invoke(app, ["initialise-workbook", "--owner", "Trevor"])
    runner.invoke(
        app,
        ["add-source", "--url", "https://example.gov/stats", "--type", "regulator_statistics"],
    )

    for sheet_name, rows in fake_service.sheets.items():
        for row in rows:
            for cell in row:
                assert FAKE_CREDENTIAL_MARKER not in str(
                    cell
                ), f"Secret leaked into {sheet_name!r}: {cell!r}"


def test_no_secret_appears_in_csv_export(tmp_path, fake_service, sheets_client):
    ensure_tabs_and_headers(sheets_client)
    runner.invoke(app, ["initialise-workbook"])
    runner.invoke(
        app,
        ["add-source", "--url", "https://example.gov/stats2", "--type", "regulator_statistics"],
    )

    result = runner.invoke(app, ["export", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output

    for csv_file in tmp_path.glob("*.csv"):
        with open(csv_file, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                for cell in row:
                    assert (
                        FAKE_CREDENTIAL_MARKER not in cell
                    ), f"Secret leaked into export {csv_file.name}: {cell!r}"
