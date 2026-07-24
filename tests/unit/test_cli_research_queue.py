import pytest
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.services.research_task_service import ResearchTaskService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

runner = CliRunner()


@pytest.fixture(autouse=True)
def _setup(monkeypatch, sheets_client, fake_service):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", ":memory:")
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )
    fake_service.add_sheet("Research Queue", SHEET_HEADERS["Research Queue"])
    fake_service.add_sheet("Change Log", SHEET_HEADERS["Change Log"])
    return fake_service


def test_research_queue_list_shows_open_tasks(fake_service, sheets_client):
    service = ResearchTaskService(sheets_client)
    service.create_task(
        subject_type="source",
        subject_id="source_1",
        task_type="perform_ux_audit",
        priority=1,
    )
    result = runner.invoke(app, ["research-queue", "list"])
    assert result.exit_code == 0, result.output
    assert "perform_ux_audit" in result.output


def test_research_queue_list_empty_reports_no_matches(fake_service):
    result = runner.invoke(app, ["research-queue", "list"])
    assert result.exit_code == 0
    assert "No matching tasks" in result.output


def test_research_queue_run_defers_audit_tasks(fake_service, sheets_client):
    service = ResearchTaskService(sheets_client)
    service.create_task(
        subject_type="brand",
        subject_id="brand_1",
        task_type="perform_ux_audit",
        priority=1,
    )
    result = runner.invoke(app, ["research-queue", "run", "--limit", "5"])
    assert result.exit_code == 0, result.output
    assert "deferred - manual" in result.output
    # Deferred tasks are left open, not marked done/blocked.
    header = SHEET_HEADERS["Research Queue"]
    status_col = header.index("status")
    assert fake_service.sheets["Research Queue"][1][status_col] == "open"


def test_research_queue_run_marks_unroutable_task_blocked(fake_service, sheets_client):
    service = ResearchTaskService(sheets_client)
    service.create_task(
        subject_type="market",  # not "source" -> cannot dispatch to fetch/ingest
        subject_id="market_gb",
        task_type="capture_traffic",
        priority=1,
    )
    result = runner.invoke(app, ["research-queue", "run"])
    assert result.exit_code == 0  # deferred, not a failure
    assert "deferred - manual" in result.output
