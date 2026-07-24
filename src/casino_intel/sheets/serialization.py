"""Convert a Pydantic `model_dump(mode="json")` dict into sheet-cell-safe
values (lists -> comma-joined strings, None -> "", everything else passes
through as the JSON-mode dump already produces strings/numbers/bools for
datetimes and enums)."""

from __future__ import annotations

from typing import Any


def flatten_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return value


def to_sheet_record(dumped: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    """Project a model's JSON-mode dump onto `columns`, flattening values."""
    return {col: flatten_value(dumped.get(col, "")) for col in columns}
