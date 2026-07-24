"""UKGC HTML/XLSX importer (source doc §10.2/§10.4): annual industry
statistics, market overview, gambling business data.

Maps known UKGC published-statistics row labels onto the market-level
metric registry (`market_ggy`, `market_active_accounts`, ...). An
unrecognised row label is skipped, not guessed — it simply doesn't become
a candidate fact, leaving a visible research gap rather than a speculative
`metric_id`.
"""

from __future__ import annotations

import pandas as pd

from casino_intel.extraction.extractor import make_extraction_record
from casino_intel.extraction.schema import ExtractionRecord
from casino_intel.parsing.tabular_parser import parse_xlsx

#: UKGC published-statistics row label (lower-cased) -> metric registry id.
METRIC_LABEL_MAP: dict[str, str] = {
    "gross gambling yield": "market_ggy",
    "gross gaming yield": "market_ggy",
    "gross gambling revenue": "market_ggr",
    "number of active accounts": "market_active_accounts",
    "active accounts": "market_active_accounts",
    "number of bets or spins": "market_bets_or_spins",
    "bets or spins": "market_bets_or_spins",
    "number of sessions": "market_sessions",
    "average session length (minutes)": "market_average_session_minutes",
    "sessions lasting longer than one hour": "market_sessions_over_one_hour",
}


def extract_ukgc_statistics(
    table: pd.DataFrame,
    *,
    source_id: str,
    subject_id: str,
    period_start: str,
    period_end: str,
    geography: str = "GB",
    metric_column: str = "Metric",
    value_column: str = "Value",
    unit_column: str | None = "Unit",
) -> list[ExtractionRecord]:
    """Map a parsed UKGC statistics table (one row per published metric)
    onto `ExtractionRecord` candidates against `subject_id` (a `market`
    subject, per data-model.md `SubjectType.MARKET`)."""
    records: list[ExtractionRecord] = []
    for row_number, row in table.iterrows():
        label = str(row.get(metric_column, "")).strip().lower()
        metric_id = METRIC_LABEL_MAP.get(label)
        if metric_id is None:
            continue

        raw_value = str(row.get(value_column, "")).strip()
        if not raw_value or raw_value.lower() == "nan":
            continue

        raw_unit = ""
        if unit_column:
            raw_unit_value = row.get(unit_column, "")
            raw_unit = "" if pd.isna(raw_unit_value) else str(raw_unit_value).strip()

        records.append(
            make_extraction_record(
                subject_type="market",
                subject_id=subject_id,
                metric_id=metric_id,
                raw_value=raw_value,
                raw_unit=raw_unit,
                source_id=source_id,
                source_locator=f"row {row_number + 2}, column {value_column!r}",
                evidence_type="reported_primary",
                confidence="high",
                verbatim_excerpt=f"{row.get(metric_column, '')}: {raw_value}",
                period_start=period_start,
                period_end=period_end,
                geography=geography,
            )
        )
    return records


def extract_ukgc_xlsx(
    content: bytes,
    *,
    source_id: str,
    subject_id: str,
    period_start: str,
    period_end: str,
    sheet_name: str | int = 0,
    geography: str = "GB",
) -> list[ExtractionRecord]:
    """`extract_fn` entry point for `IngestionRun`/`import-file`: parse a
    UKGC statistics XLSX export and return its candidate facts."""
    table = parse_xlsx(content, sheet_name=sheet_name)
    if isinstance(table, dict):
        table = next(iter(table.values()))
    return extract_ukgc_statistics(
        table,
        source_id=source_id,
        subject_id=subject_id,
        period_start=period_start,
        period_end=period_end,
        geography=geography,
    )
