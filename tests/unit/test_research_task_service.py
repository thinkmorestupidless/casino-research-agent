"""Unit tests for Research Task auto-creation on ingestion blockers (T062)."""

from __future__ import annotations

import pytest

from casino_intel.models.vocab import TaskStatus, TaskType
from casino_intel.services.research_task_service import ResearchTaskService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

SHEET_NAME = "Research Queue"


@pytest.fixture(autouse=True)
def _sheet(fake_service):
    fake_service.add_sheet(SHEET_NAME, SHEET_HEADERS[SHEET_NAME])


@pytest.fixture
def service(sheets_client) -> ResearchTaskService:
    return ResearchTaskService(sheets_client)


def test_flag_paywalled_source_creates_open_download_document_task(fake_service, service):
    service.flag_paywalled_source(source_id="source_1", url="https://paywalled.example/report")

    header = SHEET_HEADERS[SHEET_NAME]
    row = dict(zip(header, fake_service.sheets[SHEET_NAME][1], strict=False))
    assert row["task_type"] == TaskType.DOWNLOAD_DOCUMENT.value
    assert row["status"] == TaskStatus.OPEN.value
    assert "paywalled" in row["blocking_issue"]


def test_flag_parse_failure_creates_parse_document_task(fake_service, service):
    service.flag_parse_failure(source_id="source_1", document_id="document_1", error="bad xlsx")

    header = SHEET_HEADERS[SHEET_NAME]
    row = dict(zip(header, fake_service.sheets[SHEET_NAME][1], strict=False))
    assert row["task_type"] == TaskType.PARSE_DOCUMENT.value
    assert "bad xlsx" in row["blocking_issue"]


def test_flag_unresolved_conflict_creates_review_conflict_task(fake_service, service):
    service.flag_unresolved_conflict(
        subject_type="brand",
        subject_id="brand_1",
        metric_id="estimated_monthly_visits",
        description="Two high-confidence sources disagree",
    )

    header = SHEET_HEADERS[SHEET_NAME]
    row = dict(zip(header, fake_service.sheets[SHEET_NAME][1], strict=False))
    assert row["task_type"] == TaskType.REVIEW_CONFLICT.value
    assert row["requested_metric_ids"] == "estimated_monthly_visits"


def test_tasks_are_never_overwritten_only_appended(fake_service, service):
    service.flag_paywalled_source(source_id="source_1", url="https://paywalled.example/1")
    service.flag_paywalled_source(source_id="source_2", url="https://paywalled.example/2")

    assert len(fake_service.sheets[SHEET_NAME]) == 3  # header + 2 distinct tasks
