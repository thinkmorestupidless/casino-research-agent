"""User Story 2 independent test (quickstart.md Steps 3-6, T072):

1. Idempotent re-ingestion: ingesting the same unchanged UKGC XLSX fixture
   twice creates zero duplicate Observation/Document rows the second time
   (FR-018).
2. Versioned re-ingestion: a changed fixture (new content hash) creates a
   new Document row — the prior Document row is retained unmodified — and
   any resulting new observations are held at review_status=unreviewed
   pending human review (FR-019).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from casino_intel.drive.client import DriveClient
from casino_intel.fetching.archiver import DocumentArchiver
from casino_intel.fetching.fetcher import Fetcher
from casino_intel.parsing.ukgc_importer import extract_ukgc_xlsx
from casino_intel.services.ingestion_run import IngestionRun
from casino_intel.services.observation_service import ObservationService
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation.data_quality import DataQualityWriter

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "ukgc_business_data.xlsx"
SOURCE_ID = "source_ukgc_test"
SUBJECT_ID = "market_gb"


class FakeDriveService:
    """Minimal in-memory stand-in for the Drive API v3 resource used by
    `DriveClient` — no live network access, mirroring
    `tests/conftest.py`'s `FakeSheetsService` pattern for Sheets."""

    def __init__(self) -> None:
        self._next_id = 1
        self.uploaded_files: list[dict[str, Any]] = []
        self._pending: tuple[Any, ...] = ()

    def files(self) -> FakeDriveService:
        return self

    def list(self, q: str, fields: str, **kwargs: object) -> FakeDriveService:
        self._pending = ("list",)
        return self

    def create(
        self,
        body: dict,
        fields: str = "id",
        media_body: object | None = None,
        **kwargs: object,
    ) -> FakeDriveService:
        self._pending = ("create", body, media_body)
        return self

    def execute(self) -> dict:
        if self._pending[0] == "list":
            return {"files": []}  # force DriveClient to always create fresh folders/files
        _, body, media_body = self._pending
        new_id = f"fake-drive-file-{self._next_id}"
        self._next_id += 1
        if media_body is not None:
            self.uploaded_files.append({"id": new_id, "name": body.get("name")})
        return {"id": new_id}


@pytest.fixture(autouse=True)
def _sheets(fake_service):
    fake_service.add_sheet("Sources", SHEET_HEADERS["Sources"])
    fake_service.add_sheet("Documents", SHEET_HEADERS["Documents"])
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.add_sheet("Data Quality", SHEET_HEADERS["Data Quality"])
    return fake_service


@pytest.fixture
def drive_client() -> DriveClient:
    return DriveClient(service=FakeDriveService(), root_folder_id="fake-root")


@pytest.fixture
def ingestion_run(sheets_writer, fingerprint_store, drive_client) -> IngestionRun:
    metric_registry = MetricRegistry("config/metrics.yaml")
    data_quality = DataQualityWriter(sheets_writer.client)
    observation_service = ObservationService(sheets_writer, data_quality, metric_registry)
    archiver = DocumentArchiver(drive_client, fingerprint_store, sheets_writer)
    return IngestionRun(
        fetcher=Fetcher(),  # unused: content is supplied directly, never fetched live
        archiver=archiver,
        observation_service=observation_service,
        data_quality=data_quality,
        metric_registry=metric_registry,
    )


def _extract_fn(content: bytes, content_type: str):
    return extract_ukgc_xlsx(
        content,
        source_id=SOURCE_ID,
        subject_id=SUBJECT_ID,
        period_start="2025-01-01",
        period_end="2025-12-31",
    )


def _fake_source():
    from casino_intel.models.source import Source

    return Source(
        record_id=SOURCE_ID,
        created_at="2026-07-01T00:00:00Z",
        created_by="tester",
        updated_at="2026-07-01T00:00:00Z",
        source_type="regulator_statistics",
        url="https://www.gamblingcommission.gov.uk/statistics-and-research/example",
    )


def test_idempotent_reingestion_creates_zero_duplicates_on_unchanged_rerun(
    fake_service, ingestion_run
):
    content = FIXTURE_PATH.read_bytes()
    source = _fake_source()

    first = ingestion_run.run(
        source=source,
        extract_fn=_extract_fn,
        actor="tester",
        ingestion_run_id="run_test_1",
        content=content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="ukgc_business_data.xlsx",
    )
    assert not first.skipped_no_content_change
    assert first.new_observations == 4  # market_ggy, active_accounts, bets_or_spins, avg_session
    assert first.duplicate_observations == 0
    assert len(fake_service.sheets["Documents"]) == 2  # header + 1 document row
    assert len(fake_service.sheets["Observations"]) == 5  # header + 4 observations

    second = ingestion_run.run(
        source=source,
        extract_fn=_extract_fn,
        actor="tester",
        ingestion_run_id="run_test_2",
        content=content,  # byte-identical re-ingestion
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="ukgc_business_data.xlsx",
    )

    # Unchanged content short-circuits before parsing/extraction even runs —
    # the strongest form of "zero duplicates" (FR-018).
    assert second.skipped_no_content_change
    assert second.new_observations == 0
    assert second.duplicate_observations == 0
    assert second.document_id == first.document_id
    assert len(fake_service.sheets["Documents"]) == 2  # no new Document row
    assert len(fake_service.sheets["Observations"]) == 5  # no new/duplicate Observation rows


def test_versioned_reingestion_creates_new_document_and_holds_for_review(
    fake_service, ingestion_run
):
    original_content = FIXTURE_PATH.read_bytes()
    source = _fake_source()

    first = ingestion_run.run(
        source=source,
        extract_fn=_extract_fn,
        actor="tester",
        ingestion_run_id="run_test_1",
        content=original_content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="ukgc_business_data.xlsx",
    )
    assert first.new_observations == 4

    # Simulate the regulator publishing a revised statistics export: one
    # value changes, everything else stays the same.
    table = pd.read_excel(io.BytesIO(original_content), engine="openpyxl")
    table.loc[table["Metric"] == "Gross gambling yield", "Value"] = 1_300_000_000
    buffer = io.BytesIO()
    table.to_excel(buffer, index=False, sheet_name="Statistics")
    changed_content = buffer.getvalue()
    assert changed_content != original_content

    second = ingestion_run.run(
        source=source,
        extract_fn=_extract_fn,
        actor="tester",
        ingestion_run_id="run_test_2",
        content=changed_content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="ukgc_business_data.xlsx",
    )

    # A changed content hash always creates a brand-new Document row — the
    # prior Document row is retained unmodified (FR-019), never overwritten.
    assert not second.skipped_no_content_change
    assert second.document_id != first.document_id
    document_rows = fake_service.sheets["Documents"][1:]
    assert len(document_rows) == 2
    doc_header = SHEET_HEADERS["Documents"]
    document_ids = {dict(zip(doc_header, row, strict=False))["record_id"] for row in document_rows}
    assert document_ids == {first.document_id, second.document_id}

    # The three unchanged metrics dedupe as duplicates (identical
    # fingerprint); only the changed metric produces a genuinely new,
    # unreviewed observation — never silently overwriting the prior value.
    assert second.new_observations == 1
    assert second.duplicate_observations == 3

    observation_rows = fake_service.sheets["Observations"][1:]
    assert len(observation_rows) == 5  # 4 from the first run + 1 changed value
    obs_header = SHEET_HEADERS["Observations"]
    for row in observation_rows:
        record = dict(zip(obs_header, row, strict=False))
        assert record["review_status"] == "unreviewed"  # held for review, never auto-approved

    raw_values = {dict(zip(obs_header, row, strict=False))["raw_value"] for row in observation_rows}
    assert "1234000000.0" in raw_values  # original value retained, not overwritten
    assert "1300000000.0" in raw_values  # new value appended alongside it
