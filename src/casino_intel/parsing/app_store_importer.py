"""App-store presence capture (data-model.md "AppPresence" domain view).

`download_estimate` is kept strictly distinct from any active-user count —
this importer never writes a `download_estimate` value onto an
active-customer metric_id, and vice versa; the two are structurally
different fields/metrics throughout.

Each capture creates one `App Presence` row plus canonical `app_*`
Observations (`subject_type=app`, `subject_id` = the new `App Presence`
row's own id, since there is no separate App entity/table per
data-model.md — the App Presence row *is* the addressable "app" subject).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from casino_intel.models.ids import new_id
from casino_intel.services.observation_service import ObservationInput, ObservationService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.writer import SheetsWriter

APP_PRESENCE_SHEET = "App Presence"

#: App-store capture field -> canonical metric_id.
_METRIC_FIELDS: dict[str, str] = {
    "rating": "app_rating",
    "rating_count": "app_rating_count",
    "review_count": "app_review_count",
    "download_estimate": "app_download_estimate",
    "rank": "app_rank",
    "current_version": "app_version",
    "last_updated_at": "app_last_updated_at",
    "app_size_bytes": "app_size_bytes",
}


def import_app_store_capture(
    captures: list[dict[str, Any]],
    *,
    source_id: str,
    writer: SheetsWriter,
    observation_service: ObservationService,
    actor: str,
    ingestion_run_id: str | None = None,
) -> list[str]:
    """Each item of `captures` (parsed from a JSON export) must carry
    `brand_id`, `platform`, `app_id`, and should carry the App Presence
    fields listed in `sheets/schema_definitions.py`."""
    created_ids: list[str] = []
    now = datetime.now(UTC)
    header = SHEET_HEADERS[APP_PRESENCE_SHEET]

    for capture in captures:
        brand_id = str(capture["brand_id"])
        app_presence_id = new_id("app_presence")

        record = {
            "record_id": app_presence_id,
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
            "platform": str(capture.get("platform", "")),
            "store_country": str(capture.get("store_country", "")),
            "app_name": str(capture.get("app_name", "")),
            "developer_name": str(capture.get("developer_name", "")),
            "app_id": str(capture.get("app_id", "")),
            "store_url": str(capture.get("store_url", "")),
            "category": str(capture.get("category", "")),
            "rating": capture.get("rating", ""),
            "rating_count": capture.get("rating_count", ""),
            "review_count": capture.get("review_count", ""),
            "current_version": str(capture.get("current_version", "")),
            "last_updated_at": str(capture.get("last_updated_at", "")),
            "minimum_os": str(capture.get("minimum_os", "")),
            "app_size_bytes": capture.get("app_size_bytes", ""),
            "in_app_purchases": capture.get("in_app_purchases", ""),
            "age_rating": str(capture.get("age_rating", "")),
            "download_estimate": capture.get("download_estimate", ""),
            "rank": capture.get("rank", ""),
        }
        row_for_sheet = {col: record.get(col, "") for col in header}
        appended = writer.append_record(
            APP_PRESENCE_SHEET, row_for_sheet, actor=actor, ingestion_run_id=ingestion_run_id
        )
        created_ids.append(appended.record_id)

        for field_name, metric_id in _METRIC_FIELDS.items():
            value = capture.get(field_name)
            if value in (None, ""):
                continue
            numeric_value = _to_float(value)
            observation_service.record_observation(
                ObservationInput(
                    subject_type="app",
                    subject_id=app_presence_id,
                    metric_id=metric_id,
                    raw_value=str(value),
                    source_id=source_id,
                    evidence_type="direct_observation",
                    confidence="high",
                    normalised_numeric_value=numeric_value,
                    geography=str(capture.get("store_country", "")),
                    created_by=actor,
                ),
                actor=actor,
                ingestion_run_id=ingestion_run_id,
            )

    return created_ids


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
