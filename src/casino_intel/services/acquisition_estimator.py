"""Acquisition/CPA-range estimator (data-model.md "Acquisition" domain
view, spec FR-024): combines reported figures, affiliate offer terms, and
paid-search cost data into an indicative CPA range.

Any CPA figure derived from *group*-level marketing expense (rather than a
brand-reported figure) is always labelled a group-level proxy in its
`methodology_note` — never presented as if it were a brand-specific
reported number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from casino_intel.models.ids import new_id
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.writer import SheetsWriter

ACQUISITION_SHEET = "Acquisition"

GROUP_LEVEL_PROXY_LABEL = "group_level_proxy"


@dataclass(frozen=True)
class CpaRangeEstimate:
    low: float
    mid: float
    high: float
    is_group_level_proxy: bool
    methodology_note: str


def estimate_cpa_from_group_marketing_spend(
    *,
    group_marketing_expense: float,
    group_new_customers: float,
    uncertainty_pct: float = 0.25,
) -> CpaRangeEstimate:
    """FR-024: a CPA derived from *group* marketing spend divided by *group*
    new customers is a rough, brand-agnostic proxy — always labelled as
    such via `GROUP_LEVEL_PROXY_LABEL`, never mistaken for a brand-reported CPA."""
    if group_new_customers <= 0:
        raise ValueError("group_new_customers must be positive")
    mid = group_marketing_expense / group_new_customers
    return CpaRangeEstimate(
        low=round(mid * (1 - uncertainty_pct), 2),
        mid=round(mid, 2),
        high=round(mid * (1 + uncertainty_pct), 2),
        is_group_level_proxy=True,
        methodology_note=(
            f"{GROUP_LEVEL_PROXY_LABEL}: derived from group marketing expense "
            f"({group_marketing_expense}) / group new customers ({group_new_customers}); "
            "not a brand-specific reported figure (FR-024)."
        ),
    )


def estimate_cpa_from_affiliate_terms(
    *, affiliate_cpa_offer: float, paid_keyword_cpc_low: float, paid_keyword_cpc_high: float
) -> CpaRangeEstimate:
    """A brand-specific indicative range from its own affiliate CPA offer
    and paid-search CPC bounds — not a group-level proxy."""
    low = min(affiliate_cpa_offer, paid_keyword_cpc_low)
    high = max(affiliate_cpa_offer, paid_keyword_cpc_high)
    mid = (low + high) / 2
    return CpaRangeEstimate(
        low=round(low, 2),
        mid=round(mid, 2),
        high=round(high, 2),
        is_group_level_proxy=False,
        methodology_note=(
            f"Derived from affiliate CPA offer ({affiliate_cpa_offer}) and paid-search "
            f"CPC range ({paid_keyword_cpc_low}-{paid_keyword_cpc_high})."
        ),
    )


def record_acquisition_estimate(
    *,
    brand_id: str,
    geography: str,
    channel: str,
    estimate: CpaRangeEstimate,
    source_id: str,
    writer: SheetsWriter,
    actor: str,
    affiliate_model: str = "",
    affiliate_cpa_offer: float | None = None,
    affiliate_revenue_share_percent: float | None = None,
    paid_keyword_cpc_low: float | None = None,
    paid_keyword_cpc_high: float | None = None,
    ingestion_run_id: str | None = None,
) -> str:
    now = datetime.now(UTC)
    header = SHEET_HEADERS[ACQUISITION_SHEET]
    record = {
        "record_id": new_id("acquisition"),
        "created_at": now.isoformat(),
        "created_by": actor,
        "updated_at": now.isoformat(),
        "status": "active",
        "notes": "",
        "source_id": source_id,
        "document_id": "",
        "evidence_type": "inferred_range",
        "confidence": "low" if estimate.is_group_level_proxy else "medium",
        "review_status": "unreviewed",
        "captured_at": now.isoformat(),
        "valid_from": "",
        "valid_to": "",
        "period_start": "",
        "period_end": "",
        "brand_id": brand_id,
        "geography": geography,
        "channel": channel,
        "traffic_share": "",
        "spend_reported": "",
        "spend_estimated": "",
        "new_customers_reported": "",
        "new_customers_estimated": "",
        "cpa_reported": "",
        "cpa_estimate_low": estimate.low,
        "cpa_estimate_mid": estimate.mid,
        "cpa_estimate_high": estimate.high,
        "affiliate_model": affiliate_model,
        "affiliate_cpa_offer": affiliate_cpa_offer if affiliate_cpa_offer is not None else "",
        "affiliate_revenue_share_percent": (
            affiliate_revenue_share_percent if affiliate_revenue_share_percent is not None else ""
        ),
        "paid_keyword_cpc_low": paid_keyword_cpc_low if paid_keyword_cpc_low is not None else "",
        "paid_keyword_cpc_high": paid_keyword_cpc_high if paid_keyword_cpc_high is not None else "",
        "methodology_note": estimate.methodology_note,
    }
    row = {col: record.get(col, "") for col in header}
    result = writer.append_record(
        ACQUISITION_SHEET, row, actor=actor, ingestion_run_id=ingestion_run_id
    )
    return result.record_id
