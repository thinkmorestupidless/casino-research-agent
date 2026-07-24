"""Unit tests for app-store presence capture (T065): download_estimate is
kept distinct from any active-user metric, and every capture field lands
on its own canonical Observation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from casino_intel.parsing.app_store_importer import import_app_store_capture
from casino_intel.services.observation_service import ObservationService
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation.data_quality import DataQualityWriter

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "app_store_capture.json"
SOURCE_ID = "source_app_store_1"


@pytest.fixture(autouse=True)
def _sheets(fake_service):
    fake_service.add_sheet("App Presence", SHEET_HEADERS["App Presence"])
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.add_sheet("Data Quality", SHEET_HEADERS["Data Quality"])


@pytest.fixture
def observation_service(sheets_writer) -> ObservationService:
    metric_registry = MetricRegistry("config/metrics.yaml")
    data_quality = DataQualityWriter(sheets_writer.client)
    return ObservationService(sheets_writer, data_quality, metric_registry)


def test_import_app_store_capture_creates_one_app_presence_row_per_capture(
    fake_service, sheets_writer, observation_service
):
    captures = json.loads(FIXTURE_PATH.read_text())
    created = import_app_store_capture(
        captures,
        source_id=SOURCE_ID,
        writer=sheets_writer,
        observation_service=observation_service,
        actor="tester",
    )
    assert len(created) == 2

    header = SHEET_HEADERS["App Presence"]
    rows = [dict(zip(header, row, strict=False)) for row in fake_service.sheets["App Presence"][1:]]
    assert {row["platform"] for row in rows} == {"ios", "android"}

    obs_header = SHEET_HEADERS["Observations"]
    obs_rows = [
        dict(zip(obs_header, row, strict=False)) for row in fake_service.sheets["Observations"][1:]
    ]
    metric_ids = {row["metric_id"] for row in obs_rows}
    assert "app_download_estimate" in metric_ids
    assert "app_rating" in metric_ids

    # download_estimate is never conflated with an active-customer metric.
    download_rows = [row for row in obs_rows if row["metric_id"] == "app_download_estimate"]
    assert all(row["subject_type"] == "app" for row in download_rows)
    assert "active_customers" not in metric_ids
