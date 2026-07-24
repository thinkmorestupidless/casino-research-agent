"""Unit tests for the human review workflow (T057): review_status
transitions, and that a "correction" is a new row plus a rejection on the
old one, never an in-place value edit."""

from __future__ import annotations

import pytest

from casino_intel.models.base import InvalidStatusTransition
from casino_intel.services.review_service import ReviewService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

OBSERVATIONS_SHEET = "Observations"


@pytest.fixture(autouse=True)
def _observations_sheet(fake_service):
    fake_service.add_sheet(OBSERVATIONS_SHEET, SHEET_HEADERS[OBSERVATIONS_SHEET])


@pytest.fixture
def review_service(sheets_client, change_log_writer) -> ReviewService:
    return ReviewService(sheets_client, change_log_writer)


def _seed_observation_row(fake_service, *, record_id: str, review_status: str = "unreviewed"):
    header = SHEET_HEADERS[OBSERVATIONS_SHEET]
    row = ["" for _ in header]
    row[header.index("record_id")] = record_id
    row[header.index("status")] = "active"
    row[header.index("review_status")] = review_status
    row[header.index("subject_id")] = "brand_1"
    row[header.index("metric_id")] = "estimated_monthly_visits"
    row[header.index("raw_value")] = "1,000,000"
    fake_service.sheets[OBSERVATIONS_SHEET].append(row)


def test_approve_requires_passing_through_machine_checked_and_human_reviewed(
    fake_service, review_service
):
    _seed_observation_row(fake_service, record_id="obs_1", review_status="unreviewed")

    with pytest.raises(InvalidStatusTransition):
        review_service.approve(OBSERVATIONS_SHEET, "obs_1", actor="tester")


def test_full_approve_path_transitions_through_the_legal_graph(fake_service, review_service):
    _seed_observation_row(fake_service, record_id="obs_1", review_status="unreviewed")

    review_service.mark_machine_checked(OBSERVATIONS_SHEET, "obs_1", actor="tester")
    review_service.mark_human_reviewed(OBSERVATIONS_SHEET, "obs_1", actor="tester")
    review_service.approve(OBSERVATIONS_SHEET, "obs_1", actor="tester")

    header = SHEET_HEADERS[OBSERVATIONS_SHEET]
    row = fake_service.sheets[OBSERVATIONS_SHEET][1]
    assert dict(zip(header, row, strict=False))["review_status"] == "approved"


def test_reject_is_legal_from_unreviewed(fake_service, review_service):
    _seed_observation_row(fake_service, record_id="obs_1", review_status="unreviewed")
    review_service.reject(OBSERVATIONS_SHEET, "obs_1", actor="tester", reason="bad extraction")

    header = SHEET_HEADERS[OBSERVATIONS_SHEET]
    row = fake_service.sheets[OBSERVATIONS_SHEET][1]
    assert dict(zip(header, row, strict=False))["review_status"] == "rejected"


def test_approve_is_terminal_no_further_transition_allowed(fake_service, review_service):
    _seed_observation_row(fake_service, record_id="obs_1", review_status="unreviewed")
    review_service.mark_machine_checked(OBSERVATIONS_SHEET, "obs_1", actor="tester")
    review_service.mark_human_reviewed(OBSERVATIONS_SHEET, "obs_1", actor="tester")
    review_service.approve(OBSERVATIONS_SHEET, "obs_1", actor="tester")

    with pytest.raises(InvalidStatusTransition):
        review_service.reject(OBSERVATIONS_SHEET, "obs_1", actor="tester")


def test_correct_rejects_old_row_and_appends_a_new_one(fake_service, review_service, sheets_writer):
    _seed_observation_row(fake_service, record_id="obs_1", review_status="unreviewed")

    new_id = review_service.correct(
        OBSERVATIONS_SHEET,
        "obs_1",
        writer=sheets_writer,
        corrected_fields={"raw_value": "1,050,000"},
        actor="tester",
        reason="typo in original extraction",
    )

    header = SHEET_HEADERS[OBSERVATIONS_SHEET]
    rows = fake_service.sheets[OBSERVATIONS_SHEET][1:]
    assert len(rows) == 2  # the old row is retained, never deleted or edited in place
    as_dicts = [dict(zip(header, row, strict=False)) for row in rows]

    old_row = next(r for r in as_dicts if r["record_id"] == "obs_1")
    assert old_row["review_status"] == "rejected"
    assert old_row["raw_value"] == "1,000,000"  # untouched — no in-place edit

    new_row = next(r for r in as_dicts if r["record_id"] == new_id)
    assert new_row["raw_value"] == "1,050,000"
    assert new_row["review_status"] == "unreviewed"
    assert new_row["record_id"] != old_row["record_id"]
