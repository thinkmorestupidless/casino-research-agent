"""Workbook schema bootstrap: create/verify all 23 tabs, headers, frozen
header rows, and confidence/quality conditional formatting
(spec FR-041, source doc §5/§17.1).

Idempotent by design (contracts/cli-commands.md `initialise-workbook`):
re-running only adds missing tabs/headers, never duplicates a tab or
touches existing data rows. Named ranges and data-validation dropdowns for
controlled vocabularies are created by `config_loader.py`, once the `Config`
sheet's content (and therefore the ranges to name) is known.
"""

from __future__ import annotations

from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.schema_definitions import SHEET_HEADERS, TAB_NAMES

#: Columns whose values should get confidence/quality colour-coding, per tab.
_CONFIDENCE_COLUMNS = {
    "Observations": "confidence",
    "Data Quality": "severity",
}

_CONFIDENCE_COLORS = {
    "high": {"red": 0.79, "green": 0.94, "blue": 0.80},  # green
    "medium": {"red": 1.0, "green": 0.95, "blue": 0.70},  # yellow
    "low": {"red": 1.0, "green": 0.80, "blue": 0.80},  # red
    "critical": {"red": 0.93, "green": 0.60, "blue": 0.60},  # dark red
}


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def ensure_tabs_and_headers(client: SheetsClient, dry_run: bool = False) -> list[str]:
    """Create any missing tabs (with headers, frozen header row) and write
    headers for any existing-but-empty tabs. Returns the list of tab names
    that would be (or were) newly created. Never touches a tab that already
    has data. In `dry_run` mode, only reads current state — no writes occur.
    """
    existing = set(client.get_sheet_titles())
    to_create = [name for name in TAB_NAMES if name not in existing]

    if dry_run:
        return to_create

    if to_create:
        requests = [{"addSheet": {"properties": {"title": name}}} for name in to_create]
        client.batch_update_spreadsheet(requests)

    # Write headers for every tab whose first row is currently empty
    # (freshly created tabs, or a pre-existing but never-initialised tab).
    header_writes = []
    freeze_requests = []
    sheet_ids = _sheet_id_map(client)
    current_headers = client.batch_get_values([f"{name}!1:1" for name in TAB_NAMES])
    for name in TAB_NAMES:
        existing_header = current_headers.get(f"{name}!1:1", [])
        if not existing_header or not existing_header[0]:
            header_writes.append({"range": f"{name}!A1", "values": [SHEET_HEADERS[name]]})
        freeze_requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_ids[name],
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )

    if header_writes:
        client.batch_update_values(header_writes, value_input_option="RAW")
    if freeze_requests:
        client.batch_update_spreadsheet(freeze_requests)

    return to_create


def _sheet_id_map(client: SheetsClient) -> dict[str, int]:
    return {sheet["title"]: sheet["sheetId"] for sheet in client.get_sheets_metadata()}


def apply_confidence_conditional_formatting(client: SheetsClient) -> None:
    """Apply colour-coded conditional formatting to the confidence/severity
    columns on the tabs listed in `_CONFIDENCE_COLUMNS` (source doc §17.1)."""
    sheet_ids = _sheet_id_map(client)
    requests = []
    for tab_name, column_name in _CONFIDENCE_COLUMNS.items():
        if tab_name not in sheet_ids:
            continue
        col_index = SHEET_HEADERS[tab_name].index(column_name)
        for value, color in _CONFIDENCE_COLORS.items():
            requests.append(
                {
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [
                                {
                                    "sheetId": sheet_ids[tab_name],
                                    "startRowIndex": 1,
                                    "startColumnIndex": col_index,
                                    "endColumnIndex": col_index + 1,
                                }
                            ],
                            "booleanRule": {
                                "condition": {
                                    "type": "TEXT_EQ",
                                    "values": [{"userEnteredValue": value}],
                                },
                                "format": {"backgroundColor": color},
                            },
                        },
                        "index": 0,
                    }
                }
            )
    if requests:
        client.batch_update_spreadsheet(requests)
