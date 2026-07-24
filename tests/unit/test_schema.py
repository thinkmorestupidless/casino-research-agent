from casino_intel.sheets.schema import (
    apply_confidence_conditional_formatting,
    ensure_tabs_and_headers,
)
from casino_intel.sheets.schema_definitions import SHEET_HEADERS, TAB_NAMES


def test_ensure_tabs_and_headers_creates_all_missing_tabs(sheets_client, fake_service):
    created = ensure_tabs_and_headers(sheets_client)
    assert set(created) == set(TAB_NAMES)
    assert set(fake_service.sheets.keys()) == set(TAB_NAMES)


def test_ensure_tabs_and_headers_writes_correct_header_row(sheets_client, fake_service):
    ensure_tabs_and_headers(sheets_client)
    assert fake_service.sheets["Brands"][0] == SHEET_HEADERS["Brands"]
    assert fake_service.sheets["Observations"][0] == SHEET_HEADERS["Observations"]


def test_ensure_tabs_and_headers_is_idempotent_and_never_touches_data(sheets_client, fake_service):
    ensure_tabs_and_headers(sheets_client)
    fake_service.sheets["Brands"].append(
        ["brand_1", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "Example Casino"]
        + [""] * 11
    )
    row_count_before = len(fake_service.sheets["Brands"])

    created_again = ensure_tabs_and_headers(sheets_client)

    assert created_again == []  # nothing new created second time
    assert len(fake_service.sheets["Brands"]) == row_count_before  # data row untouched
    assert fake_service.sheets["Brands"][0] == SHEET_HEADERS["Brands"]  # header still correct


def test_apply_confidence_conditional_formatting_does_not_raise(sheets_client, fake_service):
    ensure_tabs_and_headers(sheets_client)
    apply_confidence_conditional_formatting(sheets_client)  # should complete without error
