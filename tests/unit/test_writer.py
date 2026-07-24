import pytest

from casino_intel.models.base import InvalidStatusTransition
from casino_intel.models.vocab import RecordStatus


def test_append_record_writes_row_and_change_log(sheets_writer, fake_service):
    fake_service.add_sheet("Brands", ["record_id", "brand_name", "source_id"])
    result = sheets_writer.append_record(
        "Brands",
        {"record_id": "brand_1", "brand_name": "Example Casino", "source_id": "source_1"},
        actor="tester",
    )
    assert result.written
    assert fake_service.sheets["Brands"][1] == ["brand_1", "Example Casino", "source_1"]
    change_log_rows = fake_service.sheets["Change Log"]
    assert len(change_log_rows) == 2  # header + 1 entry
    assert change_log_rows[1][3] == "create"
    assert change_log_rows[1][5] == "brand_1"


def test_append_record_escapes_formula_injection(sheets_writer, fake_service):
    fake_service.add_sheet("Offers", ["record_id", "headline"])
    sheets_writer.append_record(
        "Offers", {"record_id": "offer_1", "headline": '=HYPERLINK("evil")'}, actor="tester"
    )
    assert fake_service.sheets["Offers"][1][1].startswith("'")


def test_append_observation_is_idempotent_on_unchanged_fingerprint(sheets_writer, fake_service):
    fake_service.add_sheet(
        "Observations",
        [
            "record_id",
            "subject_id",
            "metric_id",
            "period_start",
            "period_end",
            "as_of_date",
            "geography",
            "segment",
            "source_id",
            "raw_value",
        ],
    )
    obs = {
        "record_id": "obs_1",
        "subject_id": "brand_1",
        "metric_id": "estimated_monthly_visits",
        "period_start": "2026-06-01",
        "period_end": "2026-06-30",
        "as_of_date": None,
        "geography": "GB",
        "segment": "casino",
        "source_id": "source_1",
        "raw_value": "1000000",
    }
    first = sheets_writer.append_observation("Observations", obs, actor="tester")
    assert first.written and not first.duplicate

    duplicate_obs = {**obs, "record_id": "obs_2"}  # same fact, re-ingested
    second = sheets_writer.append_observation("Observations", duplicate_obs, actor="tester")
    assert not second.written
    assert second.duplicate
    assert second.record_id == "obs_1"

    # Only one data row was ever appended, despite two calls.
    assert len(fake_service.sheets["Observations"]) == 2  # header + 1 row


def test_transition_status_updates_only_status_column(sheets_writer, fake_service):
    fake_service.add_sheet("Observations", ["record_id", "raw_value", "status"])
    fake_service.sheets["Observations"].append(["obs_1", "1000000", "active"])

    sheets_writer.transition_status(
        "Observations",
        "obs_1",
        RecordStatus.SUPERSEDED,
        actor="tester",
        current_status=RecordStatus.ACTIVE,
    )

    row = fake_service.sheets["Observations"][1]
    assert row == ["obs_1", "1000000", "superseded"]  # raw_value untouched


def test_transition_status_rejects_illegal_transition(sheets_writer, fake_service):
    fake_service.add_sheet("Observations", ["record_id", "status"])
    fake_service.sheets["Observations"].append(["obs_1", "superseded"])

    with pytest.raises(InvalidStatusTransition):
        sheets_writer.transition_status(
            "Observations",
            "obs_1",
            RecordStatus.ACTIVE,
            actor="tester",
            current_status=RecordStatus.SUPERSEDED,
        )
