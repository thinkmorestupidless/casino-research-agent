"""Unit tests for the Google Trends CSV import (T064, spec FR-026): every
row's `interest_index` carries its `comparison_set_id` so nothing
downstream compares across differing comparison sets."""

from __future__ import annotations

from pathlib import Path

import pytest

from casino_intel.parsing.tabular_parser import parse_csv
from casino_intel.parsing.trends_importer import import_trends_rows
from casino_intel.services.observation_service import ObservationService
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation.data_quality import DataQualityWriter

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "trends_export.csv"
SOURCE_ID = "source_trends_1"
DOCUMENT_ID = "document_trends_1"


@pytest.fixture(autouse=True)
def _sheets(fake_service):
    fake_service.add_sheet("Search Interest", SHEET_HEADERS["Search Interest"])
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.add_sheet("Data Quality", SHEET_HEADERS["Data Quality"])


@pytest.fixture
def observation_service(sheets_writer) -> ObservationService:
    metric_registry = MetricRegistry("config/metrics.yaml")
    data_quality = DataQualityWriter(sheets_writer.client)
    return ObservationService(sheets_writer, data_quality, metric_registry)


def test_import_trends_rows_tags_every_row_with_its_comparison_set(
    fake_service, sheets_writer, observation_service
):
    table = parse_csv(FIXTURE_PATH.read_bytes())
    created = import_trends_rows(
        table,
        source_id=SOURCE_ID,
        document_id=DOCUMENT_ID,
        writer=sheets_writer,
        observation_service=observation_service,
        actor="tester",
    )
    assert len(created) == 2

    header = SHEET_HEADERS["Search Interest"]
    rows = [
        dict(zip(header, row, strict=False)) for row in fake_service.sheets["Search Interest"][1:]
    ]
    assert all(row["comparison_set_id"] == "cmp_gb_casino_2026_06" for row in rows)

    obs_header = SHEET_HEADERS["Observations"]
    obs_rows = [
        dict(zip(obs_header, row, strict=False)) for row in fake_service.sheets["Observations"][1:]
    ]
    assert all(row["comparability_group"] == "cmp_gb_casino_2026_06" for row in obs_rows)
    assert all(row["metric_id"] == "branded_search_interest_index" for row in obs_rows)
