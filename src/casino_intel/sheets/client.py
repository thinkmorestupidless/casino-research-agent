"""Thin wrapper over the Sheets API v4 (research.md decision #2).

All reads/writes go through batch calls (`values.batchGet`/`batchUpdate`),
never cell-by-cell (source doc §17.1), and retry with exponential backoff on
quota/transient errors (source doc §17.1). The underlying `service` object is
injectable so the rest of the codebase can be unit-tested without live
Google API access.
"""

from __future__ import annotations

import os
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

#: HTTP statuses worth retrying: rate limiting and transient server errors.
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, HttpError) and getattr(exc, "status_code", None) in _RETRYABLE_STATUSES


def build_credentials(credentials_path: str | None = None):
    """Load service-account credentials from ``credentials_path`` or the
    ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable (spec FR-050)."""
    path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path:
        raise RuntimeError(
            "No credentials configured — set GOOGLE_APPLICATION_CREDENTIALS "
            "(see .env.example). Credentials are never accepted as CLI arguments."
        )
    return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)


class SheetsClient:
    """Batch-oriented, retrying wrapper over the Sheets API v4."""

    def __init__(self, spreadsheet_id: str, service: Resource | None = None) -> None:
        self.spreadsheet_id = spreadsheet_id
        self._service = service or build("sheets", "v4", credentials=build_credentials())

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def batch_get_values(self, ranges: list[str]) -> dict[str, list[list[Any]]]:
        """Read one or more A1 ranges in a single API call."""
        response = (
            self._service.spreadsheets()
            .values()
            .batchGet(spreadsheetId=self.spreadsheet_id, ranges=ranges)
            .execute()
        )
        result: dict[str, list[list[Any]]] = {}
        for value_range in response.get("valueRanges", []):
            result[value_range["range"]] = value_range.get("values", [])
        return result

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def batch_update_values(
        self, data: list[dict[str, Any]], value_input_option: str = "RAW"
    ) -> dict[str, Any]:
        """Write one or more ranges in a single, all-or-nothing API call.

        ``data`` is a list of ``{"range": "Sheet!A1", "values": [[...]]}``.
        ``value_input_option`` defaults to RAW (literal text, no formula
        evaluation) — see sheets/safety.py for why this matters.
        """
        body = {"valueInputOption": value_input_option, "data": data}
        return (
            self._service.spreadsheets()
            .values()
            .batchUpdate(spreadsheetId=self.spreadsheet_id, body=body)
            .execute()
        )

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def append_rows(
        self, sheet_name: str, rows: list[list[Any]], value_input_option: str = "RAW"
    ) -> dict[str, Any]:
        """Append rows to the end of ``sheet_name`` in a single API call."""
        body = {"values": rows}
        return (
            self._service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption=value_input_option,
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def batch_update_spreadsheet(self, requests: list[dict[str, Any]]) -> dict[str, Any]:
        """Run structural/formatting requests (add sheet, format, validation,
        named ranges, protected ranges, conditional formatting) in one call."""
        return (
            self._service.spreadsheets()
            .batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests})
            .execute()
        )

    def get_sheets_metadata(self) -> list[dict[str, Any]]:
        """Return `{"title": ..., "sheetId": ...}` for every tab."""
        meta = self._service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        return [
            {"title": sheet["properties"]["title"], "sheetId": sheet["properties"]["sheetId"]}
            for sheet in meta.get("sheets", [])
        ]

    def get_sheet_titles(self) -> list[str]:
        """List the titles of all tabs currently in the spreadsheet."""
        return [sheet["title"] for sheet in self.get_sheets_metadata()]
