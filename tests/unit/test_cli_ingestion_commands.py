"""Unit tests for the `fetch-source`, `ingest-source`, `import-file`, and
`validate` CLI commands (T058-T061), driven entirely through the Typer
`CliRunner` against fake Sheets/Drive backends — no live network access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.drive.client import DriveClient
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

runner = CliRunner()

UKGC_FIXTURE = Path(__file__).parent.parent / "fixtures" / "ukgc_business_data.xlsx"


class _FakeDriveService:
    def __init__(self) -> None:
        self._next_id = 1
        self._pending: tuple[Any, ...] = ()

    def files(self):
        return self

    def list(self, q, fields, **kwargs):
        self._pending = ("list",)
        return self

    def create(self, body, fields="id", media_body=None, **kwargs):
        self._pending = ("create",)
        return self

    def execute(self):
        if self._pending[0] == "list":
            return {"files": []}
        file_id = f"fake-file-{self._next_id}"
        self._next_id += 1
        return {"id": file_id}


@pytest.fixture(autouse=True)
def _setup(monkeypatch, sheets_client, fake_service, tmp_path):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    # A real (temp-file) cache path, not ":memory:" — each `runner.invoke()`
    # call builds a brand-new `AppContext`/`FingerprintStore`, and a
    # ":memory:" SQLite database does not survive across those separate
    # connections, which would make idempotency untestable across two
    # invocations in the same test.
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", str(tmp_path / "fingerprints.sqlite3"))
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )
    monkeypatch.setattr(
        "casino_intel.cli.context.DriveClient",
        lambda: DriveClient(service=_FakeDriveService(), root_folder_id="fake-root"),
    )
    fake_service.add_sheet("Sources", SHEET_HEADERS["Sources"])
    fake_service.add_sheet("Documents", SHEET_HEADERS["Documents"])
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.add_sheet("Data Quality", SHEET_HEADERS["Data Quality"])
    fake_service.add_sheet("Change Log", SHEET_HEADERS["Change Log"])
    fake_service.add_sheet("Research Queue", SHEET_HEADERS["Research Queue"])
    return fake_service


def _register_source(fake_service, *, paywalled=False, authentication_required=False) -> str:
    result = runner.invoke(
        app,
        ["add-source", "--url", "https://example.gov/statistics", "--type", "regulator_statistics"],
    )
    assert result.exit_code == 0, result.output
    header = SHEET_HEADERS["Sources"]
    row = fake_service.sheets["Sources"][1]
    record = dict(zip(header, row, strict=False))
    source_id = record["record_id"]
    if paywalled or authentication_required:
        idx_paywalled = header.index("paywalled")
        idx_auth = header.index("authentication_required")
        row[idx_paywalled] = paywalled
        row[idx_auth] = authentication_required
    return source_id


def test_import_file_ingests_ukgc_fixture_and_creates_unreviewed_observations(fake_service):
    source_id = _register_source(fake_service)

    result = runner.invoke(
        app,
        [
            "import-file",
            "--path",
            str(UKGC_FIXTURE),
            "--source-id",
            source_id,
            "--importer",
            "ukgc",
            "--subject-id",
            "market_gb",
            "--period-start",
            "2025-01-01",
            "--period-end",
            "2025-12-31",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "4 new" in result.output

    obs_header = SHEET_HEADERS["Observations"]
    rows = [
        dict(zip(obs_header, row, strict=False)) for row in fake_service.sheets["Observations"][1:]
    ]
    assert len(rows) == 4
    assert all(row["review_status"] == "unreviewed" for row in rows)
    assert len(fake_service.sheets["Documents"]) == 2  # header + 1 new Document row


def test_import_file_is_idempotent_on_unchanged_rerun(fake_service):
    source_id = _register_source(fake_service)
    common_args = [
        "import-file",
        "--path",
        str(UKGC_FIXTURE),
        "--source-id",
        source_id,
        "--importer",
        "ukgc",
        "--subject-id",
        "market_gb",
        "--period-start",
        "2025-01-01",
        "--period-end",
        "2025-12-31",
    ]
    first = runner.invoke(app, common_args)
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, common_args)
    assert second.exit_code == 0, second.output
    assert "unchanged=True" in second.output

    obs_rows = fake_service.sheets["Observations"][1:]
    assert len(obs_rows) == 4  # no duplicates, no re-parse
    assert len(fake_service.sheets["Documents"]) == 2  # no new Document row


def test_import_file_requires_existing_source_id(fake_service):
    result = runner.invoke(
        app, ["import-file", "--path", str(UKGC_FIXTURE), "--source-id", "source_does_not_exist"]
    )
    assert result.exit_code == 1


def test_import_file_requires_source_id_flag(fake_service):
    result = runner.invoke(app, ["import-file", "--path", str(UKGC_FIXTURE)])
    assert result.exit_code == 1


def test_ingest_source_refuses_paywalled_source_and_creates_research_task(fake_service):
    source_id = _register_source(fake_service, paywalled=True)

    result = runner.invoke(app, ["ingest-source", "--source-id", source_id])
    assert result.exit_code == 5, result.output
    assert len(fake_service.sheets["Research Queue"]) == 2  # header + 1 auto-created task


def test_fetch_source_refuses_authentication_required_source(fake_service):
    source_id = _register_source(fake_service, authentication_required=True)

    result = runner.invoke(app, ["fetch-source", "--source-id", source_id])
    assert result.exit_code == 5, result.output
    assert len(fake_service.sheets["Documents"]) == 1  # header only — nothing fetched


def test_validate_reports_zero_issues_when_observations_are_clean(fake_service):
    header = SHEET_HEADERS["Observations"]
    row = ["" for _ in header]
    row[header.index("record_id")] = "obs_clean_1"
    row[header.index("status")] = "active"
    row[header.index("source_id")] = "source_1"
    row[header.index("metric_id")] = "estimated_monthly_visits"
    row[header.index("raw_value")] = "1,000,000"
    fake_service.sheets["Observations"].append(row)

    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0, result.output
    assert "0 data-quality issue" in result.output


def test_validate_flags_missing_source_without_mutating_observations(fake_service):
    header = SHEET_HEADERS["Observations"]
    row = ["" for _ in header]
    row[header.index("record_id")] = "obs_bad_1"
    row[header.index("status")] = "active"
    row[header.index("source_id")] = ""  # missing source
    row[header.index("metric_id")] = "estimated_monthly_visits"
    row[header.index("raw_value")] = "1,000,000"
    fake_service.sheets["Observations"].append(row)
    original_row = list(fake_service.sheets["Observations"][1])

    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0, result.output
    assert "1 data-quality issue" in result.output
    assert fake_service.sheets["Observations"][1] == original_row  # never mutated
    assert len(fake_service.sheets["Data Quality"]) == 2  # header + 1 issue
