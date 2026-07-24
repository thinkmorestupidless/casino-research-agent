"""Unit tests for the brand traffic-provider CSV import (T063, spec FR-025):
never merges data across `provider` values, and writes both canonical
Observations and the human-friendly Traffic sheet row."""

from __future__ import annotations

from pathlib import Path

import pytest

from casino_intel.parsing.tabular_parser import parse_csv
from casino_intel.parsing.traffic_importer import import_traffic_rows
from casino_intel.services.observation_service import ObservationService
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation.data_quality import DataQualityWriter

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "traffic_export.csv"
SOURCE_ID = "source_traffic_1"


@pytest.fixture(autouse=True)
def _sheets(fake_service):
    fake_service.add_sheet("Traffic", SHEET_HEADERS["Traffic"])
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.add_sheet("Data Quality", SHEET_HEADERS["Data Quality"])


@pytest.fixture
def observation_service(sheets_writer) -> ObservationService:
    metric_registry = MetricRegistry("config/metrics.yaml")
    data_quality = DataQualityWriter(sheets_writer.client)
    return ObservationService(sheets_writer, data_quality, metric_registry)


def test_import_traffic_rows_creates_one_row_per_provider_scoped_brand(
    fake_service, sheets_writer, observation_service
):
    table = parse_csv(FIXTURE_PATH.read_bytes())
    created = import_traffic_rows(
        table,
        source_id=SOURCE_ID,
        writer=sheets_writer,
        observation_service=observation_service,
        actor="tester",
    )
    assert len(created) == 2  # one Traffic row per CSV row (two distinct brands)

    traffic_rows = fake_service.sheets["Traffic"][1:]
    assert len(traffic_rows) == 2
    header = SHEET_HEADERS["Traffic"]
    providers = {dict(zip(header, row, strict=False))["provider"] for row in traffic_rows}
    assert providers == {"similarweb"}  # both rows scoped to the one provider present

    # Canonical Observations were also written, comparability_group scoped
    # to the provider so nothing downstream can merge across providers.
    obs_header = SHEET_HEADERS["Observations"]
    obs_rows = [
        dict(zip(obs_header, row, strict=False)) for row in fake_service.sheets["Observations"][1:]
    ]
    assert obs_rows
    assert all("similarweb" in row["comparability_group"] for row in obs_rows)


def test_import_traffic_rows_is_idempotent_on_rerun(
    fake_service, sheets_writer, observation_service
):
    table = parse_csv(FIXTURE_PATH.read_bytes())
    import_traffic_rows(
        table,
        source_id=SOURCE_ID,
        writer=sheets_writer,
        observation_service=observation_service,
        actor="tester",
    )
    traffic_row_count = len(fake_service.sheets["Traffic"])
    obs_row_count = len(fake_service.sheets["Observations"])

    # Re-importing the identical export must not create duplicate Traffic
    # rows or duplicate canonical Observations.
    import_traffic_rows(
        table,
        source_id=SOURCE_ID,
        writer=sheets_writer,
        observation_service=observation_service,
        actor="tester",
    )
    assert len(fake_service.sheets["Traffic"]) == traffic_row_count
    assert len(fake_service.sheets["Observations"]) == obs_row_count
