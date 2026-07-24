"""Wires currency/date/percentage/unit normalisation (`normalisation.currency`,
`normalisation.units`) into the extraction pipeline's output, between
extraction (T049) and ingestion-time validation (T051).

Unparseable values are left un-normalised rather than guessed — the
ingestion validator then routes the resulting gap (e.g. missing
`normalised_numeric_value`) to Data Quality instead of silently accepting
or fabricating a figure.
"""

from __future__ import annotations

from casino_intel.extraction.schema import ExtractionRecord
from casino_intel.normalisation.currency import FxRateProvider, normalise_currency
from casino_intel.normalisation.units import parse_date, parse_number, parse_percentage


def normalise_extraction_record(
    record: ExtractionRecord,
    *,
    target_currency: str = "GBP",
    fx_provider: FxRateProvider | None = None,
    is_percentage: bool = False,
) -> ExtractionRecord:
    """Return a copy of `record` with `normalised_numeric_value`,
    `normalised_currency`, `fx_rate`, `fx_rate_date` and a normalised
    `as_of_date` populated wherever they can be derived."""
    updates: dict[str, object] = {}

    numeric_value = record.normalised_numeric_value
    if numeric_value is None:
        try:
            numeric_value = (
                parse_percentage(record.raw_value)
                if is_percentage
                else parse_number(record.raw_value)
            )
            updates["normalised_numeric_value"] = numeric_value
        except ValueError:
            numeric_value = None

    if numeric_value is not None and record.currency and record.currency != target_currency:
        kwargs = {"provider": fx_provider} if fx_provider else {}
        try:
            converted = normalise_currency(
                numeric_value,
                record.currency,
                target_currency,
                as_of_date=record.as_of_date or "",
                **kwargs,
            )
            updates["normalised_numeric_value"] = converted.normalised_value
            updates["normalised_currency"] = converted.normalised_currency
            updates["fx_rate"] = converted.fx_rate
            updates["fx_rate_date"] = converted.fx_rate_date
        except KeyError:
            # Unsupported currency pair: leave un-normalised so
            # rules_ingestion.py's `unsupported_currency` check can flag it.
            pass

    if record.as_of_date:
        try:
            updates["as_of_date"] = parse_date(record.as_of_date).isoformat()
        except ValueError:
            pass

    if not updates:
        return record
    return record.model_copy(update=updates)
