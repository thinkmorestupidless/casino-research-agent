"""Date/percentage/number/unit normalisation helpers (source doc §11.1).

Each function raises `ValueError` on unparseable input rather than
guessing — callers (the extractor, T049) catch this and route the
candidate fact to Data Quality instead of writing a fabricated value.
"""

from __future__ import annotations

import re
from datetime import date, datetime

_THOUSANDS_SEP = re.compile(r"[,\s]")
_PERCENT_SUFFIX = re.compile(r"\s*%$")
_MAGNITUDE_SUFFIXES = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
}
_MAGNITUDE_PATTERN = re.compile(r"^([\d.,]+)\s*(k|thousand|m|million|bn|billion)$", re.IGNORECASE)


def parse_number(raw: str) -> float:
    """Parse a human-formatted number, e.g. '4.2 million', '1,200,000', '3.5%'."""
    text = raw.strip()
    text = _PERCENT_SUFFIX.sub("", text)
    if match := _MAGNITUDE_PATTERN.match(text):
        number_part, suffix = match.groups()
        base = float(_THOUSANDS_SEP.sub("", number_part))
        return base * _MAGNITUDE_SUFFIXES[suffix.lower()]
    cleaned = _THOUSANDS_SEP.sub("", text)
    return float(cleaned)


def parse_percentage(raw: str) -> float:
    """Parse a percentage string into a 0-100 float, validating the range
    (spec FR-020 `percentage_outside_0_100`)."""
    value = parse_number(raw)
    if not 0 <= value <= 100:
        raise ValueError(f"Percentage {value} is outside the valid 0-100 range")
    return value


_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %Y",
    "%b %Y",
    "%Y",
]


def parse_date(raw: str) -> date:
    """Parse a date in one of several common report formats into ISO date.

    Formats lacking a day (e.g. "March 2026") resolve to the 1st of that
    month/year — callers should treat such values as approximate.
    """
    text = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%Y":
            return date(parsed.year, 1, 1)
        return parsed.date()
    raise ValueError(f"Unrecognised date format: {raw!r}")


def parse_boolean(raw: str) -> bool:
    normalised = raw.strip().lower()
    if normalised in {"true", "yes", "y", "1"}:
        return True
    if normalised in {"false", "no", "n", "0"}:
        return False
    raise ValueError(f"Unrecognised boolean value: {raw!r}")
