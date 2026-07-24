"""Unit tests for reputation aggregation import (T068, spec FR-030/FR-047):
only aggregate scores and paraphrased themes are stored — raw review text
and usernames must be rejected, never silently truncated or accepted."""

from __future__ import annotations

import pytest

from casino_intel.parsing.reputation_importer import (
    RawReviewContentError,
    import_reputation_summary,
)
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

SOURCE_ID = "source_reputation_1"


@pytest.fixture(autouse=True)
def _sheet(fake_service):
    fake_service.add_sheet("Reputation", SHEET_HEADERS["Reputation"])


def test_import_reputation_summary_stores_aggregate_and_paraphrased_themes(
    fake_service, sheets_writer
):
    reputation_id = import_reputation_summary(
        brand_id="brand_1",
        platform="trustpilot",
        profile_url="https://www.trustpilot.com/review/example-casino.example",
        score=4.1,
        score_scale_max=5,
        review_count=3200,
        recent_review_window_days=90,
        recent_review_count=210,
        positive_theme_summary="Customers frequently praise fast withdrawals and game variety.",
        negative_theme_summary="Recurring complaints about slow KYC verification at withdrawal.",
        source_id=SOURCE_ID,
        writer=sheets_writer,
        actor="tester",
    )
    assert reputation_id

    header = SHEET_HEADERS["Reputation"]
    row = dict(zip(header, fake_service.sheets["Reputation"][1], strict=False))
    assert row["score"] == 4.1
    assert "withdrawals" in row["positive_theme_summary"]
    assert "KYC" in row["negative_theme_summary"]


def test_import_reputation_summary_rejects_verbatim_length_review_text(fake_service, sheets_writer):
    with pytest.raises(RawReviewContentError):
        import_reputation_summary(
            brand_id="brand_1",
            platform="trustpilot",
            profile_url="https://www.trustpilot.com/review/example-casino.example",
            score=4.1,
            score_scale_max=5,
            review_count=3200,
            recent_review_window_days=90,
            recent_review_count=210,
            positive_theme_summary="x" * 401,  # over the paraphrase-length guard
            negative_theme_summary="Short summary.",
            source_id=SOURCE_ID,
            writer=sheets_writer,
            actor="tester",
        )
    assert len(fake_service.sheets["Reputation"]) == 1  # nothing written


def test_import_reputation_summary_rejects_username_reference(fake_service, sheets_writer):
    with pytest.raises(RawReviewContentError):
        import_reputation_summary(
            brand_id="brand_1",
            platform="trustpilot",
            profile_url="https://www.trustpilot.com/review/example-casino.example",
            score=4.1,
            score_scale_max=5,
            review_count=3200,
            recent_review_window_days=90,
            recent_review_count=210,
            positive_theme_summary="Good experience overall.",
            negative_theme_summary="Reviewer: @jsmith82 said withdrawals were slow.",
            source_id=SOURCE_ID,
            writer=sheets_writer,
            actor="tester",
        )
    assert len(fake_service.sheets["Reputation"]) == 1
