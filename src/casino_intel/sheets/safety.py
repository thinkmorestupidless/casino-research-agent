"""Formula-injection protection (spec FR-042, source doc §17.1, contracts/observation-write-contract.md §3).

Any text value written to a cell that begins with ``=``, ``+``, ``-`` or
``@`` is a potential spreadsheet formula. Google Sheets treats a leading
apostrophe as "force literal text", which is the simplest reliable way to
neutralise this across both the Sheets UI and API-written values regardless
of ``valueInputOption``. This is applied centrally in the write path (T016)
so no caller can bypass it — never left to individual extractors/importers.
"""

from __future__ import annotations

from typing import Any

_DANGEROUS_LEADING_CHARS = ("=", "+", "-", "@")


def escape_cell_value(value: Any) -> Any:
    """Neutralise a value that would otherwise be interpreted as a formula.

    Non-string values pass through unchanged. A string starting with one of
    the dangerous characters is prefixed with a literal apostrophe.
    """
    if isinstance(value, str) and value.startswith(_DANGEROUS_LEADING_CHARS):
        return f"'{value}"
    return value


def escape_row(row: list[Any]) -> list[Any]:
    """Apply :func:`escape_cell_value` to every cell in a row."""
    return [escape_cell_value(cell) for cell in row]


def escape_rows(rows: list[list[Any]]) -> list[list[Any]]:
    """Apply :func:`escape_row` to every row in a batch."""
    return [escape_row(row) for row in rows]
