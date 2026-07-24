"""User Story 1 independent test (quickstart.md Steps 1-2): register one
operator, one brand, one source, and two dated observations for the same
brand/metric — confirm both persist, traceably, without overwrite."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.services.observation_service import ObservationInput, ObservationService
from casino_intel.services.registry_service import RegistryService
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation.data_quality import DataQualityWriter

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_sheets_client(monkeypatch, sheets_client):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", ":memory:")
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )


def test_full_user_story_1_flow(fake_service, sheets_writer):
    # Step 1: stand up the workbook (all tabs, headers, Config vocab).
    init_result = runner.invoke(app, ["initialise-workbook", "--owner", "Trevor"])
    assert init_result.exit_code == 0, init_result.output

    # Step 2a: register a source via the CLI.
    add_source_result = runner.invoke(
        app,
        [
            "add-source",
            "--url",
            "https://www.gamblingcommission.gov.uk/statistics-and-research/publication/example",
            "--type",
            "regulator_statistics",
        ],
    )
    assert add_source_result.exit_code == 0, add_source_result.output
    header = SHEET_HEADERS["Sources"]
    source_row = fake_service.sheets["Sources"][1]
    source_id = dict(zip(header, source_row, strict=False))["record_id"]

    # Step 2b: register an operator and a brand belonging to it.
    registry = RegistryService(sheets_writer)
    operator_result = registry.register_operator(
        {"operator_name": "Example Group plc", "ownership_type": "public"}, actor="tester"
    )
    brand_result = registry.register_brand(
        {
            "brand_name": "Example Casino",
            "operator_id": operator_result.record_id,
            "primary_domain": "example-casino.example",
            "brand_type": "casino_only",
            "sampling_rationale": "Integration-test brand.",
        },
        actor="tester",
    )

    # Step 2c: record two dated observations for the same brand/metric.
    metric_registry = MetricRegistry("config/metrics.yaml")
    data_quality = DataQualityWriter(sheets_writer.client)
    observation_service = ObservationService(sheets_writer, data_quality, metric_registry)

    first = observation_service.record_observation(
        ObservationInput(
            subject_type="brand",
            subject_id=brand_result.record_id,
            metric_id="estimated_monthly_visits",
            raw_value="900,000",
            source_id=source_id,
            evidence_type="third_party_estimate",
            confidence="medium",
            period_start="2026-05-01",
            period_end="2026-05-31",
            geography="GB",
        ),
        actor="tester",
    )
    second = observation_service.record_observation(
        ObservationInput(
            subject_type="brand",
            subject_id=brand_result.record_id,
            metric_id="estimated_monthly_visits",
            raw_value="1,050,000",
            source_id=source_id,
            evidence_type="third_party_estimate",
            confidence="medium",
            period_start="2026-06-01",
            period_end="2026-06-30",
            geography="GB",
        ),
        actor="tester",
    )

    # Both observations persisted — no overwrite.
    assert first.written and second.written
    assert first.record_id != second.record_id
    observation_rows = fake_service.sheets["Observations"][1:]
    assert len(observation_rows) == 2

    # Every observation traces back to the registered source and brand,
    # with evidence type/confidence visible (spec SC-001/SC-003).
    obs_header = SHEET_HEADERS["Observations"]
    for row in observation_rows:
        record = dict(zip(obs_header, row, strict=False))
        assert record["source_id"] == source_id
        assert record["subject_id"] == brand_result.record_id
        assert record["evidence_type"] == "third_party_estimate"
        assert record["confidence"] == "medium"

    # Change Log recorded a create entry for every write (source, operator,
    # brand, and both observations).
    change_log_rows = fake_service.sheets["Change Log"][1:]
    assert len(change_log_rows) >= 5
