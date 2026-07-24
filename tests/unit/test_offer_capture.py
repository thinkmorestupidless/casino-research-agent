"""Unit tests for offer capture from promotion pages (T066, spec FR-028):
must capture full terms, never headline-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from casino_intel.cache.fingerprint_store import FingerprintStore
from casino_intel.drive.client import DriveClient
from casino_intel.fetching.archiver import DocumentArchiver
from casino_intel.parsing.offer_capture import capture_offer
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation.data_quality import DataQualityWriter

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "promotion_terms.html"
SOURCE_ID = "source_offer_1"

_HEADLINE_ONLY_HTML = b"""
<html><body>
  <div class="offer-headline">Get a 100% Welcome Bonus up to &pound;200</div>
</body></html>
"""


class _FakeDriveService:
    def __init__(self) -> None:
        self._next_id = 1
        self._pending: tuple[Any, ...] = ()

    def files(self):
        return self

    def list(self, q, fields):
        self._pending = ("list",)
        return self

    def create(self, body, fields="id", media_body=None):
        self._pending = ("create",)
        return self

    def execute(self):
        if self._pending[0] == "list":
            return {"files": []}
        file_id = f"fake-file-{self._next_id}"
        self._next_id += 1
        return {"id": file_id}


@pytest.fixture(autouse=True)
def _sheets(fake_service):
    fake_service.add_sheet("Offers", SHEET_HEADERS["Offers"])
    fake_service.add_sheet("Documents", SHEET_HEADERS["Documents"])
    fake_service.add_sheet("Data Quality", SHEET_HEADERS["Data Quality"])


@pytest.fixture
def archiver(sheets_writer) -> DocumentArchiver:
    drive_client = DriveClient(service=_FakeDriveService(), root_folder_id="fake-root")
    return DocumentArchiver(drive_client, FingerprintStore(path=":memory:"), sheets_writer)


@pytest.fixture
def data_quality(sheets_client) -> DataQualityWriter:
    return DataQualityWriter(sheets_client)


def test_capture_offer_records_full_terms_not_just_headline(
    fake_service, archiver, sheets_writer, data_quality
):
    terms_html = FIXTURE_PATH.read_bytes()
    offer_id = capture_offer(
        brand_id="brand_1",
        geography="GB",
        customer_type="new",
        offer_type="deposit_match",
        headline_html=_HEADLINE_ONLY_HTML,
        terms_html=terms_html,
        terms_url="https://example-casino.example/promotions/welcome/terms",
        source_id=SOURCE_ID,
        archiver=archiver,
        writer=sheets_writer,
        data_quality=data_quality,
        actor="tester",
    )
    assert offer_id is not None

    header = SHEET_HEADERS["Offers"]
    row = dict(zip(header, fake_service.sheets["Offers"][1], strict=False))
    assert row["headline"] == "Get a 100% Welcome Bonus up to £200"
    assert "wagering" in row["description"].lower()
    assert len(row["description"]) > len(row["headline"])  # never headline-only
    assert row["minimum_deposit"] == "10"
    assert row["wagering_multiplier"] == "35"
    assert row["screenshot_document_id"]  # terms page archived for provenance


def test_capture_offer_routes_to_data_quality_when_terms_page_has_no_terms(
    fake_service, archiver, sheets_writer, data_quality
):
    empty_terms_html = b"<html><body><div class='offer-headline'>50 Free Spins</div></body></html>"

    result = capture_offer(
        brand_id="brand_1",
        geography="GB",
        customer_type="new",
        offer_type="free_spins",
        headline_html=empty_terms_html,
        terms_html=empty_terms_html,  # no .offer-full-terms element present
        terms_url="https://example-casino.example/promotions/spins/terms",
        source_id=SOURCE_ID,
        archiver=archiver,
        writer=sheets_writer,
        data_quality=data_quality,
        actor="tester",
    )
    assert result is None
    assert len(fake_service.sheets["Offers"]) == 1  # header only — nothing written
    assert len(fake_service.sheets["Data Quality"]) == 2  # header + 1 issue
