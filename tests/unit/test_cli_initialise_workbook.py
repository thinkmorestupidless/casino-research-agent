import pytest
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.sheets.schema_definitions import TAB_NAMES

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_sheets_client(monkeypatch, sheets_client, fake_service):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", ":memory:")
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )
    return fake_service


def test_initialise_workbook_creates_all_tabs(fake_service):
    result = runner.invoke(app, ["initialise-workbook", "--owner", "Trevor"])
    assert result.exit_code == 0, result.output
    assert set(fake_service.sheets.keys()) == set(TAB_NAMES)
    assert fake_service.sheets["README"][1][5] == "Trevor"


def test_initialise_workbook_is_idempotent(fake_service):
    runner.invoke(app, ["initialise-workbook"])
    row_count = len(fake_service.sheets["Brands"])

    result = runner.invoke(app, ["initialise-workbook"])

    assert result.exit_code == 0
    assert len(fake_service.sheets["Brands"]) == row_count


def test_initialise_workbook_dry_run_does_not_write(fake_service):
    result = runner.invoke(app, ["--dry-run", "initialise-workbook"])
    assert result.exit_code == 0
    # Tabs are created structurally (schema bootstrap always creates tabs so
    # subsequent reads work), but Config/README content writes are skipped.
    config_rows = fake_service.sheets.get("Config", [[]])
    assert len(config_rows) <= 1  # header only, no seeded vocab rows written
