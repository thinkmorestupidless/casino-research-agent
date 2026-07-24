"""Product/game-catalogue observation capture (data-model.md
"ProductObservation" domain view): lobby-page parsing for vertical
coverage, named game providers, and discovery features.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from casino_intel.models.ids import new_id
from casino_intel.parsing.html_parser import parse_html
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.writer import SheetsWriter

PRODUCTS_SHEET = "Products"

#: Lobby-page `data-feature` marker -> Products sheet boolean column. The
#: golden fixture / a real deployment's lobby markup tags each discovery
#: feature this way for reliable, source-locator-able detection.
_FEATURE_SELECTORS: dict[str, str] = {
    "live_casino_available": "[data-feature='live-casino']",
    "jackpots_available": "[data-feature='jackpots']",
    "sportsbook_available": "[data-feature='sportsbook']",
    "bingo_available": "[data-feature='bingo']",
    "poker_available": "[data-feature='poker']",
    "crash_games_available": "[data-feature='crash-games']",
    "demo_play_available": "[data-feature='demo-play']",
    "game_search_available": "[data-feature='game-search']",
    "filters_available": "[data-feature='filters']",
    "favourites_available": "[data-feature='favourites']",
    "recently_played_available": "[data-feature='recently-played']",
    "recommendations_available": "[data-feature='recommendations']",
}


def parse_lobby_page(html_content: bytes) -> dict[str, Any]:
    parsed = parse_html(html_content)
    features = {
        name: parsed.soup.select_one(selector) is not None
        for name, selector in _FEATURE_SELECTORS.items()
    }
    provider_elements = parsed.soup.select("[data-provider-name]")
    named_providers = sorted(
        {el["data-provider-name"] for el in provider_elements if el.has_attr("data-provider-name")}
    )
    game_count_el = parsed.soup.select_one("[data-game-count]")
    game_count = (
        int(game_count_el["data-game-count"])
        if game_count_el and game_count_el.has_attr("data-game-count")
        else None
    )
    return {
        **features,
        "named_providers": named_providers,
        "game_provider_count": len(named_providers),
        "game_count_estimated": game_count,
    }


def capture_product_observation(
    html_content: bytes,
    *,
    brand_id: str,
    vertical: str,
    source_id: str,
    writer: SheetsWriter,
    actor: str,
    ingestion_run_id: str | None = None,
) -> str:
    parsed = parse_lobby_page(html_content)
    now = datetime.now(UTC)
    header = SHEET_HEADERS[PRODUCTS_SHEET]
    record = {
        "record_id": new_id("product_observation"),
        "created_at": now.isoformat(),
        "created_by": actor,
        "updated_at": now.isoformat(),
        "status": "active",
        "notes": "",
        "source_id": source_id,
        "document_id": "",
        "evidence_type": "direct_observation",
        "confidence": "high",
        "review_status": "unreviewed",
        "captured_at": now.isoformat(),
        "valid_from": "",
        "valid_to": "",
        "period_start": "",
        "period_end": "",
        "brand_id": brand_id,
        "vertical": vertical,
        "game_count_estimated": parsed.get("game_count_estimated") or "",
        "game_provider_count": parsed.get("game_provider_count", 0),
        "named_providers": ", ".join(parsed.get("named_providers", [])),
        "exclusive_games_count": "",
        **{name: parsed.get(name, False) for name in _FEATURE_SELECTORS},
    }
    row = {col: record.get(col, "") for col in header}
    result = writer.append_record(
        PRODUCTS_SHEET, row, actor=actor, ingestion_run_id=ingestion_run_id
    )
    return result.record_id
