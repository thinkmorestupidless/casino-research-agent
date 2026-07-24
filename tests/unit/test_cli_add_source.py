import pytest
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

runner = CliRunner()


@pytest.fixture(autouse=True)
def _setup(monkeypatch, sheets_client, fake_service):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", ":memory:")
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )
    fake_service.add_sheet("Sources", SHEET_HEADERS["Sources"])
    fake_service.add_sheet("Change Log", SHEET_HEADERS["Change Log"])
    return fake_service


def test_add_source_registers_new_source(fake_service):
    result = runner.invoke(
        app,
        ["add-source", "--url", "https://example.gov/stats", "--type", "regulator_statistics"],
    )
    assert result.exit_code == 0, result.output
    assert len(fake_service.sheets["Sources"]) == 2


def test_add_source_rejects_unknown_type(fake_service):
    result = runner.invoke(
        app, ["add-source", "--url", "https://example.com/x", "--type", "not_a_real_type"]
    )
    assert result.exit_code == 1
    assert len(fake_service.sheets["Sources"]) == 1  # nothing written


def test_add_source_rejects_duplicate_url(fake_service):
    runner.invoke(
        app, ["add-source", "--url", "https://example.gov/stats", "--type", "regulator_statistics"]
    )
    result = runner.invoke(
        app, ["add-source", "--url", "https://example.gov/stats", "--type", "regulator_statistics"]
    )
    assert result.exit_code == 4
    assert len(fake_service.sheets["Sources"]) == 2  # still only the first registration
