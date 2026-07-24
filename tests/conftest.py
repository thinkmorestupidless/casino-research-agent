"""Shared test fixtures: a minimal in-memory fake of the Sheets API v4
surface used by `casino_intel.sheets.client.SheetsClient`, so the write
layer, dedup, and CLI commands can be unit-tested without live Google
credentials (see research.md decision #13 / plan.md testing strategy)."""

from __future__ import annotations

import re

import pytest

from casino_intel.cache.fingerprint_store import FingerprintStore
from casino_intel.sheets.change_log import ChangeLogWriter
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.writer import SheetsWriter

_CELL_RANGE = re.compile(r"^(?P<sheet>[^!]+)!(?P<col>[A-Z]+)(?P<row>\d+)$")
_COL_RANGE = re.compile(r"^(?P<sheet>[^!]+)!(?P<col>[A-Z]+)(?P<row>\d+):(?P<col2>[A-Z]+)?$")
_ROW_RANGE = re.compile(r"^(?P<sheet>[^!]+)!(?P<row>\d+):(?P<row2>\d+)$")


def _col_index(letters: str) -> int:
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - 64)
    return index - 1


class FakeSheetsService:
    """A tiny in-memory stand-in for the googleapiclient Sheets resource.

    Each sheet is a list of rows (row 0 = header), each row a list of str.
    Only the range shapes actually used by this codebase are supported.
    """

    def __init__(self) -> None:
        self.sheets: dict[str, list[list[str]]] = {}
        #: One entry per `.execute()` call — each corresponds to exactly one
        #: real Sheets API HTTP request. Used to assert batch usage (never
        #: cell-by-cell) per source doc §17.1 / tasks.md T102.
        self.call_log: list[str] = []

    def add_sheet(self, name: str, header: list[str]) -> None:
        self.sheets[name] = [header]

    # -- chainable API surface -----------------------------------------------------

    def spreadsheets(self) -> FakeSheetsService:
        return self

    def values(self) -> FakeSheetsService:
        return self

    def batchGet(self, spreadsheetId: str, ranges: list[str]) -> FakeSheetsService:
        self._pending = ("batchGet", ranges)
        return self

    def batchUpdate(self, spreadsheetId: str, body: dict) -> FakeSheetsService:
        if "data" in body:
            self._pending = ("valuesBatchUpdate", body)
        else:
            self._pending = ("spreadsheetBatchUpdate", body)
        return self

    def append(
        self,
        spreadsheetId: str,
        range: str,
        valueInputOption: str,
        insertDataOption: str,
        body: dict,
    ) -> FakeSheetsService:
        self._pending = ("append", range, body)
        return self

    def get(self, spreadsheetId: str) -> FakeSheetsService:
        self._pending = ("get",)
        return self

    def execute(self) -> dict:
        kind, *rest = self._pending
        self.call_log.append(kind)
        if kind == "batchGet":
            (ranges,) = rest
            value_ranges = []
            for r in ranges:
                # The real Sheets API echoes a NORMALISED range (adds column/
                # row bounds, quotes tab names with spaces) that rarely equals
                # the requested string. Emulate that so the client is forced to
                # key results by the requested range, not the response range.
                value_ranges.append(
                    {"range": self._normalise_range(r), "values": self._read_range(r)}
                )
            return {"valueRanges": value_ranges}
        if kind == "valuesBatchUpdate":
            (body,) = rest
            for item in body["data"]:
                self._write_range(item["range"], item["values"])
            return {}
        if kind == "append":
            range_, body = rest
            sheet_name = range_.split("!")[0]
            self.sheets.setdefault(sheet_name, [[]])
            self.sheets[sheet_name].extend(body["values"])
            return {}
        if kind == "get":
            return {
                "sheets": [
                    {"properties": {"title": name, "sheetId": idx}}
                    for idx, name in enumerate(self.sheets)
                ]
            }
        if kind == "spreadsheetBatchUpdate":
            (body,) = rest
            for req in body["requests"]:
                if "addSheet" in req:
                    title = req["addSheet"]["properties"]["title"]
                    self.sheets.setdefault(title, [[]])
            return {}
        raise NotImplementedError(kind)

    # -- tiny A1-range engine --------------------------------------------------------

    @staticmethod
    def _normalise_range(r: str) -> str:
        """Mimic the Sheets API's range normalisation: quote tab names that
        contain spaces and append a synthetic bound, so the echoed range does
        not string-equal the requested one."""
        sheet, _, a1 = r.partition("!")
        if " " in sheet:
            sheet = f"'{sheet}'"
        return f"{sheet}!{a1}:ZZ999"

    def _read_range(self, r: str) -> list[list[str]]:
        if m := _CELL_RANGE.match(r):
            sheet, col, row = m["sheet"], m["col"], int(m["row"])
            rows = self.sheets.get(sheet, [])
            idx = row - 1
            col_idx = _col_index(col)
            if idx < len(rows) and col_idx < len(rows[idx]):
                return [[rows[idx][col_idx]]]
            return [[]]
        if m := _ROW_RANGE.match(r):
            sheet, row = m["sheet"], int(m["row"])
            rows = self.sheets.get(sheet, [])
            idx = row - 1
            return [rows[idx]] if idx < len(rows) else [[]]
        if m := _COL_RANGE.match(r):
            sheet, col, row, col2 = m["sheet"], m["col"], int(m["row"]), m["col2"]
            rows = self.sheets.get(sheet, [])
            col_start = _col_index(col)
            col_end = _col_index(col2) if col2 else col_start
            result = []
            for data_row in rows[row - 1 :]:
                result.append(
                    [
                        data_row[c] if c < len(data_row) else ""
                        for c in range(col_start, col_end + 1)
                    ]
                )
            return result
        raise NotImplementedError(f"Unsupported range shape: {r}")

    def _write_range(self, r: str, values: list[list[str]]) -> None:
        """Write `values` anchored at the range's top-left cell, expanding
        the sheet as needed — matching the real Sheets API's anchor-write
        semantics (the range need not span the full written area)."""
        m = _CELL_RANGE.match(r)
        if not m:
            raise NotImplementedError(f"Unsupported write range shape: {r}")
        sheet, col, row = m["sheet"], m["col"], int(m["row"])
        rows = self.sheets.setdefault(sheet, [])
        start_row = row - 1
        start_col = _col_index(col)
        for row_offset, value_row in enumerate(values):
            idx = start_row + row_offset
            while len(rows) <= idx:
                rows.append([])
            for col_offset, cell in enumerate(value_row):
                col_idx = start_col + col_offset
                while len(rows[idx]) <= col_idx:
                    rows[idx].append("")
                rows[idx][col_idx] = cell


@pytest.fixture
def fake_service() -> FakeSheetsService:
    return FakeSheetsService()


@pytest.fixture
def sheets_client(fake_service: FakeSheetsService) -> SheetsClient:
    return SheetsClient(spreadsheet_id="fake-spreadsheet", service=fake_service)


@pytest.fixture
def fingerprint_store() -> FingerprintStore:
    store = FingerprintStore(path=":memory:")
    yield store
    store.close()


@pytest.fixture
def change_log_writer(
    sheets_client: SheetsClient, fake_service: FakeSheetsService
) -> ChangeLogWriter:
    fake_service.add_sheet(
        "Change Log",
        [
            "change_id",
            "timestamp",
            "actor",
            "action",
            "sheet_name",
            "record_id",
            "field_name",
            "old_value",
            "new_value",
            "reason",
            "source_id",
            "ingestion_run_id",
        ],
    )
    return ChangeLogWriter(sheets_client)


@pytest.fixture
def sheets_writer(
    sheets_client: SheetsClient,
    fingerprint_store: FingerprintStore,
    change_log_writer: ChangeLogWriter,
) -> SheetsWriter:
    return SheetsWriter(sheets_client, fingerprint_store, change_log_writer)
