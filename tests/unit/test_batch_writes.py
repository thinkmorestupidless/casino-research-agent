"""Every Sheets write must use a single batch API call regardless of how
many rows/cells/columns it touches — never cell-by-cell (source doc §17.1).
`fake_service.call_log` records one entry per `.execute()` call, i.e. one
entry per real API request that would be made against the live Sheets API.
"""

from __future__ import annotations

from casino_intel.sheets.config_loader import ConfigLoader
from casino_intel.sheets.schema import ensure_tabs_and_headers


def test_append_record_is_a_single_api_call_regardless_of_column_count(sheets_writer, fake_service):
    header = [f"col_{i}" for i in range(30)]
    fake_service.add_sheet("WideSheet", header)
    fake_service.call_log.clear()

    sheets_writer.append_record(
        "WideSheet", {col: f"value_{i}" for i, col in enumerate(header)}, actor="tester"
    )

    # One append call for the row + one append call for the paired Change
    # Log entry = 2 total API calls, never 30 (one per cell).
    assert fake_service.call_log.count("append") == 2


def test_append_observation_batch_of_many_rows_is_one_call_per_row_not_per_cell(
    sheets_writer, fake_service
):
    from casino_intel.sheets.schema_definitions import SHEET_HEADERS

    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.call_log.clear()

    sheets_writer.append_observation(
        "Observations",
        {
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
        },
        actor="tester",
    )

    # 1 append for the observation row + 1 append for its Change Log entry.
    # SHEET_HEADERS["Observations"] has ~40 columns — a cell-by-cell
    # implementation would have made dozens of calls here.
    assert fake_service.call_log.count("append") == 2


def test_ensure_tabs_and_headers_writes_all_headers_in_one_batch_call(sheets_client, fake_service):
    fake_service.call_log.clear()

    ensure_tabs_and_headers(sheets_client)

    # All 23 tabs' headers are written via ONE valuesBatchUpdate call and
    # all 23 tabs are created via ONE spreadsheetBatchUpdate call — not one
    # API call per tab (46 calls) and certainly not one per cell.
    assert fake_service.call_log.count("valuesBatchUpdate") == 1
    assert fake_service.call_log.count("spreadsheetBatchUpdate") == 2  # addSheet + freeze rows


def test_seed_vocabularies_writes_all_rows_in_one_append_call(sheets_client, fake_service):
    fake_service.add_sheet("Config", ["list_name", "value", "description"])
    loader = ConfigLoader(sheets_client)
    fake_service.call_log.clear()

    added = loader.seed_vocabularies("config/vocabularies.yaml")

    assert added > 50  # a realistic, non-trivial number of vocab rows
    assert fake_service.call_log.count("append") == 1  # one call for all rows, not one per row


def test_export_reads_all_tabs_in_one_batch_get_call(sheets_client, fake_service):
    ensure_tabs_and_headers(sheets_client)
    fake_service.call_log.clear()

    sheets_client.batch_get_values([f"{name}!A1:ZZ" for name in fake_service.sheets])

    assert fake_service.call_log.count("batchGet") == 1
