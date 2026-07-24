"""Offer capture from brand promotion pages and their full terms pages
(spec FR-028): must capture full terms, never headline-only. The terms
page's raw HTML is archived (`fetching/archiver.py`, T045) so a recorded
offer stays traceable to source content even after the live page changes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from casino_intel.fetching.archiver import DocumentArchiver
from casino_intel.models.ids import new_id
from casino_intel.models.vocab import DataQualityIssueType
from casino_intel.parsing.html_parser import parse_html
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.writer import SheetsWriter
from casino_intel.validation.data_quality import DataQualityWriter

OFFERS_SHEET = "Offers"

#: CSS selectors this importer looks for on a promotion/terms page. The
#: golden fixture (tests/fixtures/promotion_terms.html) matches this exact
#: structure; a real deployment would tune per-brand selectors similarly.
_FIELD_SELECTORS: dict[str, str] = {
    "headline": ".offer-headline",
    "promo_code": ".offer-promo-code",
    "minimum_deposit": ".offer-minimum-deposit",
    "maximum_bonus": ".offer-maximum-bonus",
    "bonus_percentage": ".offer-bonus-percentage",
    "wagering_multiplier": ".offer-wagering-multiplier",
    "wagering_basis": ".offer-wagering-basis",
    "time_limit_days": ".offer-time-limit-days",
    "full_terms": ".offer-full-terms",
}


def parse_offer_page(html_content: bytes) -> dict[str, str]:
    """Extract known offer fields from a promotion/terms page's markup."""
    parsed = parse_html(html_content)
    fields: dict[str, str] = {}
    for field_name, selector in _FIELD_SELECTORS.items():
        el = parsed.soup.select_one(selector)
        fields[field_name] = el.get_text(strip=True) if el else ""
    return fields


def capture_offer(
    *,
    brand_id: str,
    geography: str,
    customer_type: str,
    offer_type: str,
    headline_html: bytes,
    terms_html: bytes,
    terms_url: str,
    source_id: str,
    archiver: DocumentArchiver,
    writer: SheetsWriter,
    data_quality: DataQualityWriter,
    actor: str,
    ingestion_run_id: str | None = None,
) -> str | None:
    """Capture one offer from its headline page and full terms page.

    Returns the new `Offers` row id, or `None` if routed to Data Quality
    instead (e.g. the terms page carries no usable terms text — FR-028
    prohibits recording a headline-only offer).
    """
    headline_fields = parse_offer_page(headline_html)
    terms_fields = parse_offer_page(terms_html)

    full_terms = terms_fields.get("full_terms", "")
    if not full_terms:
        data_quality.raise_issue(
            issue_type=DataQualityIssueType.MISSING_SOURCE,
            sheet_name=OFFERS_SHEET,
            field_name="full_terms",
            description=(
                f"Offer for brand {brand_id} has a headline but no full terms captured "
                "from the terms page — FR-028 prohibits headline-only capture."
            ),
        )
        return None

    archive_result = archiver.archive_fetch(
        source_id=source_id,
        filename=f"{brand_id}-offer-terms.html",
        content=terms_html,
        mime_type="text/html",
        relative_folder="screenshots/brand",
        actor=actor,
        ingestion_run_id=ingestion_run_id,
    )

    now = datetime.now(UTC)
    header = SHEET_HEADERS[OFFERS_SHEET]
    record = {
        "record_id": new_id("offer"),
        "created_at": now.isoformat(),
        "created_by": actor,
        "updated_at": now.isoformat(),
        "status": "active",
        "notes": "",
        "source_id": source_id,
        "document_id": archive_result.document_id,
        "evidence_type": "direct_observation",
        "confidence": "high",
        "review_status": "unreviewed",
        "captured_at": now.isoformat(),
        "valid_from": "",
        "valid_to": "",
        "period_start": "",
        "period_end": "",
        "brand_id": brand_id,
        "geography": geography,
        "customer_type": customer_type,
        "offer_type": offer_type,
        "headline": headline_fields.get("headline", ""),
        "description": full_terms,
        "promo_code": terms_fields.get("promo_code") or headline_fields.get("promo_code", ""),
        "minimum_deposit": terms_fields.get("minimum_deposit", ""),
        "maximum_bonus": terms_fields.get("maximum_bonus", ""),
        "bonus_percentage": terms_fields.get("bonus_percentage", ""),
        "free_spins_count": "",
        "free_spin_value": "",
        "wagering_multiplier": terms_fields.get("wagering_multiplier", ""),
        "wagering_basis": terms_fields.get("wagering_basis", ""),
        "qualifying_games": "",
        "excluded_games": "",
        "minimum_odds": "",
        "maximum_bet_during_wagering": "",
        "time_limit_days": terms_fields.get("time_limit_days", ""),
        "withdrawal_cap": "",
        "cashback_percentage": "",
        "cashback_cap": "",
        "opt_in_required": "",
        "terms_url": terms_url,
        "screenshot_document_id": archive_result.document_id,
        "terms_clarity_score": "",
    }
    row = {col: record.get(col, "") for col in header}
    result = writer.append_record(OFFERS_SHEET, row, actor=actor, ingestion_run_id=ingestion_run_id)
    return result.record_id
