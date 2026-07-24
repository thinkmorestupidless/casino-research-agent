"""Google Trends CSV import (spec FR-026, data-model.md "SearchInterest"
domain view).

`interest_index` is a *relative* index (Google Trends), never comparable
across a differing `comparison_set_id` without a documented rescaling
method — every row is tagged with the `comparison_set_id`/`anchor_term` it
was captured under, and the canonical `branded_search_interest_index`
Observation carries the same `comparability_group` so nothing downstream
can silently compare across sets.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from casino_intel.models.ids import new_id
from casino_intel.services.observation_service import ObservationInput, ObservationService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.writer import SheetsWriter

SEARCH_INTEREST_SHEET = "Search Interest"
METRIC_ID = "branded_search_interest_index"


def import_trends_rows(
    table: pd.DataFrame,
    *,
    source_id: str,
    document_id: str,
    writer: SheetsWriter,
    observation_service: ObservationService,
    actor: str,
    ingestion_run_id: str | None = None,
) -> list[str]:
    """Each row of `table` must carry `brand_id`, `comparison_set_id`,
    `interest_index`, and should carry `query_text`/`query_type`/
    `platform`/`geography`/`category`/`granularity`/`anchor_term`.
    """
    created_ids: list[str] = []
    now = datetime.now(UTC)
    header = SHEET_HEADERS[SEARCH_INTEREST_SHEET]

    for _, row in table.iterrows():
        brand_id = str(row["brand_id"])
        comparison_set_id = str(row["comparison_set_id"])
        interest_index = row.get("interest_index")
        if pd.isna(interest_index):
            continue

        result = observation_service.record_observation(
            ObservationInput(
                subject_type="brand",
                subject_id=brand_id,
                metric_id=METRIC_ID,
                raw_value=str(interest_index),
                source_id=source_id,
                evidence_type="third_party_estimate",
                confidence="medium",
                normalised_numeric_value=float(interest_index),
                geography=(
                    str(row.get("geography", "")) if not pd.isna(row.get("geography", "")) else ""
                ),
                comparability_group=comparison_set_id,
                document_id=document_id,
                methodology_note=f"anchor_term={row.get('anchor_term', '')}",
                created_by=actor,
            ),
            actor=actor,
            ingestion_run_id=ingestion_run_id,
        )
        if result is None or result.duplicate:
            continue

        record = {
            "record_id": new_id("search_interest"),
            "created_at": now.isoformat(),
            "created_by": actor,
            "updated_at": now.isoformat(),
            "status": "active",
            "notes": "",
            "source_id": source_id,
            "document_id": document_id,
            "evidence_type": "third_party_estimate",
            "confidence": "medium",
            "review_status": "unreviewed",
            "captured_at": now.isoformat(),
            "valid_from": "",
            "valid_to": "",
            "period_start": "",
            "period_end": "",
            "brand_id": brand_id,
            "query_text": str(row.get("query_text", "")),
            "query_type": str(row.get("query_type", "exact_term")),
            "platform": str(row.get("platform", "google_trends")),
            "geography": (
                str(row.get("geography", "")) if not pd.isna(row.get("geography", "")) else ""
            ),
            "category": str(row.get("category", "")),
            "granularity": str(row.get("granularity", "")),
            "interest_index": interest_index,
            "comparison_set_id": comparison_set_id,
            "anchor_term": str(row.get("anchor_term", "")),
            "export_file_document_id": document_id,
        }
        row_for_sheet = [record.get(col, "") for col in header]
        appended = writer.append_record(
            SEARCH_INTEREST_SHEET,
            dict(zip(header, row_for_sheet, strict=False)),
            actor=actor,
            ingestion_run_id=ingestion_run_id,
        )
        created_ids.append(appended.record_id)

    return created_ids
