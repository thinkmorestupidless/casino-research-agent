"""Unit tests for product/game-catalogue observation capture (T067)."""

from __future__ import annotations

import pytest

from casino_intel.parsing.product_capture import capture_product_observation
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

LOBBY_HTML = b"""
<html><body>
  <div data-game-count="1500"></div>
  <div data-provider-name="NetEnt"></div>
  <div data-provider-name="Pragmatic Play"></div>
  <div data-feature="live-casino"></div>
  <div data-feature="game-search"></div>
  <div data-feature="filters"></div>
</body></html>
"""


@pytest.fixture(autouse=True)
def _sheet(fake_service):
    fake_service.add_sheet("Products", SHEET_HEADERS["Products"])


def test_capture_product_observation_detects_providers_and_features(fake_service, sheets_writer):
    record_id = capture_product_observation(
        LOBBY_HTML,
        brand_id="brand_1",
        vertical="casino",
        source_id="source_1",
        writer=sheets_writer,
        actor="tester",
    )
    assert record_id

    header = SHEET_HEADERS["Products"]
    row = dict(zip(header, fake_service.sheets["Products"][1], strict=False))
    assert row["game_count_estimated"] == 1500
    assert row["game_provider_count"] == 2
    assert "NetEnt" in row["named_providers"]
    assert row["live_casino_available"] is True
    assert row["game_search_available"] is True
    assert row["filters_available"] is True
    assert row["sportsbook_available"] is False
