"""Brand traffic-provider CSV/XLSX import (spec FR-025, data-model.md
"Traffic" domain view).

Each input row is attributed to exactly one `provider` and is never merged
with another provider's numbers for the same brand/period — every row gets
its own `comparability_group` scoped to (provider, geography, device_scope)
so nothing downstream can silently average across providers.

Every numeric column also becomes a canonical `Observation`
(`services/observation_service.py`), so idempotent re-ingestion and
Data-Quality routing come for free; the `Traffic` sheet row is written only
when at least one of those canonical observations was newly recorded (not
a duplicate), so re-running against an unchanged export does not create
repeat `Traffic` rows either.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from casino_intel.models.ids import new_id
from casino_intel.services.observation_service import ObservationInput, ObservationService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.serialization import flatten_value
from casino_intel.sheets.writer import SheetsWriter

TRAFFIC_SHEET = "Traffic"

#: Traffic CSV/XLSX column -> canonical metric_id.
_METRIC_COLUMNS: dict[str, str] = {
    "estimated_visits": "estimated_monthly_visits",
    "estimated_unique_visitors": "estimated_unique_visitors",
    "visit_duration_seconds": "visit_duration_seconds",
    "pages_per_visit": "pages_per_visit",
    "bounce_rate": "bounce_rate",
    "traffic_share_direct": "traffic_share_direct",
    "traffic_share_organic": "traffic_share_organic",
    "traffic_share_paid": "traffic_share_paid",
    "traffic_share_referral": "traffic_share_referral",
    "traffic_share_social": "traffic_share_social",
    "traffic_share_display": "traffic_share_display",
}


def import_traffic_rows(
    table: pd.DataFrame,
    *,
    source_id: str,
    writer: SheetsWriter,
    observation_service: ObservationService,
    actor: str,
    ingestion_run_id: str | None = None,
    document_id: str | None = None,
) -> list[str]:
    """Each row of `table` must carry `brand_id`, `domain`, `provider`, and
    should carry `geography`/`device_scope`/`period_start`/`period_end`
    plus zero or more of the metric columns above. Returns the list of
    newly-created `Traffic` row ids (empty entries skipped as duplicates).

    When the export has been archived as a `Document`, pass its `document_id`
    so both the canonical observations and the `Traffic` view row link back to
    the archived file (data-model.md optional `document_id` FK).
    """
    created_ids: list[str] = []
    now = datetime.now(UTC)
    header = SHEET_HEADERS[TRAFFIC_SHEET]

    for _, row in table.iterrows():
        brand_id = str(row["brand_id"])
        provider = str(row.get("provider", ""))
        geography = str(row.get("geography", "")) if not pd.isna(row.get("geography", "")) else ""
        device_scope = (
            str(row.get("device_scope", "")) if not pd.isna(row.get("device_scope", "")) else ""
        )
        period_start = _clean(row.get("period_start"))
        period_end = _clean(row.get("period_end"))
        comparability_group = f"web_visits_{provider}_{geography}_{device_scope}".strip("_")

        any_new = False
        for column, metric_id in _METRIC_COLUMNS.items():
            if column not in row or pd.isna(row[column]):
                continue
            result = observation_service.record_observation(
                ObservationInput(
                    subject_type="brand",
                    subject_id=brand_id,
                    metric_id=metric_id,
                    raw_value=str(row[column]),
                    source_id=source_id,
                    document_id=document_id,
                    evidence_type="third_party_estimate",
                    confidence="medium",
                    normalised_numeric_value=_to_float(row[column]),
                    period_start=period_start,
                    period_end=period_end,
                    geography=geography,
                    comparability_group=comparability_group,
                    methodology_note=f"provider={provider}",
                    created_by=actor,
                ),
                actor=actor,
                ingestion_run_id=ingestion_run_id,
            )
            if result is not None and not result.duplicate:
                any_new = True

        if not any_new:
            continue

        traffic_record = {
            "record_id": new_id("traffic"),
            "created_at": now.isoformat(),
            "created_by": actor,
            "updated_at": now.isoformat(),
            "status": "active",
            "notes": "",
            "source_id": source_id,
            "document_id": document_id or "",
            "evidence_type": "third_party_estimate",
            "confidence": "medium",
            "review_status": "unreviewed",
            "captured_at": now.isoformat(),
            "valid_from": "",
            "valid_to": "",
            "period_start": period_start or "",
            "period_end": period_end or "",
            "brand_id": brand_id,
            "domain": str(row.get("domain", "")),
            "provider": provider,
            "geography": geography,
            "device_scope": device_scope,
            "estimated_visits": flatten_value(row.get("estimated_visits")),
            "estimated_unique_visitors": flatten_value(row.get("estimated_unique_visitors")),
            "visit_duration_seconds": flatten_value(row.get("visit_duration_seconds")),
            "pages_per_visit": flatten_value(row.get("pages_per_visit")),
            "bounce_rate": flatten_value(row.get("bounce_rate")),
            "traffic_share_direct": flatten_value(row.get("traffic_share_direct")),
            "traffic_share_organic": flatten_value(row.get("traffic_share_organic")),
            "traffic_share_paid": flatten_value(row.get("traffic_share_paid")),
            "traffic_share_referral": flatten_value(row.get("traffic_share_referral")),
            "traffic_share_social": flatten_value(row.get("traffic_share_social")),
            "traffic_share_display": flatten_value(row.get("traffic_share_display")),
            "top_referral_domains": str(row.get("top_referral_domains", "")),
            "top_destination_domains": str(row.get("top_destination_domains", "")),
            "provider_methodology_version": str(row.get("provider_methodology_version", "")),
        }
        record = {col: _clean_nan(traffic_record.get(col, "")) for col in header}
        result = writer.append_record(
            TRAFFIC_SHEET, record, actor=actor, ingestion_run_id=ingestion_run_id
        )
        created_ids.append(result.record_id)

    return created_ids


def _clean(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _clean_nan(value: object) -> object:
    if isinstance(value, float) and pd.isna(value):
        return ""
    return value


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
