"""Reputation aggregation import (data-model.md "Reputation" domain view,
spec FR-030/FR-047): only aggregate scores and paraphrased recurring
themes are ever stored — raw review text and reviewer usernames must never
reach this sheet.
"""

from __future__ import annotations

from datetime import UTC, datetime

from casino_intel.models.ids import new_id
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.writer import SheetsWriter

REPUTATION_SHEET = "Reputation"

#: A paraphrased theme summary should be a short synthesis, not a
#: transcript — this is a heuristic guard, not a substitute for the
#: paraphrasing itself happening upstream of this importer.
MAX_THEME_SUMMARY_LENGTH = 400
_USERNAME_MARKERS = ("@", "u/", "posted by", "reviewer:")


class RawReviewContentError(ValueError):
    """Raised when a theme summary looks like verbatim review text or
    references an individual reviewer, rather than an aggregated,
    paraphrased summary (FR-030/FR-047)."""


def assert_paraphrased_theme(summary: str) -> None:
    if len(summary) > MAX_THEME_SUMMARY_LENGTH:
        raise RawReviewContentError(
            f"Theme summary is {len(summary)} chars (> {MAX_THEME_SUMMARY_LENGTH}) — "
            "looks like verbatim review text rather than a paraphrased summary."
        )
    lowered = summary.lower()
    if any(marker in lowered for marker in _USERNAME_MARKERS):
        raise RawReviewContentError(
            "Theme summary appears to reference a username/handle — individual "
            "reviewer identities must never be stored (FR-047)."
        )


def import_reputation_summary(
    *,
    brand_id: str,
    platform: str,
    profile_url: str,
    score: float,
    score_scale_max: float,
    review_count: int,
    recent_review_window_days: int,
    recent_review_count: int,
    positive_theme_summary: str,
    negative_theme_summary: str,
    source_id: str,
    writer: SheetsWriter,
    actor: str,
    withdrawal_complaint_share: float | None = None,
    verification_complaint_share: float | None = None,
    bonus_complaint_share: float | None = None,
    support_complaint_share: float | None = None,
    suspected_review_manipulation: bool = False,
    methodology_note: str = "",
    ingestion_run_id: str | None = None,
) -> str:
    """Raises `RawReviewContentError` rather than storing anything if either
    theme summary looks like raw review content (fail closed, not silently
    truncate/accept)."""
    assert_paraphrased_theme(positive_theme_summary)
    assert_paraphrased_theme(negative_theme_summary)

    now = datetime.now(UTC)
    header = SHEET_HEADERS[REPUTATION_SHEET]
    record = {
        "record_id": new_id("reputation"),
        "created_at": now.isoformat(),
        "created_by": actor,
        "updated_at": now.isoformat(),
        "status": "active",
        "notes": "",
        "source_id": source_id,
        "document_id": "",
        "evidence_type": "third_party_estimate",
        "confidence": "medium",
        "review_status": "unreviewed",
        "captured_at": now.isoformat(),
        "valid_from": "",
        "valid_to": "",
        "period_start": "",
        "period_end": "",
        "brand_id": brand_id,
        "platform": platform,
        "profile_url": profile_url,
        "score": score,
        "score_scale_max": score_scale_max,
        "review_count": review_count,
        "recent_review_window_days": recent_review_window_days,
        "recent_review_count": recent_review_count,
        "positive_theme_summary": positive_theme_summary,
        "negative_theme_summary": negative_theme_summary,
        "withdrawal_complaint_share": (
            withdrawal_complaint_share if withdrawal_complaint_share is not None else ""
        ),
        "verification_complaint_share": (
            verification_complaint_share if verification_complaint_share is not None else ""
        ),
        "bonus_complaint_share": bonus_complaint_share if bonus_complaint_share is not None else "",
        "support_complaint_share": (
            support_complaint_share if support_complaint_share is not None else ""
        ),
        "suspected_review_manipulation": suspected_review_manipulation,
        "methodology_note": methodology_note,
    }
    row = {col: record.get(col, "") for col in header}
    result = writer.append_record(
        REPUTATION_SHEET, row, actor=actor, ingestion_run_id=ingestion_run_id
    )
    return result.record_id
