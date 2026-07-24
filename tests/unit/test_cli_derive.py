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
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.add_sheet("Derived Metrics", SHEET_HEADERS["Derived Metrics"])
    fake_service.add_sheet("Change Log", SHEET_HEADERS["Change Log"])
    return fake_service


def _obs_row(record_id: str, **overrides) -> list[str]:
    header = SHEET_HEADERS["Observations"]
    defaults = {col: "" for col in header}
    defaults.update(
        record_id=record_id,
        created_at="2026-07-01T00:00:00+00:00",
        created_by="tester",
        updated_at="2026-07-01T00:00:00+00:00",
        status="active",
        evidence_type="reported_primary",
        confidence="high",
        review_status="approved",
        subject_type="brand",
        subject_id="brand_1",
    )
    defaults.update(overrides)
    return [str(defaults[col]) for col in header]


def test_derive_writes_a_new_row_for_compatible_inputs(fake_service):
    fake_service.sheets["Observations"].append(
        _obs_row(
            "obs_rev",
            metric_id="revenue",
            normalised_numeric_value="1000000",
            period_start="2026-01-01",
            period_end="2026-03-31",
        )
    )
    fake_service.sheets["Observations"].append(
        _obs_row(
            "obs_cust",
            metric_id="active_customers",
            normalised_numeric_value="10000",
            period_start="2026-01-01",
            period_end="2026-03-31",
        )
    )

    result = runner.invoke(app, ["derive"])

    assert result.exit_code == 0, result.output
    assert len(fake_service.sheets["Derived Metrics"]) == 2  # header + 1 new row


def test_derive_skips_incompatible_inputs_without_writing(fake_service):
    fake_service.sheets["Observations"].append(
        _obs_row(
            "obs_rev",
            metric_id="revenue",
            normalised_numeric_value="1000000",
            period_start="2026-01-01",
            period_end="2026-03-31",
        )
    )
    fake_service.sheets["Observations"].append(
        _obs_row(
            "obs_cust",
            metric_id="active_customers",
            normalised_numeric_value="10000",
            period_start="2026-04-01",
            period_end="2026-06-30",
        )
    )

    result = runner.invoke(app, ["derive"])

    assert result.exit_code == 0, result.output
    assert len(fake_service.sheets["Derived Metrics"]) == 1  # header only — nothing fabricated
