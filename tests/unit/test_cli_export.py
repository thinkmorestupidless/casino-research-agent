import csv

import pytest
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.sheets.schema import ensure_tabs_and_headers

runner = CliRunner()


@pytest.fixture(autouse=True)
def _setup(monkeypatch, sheets_client, fake_service):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", ":memory:")
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )
    ensure_tabs_and_headers(sheets_client)
    fake_service.sheets["Brands"].append(["brand_1"] + [""] * 15 + ["Example Casino"] + [""] * 10)
    return fake_service


def test_export_writes_one_csv_per_tab(tmp_path):
    result = runner.invoke(app, ["export", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output

    brands_csv = tmp_path / "brands.csv"
    assert brands_csv.exists()
    with open(brands_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0][0] == "record_id"  # header row preserved
    assert rows[1][0] == "brand_1"  # data row preserved, no data loss

    observations_csv = tmp_path / "observations.csv"
    assert observations_csv.exists()


def test_export_dry_run_does_not_write_files(tmp_path):
    result = runner.invoke(app, ["--dry-run", "export", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert not (tmp_path / "brands.csv").exists()


def test_export_reports_permission_failure(monkeypatch, tmp_path):
    unwritable = tmp_path / "sub"

    def _fail_mkdir(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("pathlib.Path.mkdir", _fail_mkdir)
    result = runner.invoke(app, ["export", "--output", str(unwritable)])
    assert result.exit_code == 11
