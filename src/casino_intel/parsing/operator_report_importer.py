"""Operator annual-report PDF importer (source doc §10.4): scans extracted
report text for a fixed set of KPI search terms (active customers, GGR/NGR/
GGY, marketing/S&M expense, CPA, retention/churn, ARPU, bonuses, affiliate)
and emits a candidate fact for each term with a nearby number, each tagged
`evidence_type=reported_primary` (an operator citing its own figures) and a
page-number source locator.

A search term with no number found nearby in the surrounding text is
skipped rather than guessed (`extraction.extractor.find_kpi_mentions`).
"""

from __future__ import annotations

from casino_intel.extraction.extractor import find_kpi_mentions, make_extraction_record
from casino_intel.extraction.schema import ExtractionRecord
from casino_intel.parsing.pdf_parser import PdfParseResult, parse_pdf

#: KPI search term (source doc §10.4) -> metric registry id.
KPI_SEARCH_TERMS: dict[str, str] = {
    "active_customers": "active customers",
    "ggr": "gross gaming revenue",
    "ngr": "net gaming revenue",
    "ggy": "gross gaming yield",
    "marketing_expense": "marketing expense",
    "sales_and_marketing_expense": "sales and marketing expense",
    "affiliate_expense": "affiliate expense",
    "customer_retention_rate": "retention rate",
    "churn_rate": "churn rate",
    "bonuses_and_promotions_expense": "bonuses and promotions",
    "average_deposit": "average revenue per user",
}


def extract_operator_report_kpis(
    parsed: PdfParseResult,
    *,
    source_id: str,
    subject_id: str,
    period_start: str,
    period_end: str,
    search_terms: dict[str, str] | None = None,
) -> list[ExtractionRecord]:
    """Scan every page of a parsed operator annual-report PDF for the KPI
    search terms, returning one candidate fact per term/page match."""
    search_terms = search_terms if search_terms is not None else KPI_SEARCH_TERMS
    records: list[ExtractionRecord] = []
    seen_metric_ids: set[str] = set()

    for page_number, page_text in enumerate(parsed.page_texts, start=1):
        for match in find_kpi_mentions(page_text, search_terms, page_label=f"page {page_number}"):
            if match.metric_id in seen_metric_ids:
                continue  # first mention per report is the candidate; avoid duplicate noise
            seen_metric_ids.add(match.metric_id)
            records.append(
                make_extraction_record(
                    subject_type="operator",
                    subject_id=subject_id,
                    metric_id=match.metric_id,
                    raw_value=match.raw_value,
                    source_id=source_id,
                    source_locator=match.locator,
                    evidence_type="reported_primary",
                    confidence="medium",
                    verbatim_excerpt=match.excerpt,
                    period_start=period_start,
                    period_end=period_end,
                )
            )
    return records


def extract_operator_report_pdf(
    content: bytes,
    *,
    source_id: str,
    subject_id: str,
    period_start: str,
    period_end: str,
    search_terms: dict[str, str] | None = None,
) -> list[ExtractionRecord]:
    """`extract_fn` entry point for `IngestionRun`/`import-file`."""
    parsed = parse_pdf(content)
    return extract_operator_report_kpis(
        parsed,
        source_id=source_id,
        subject_id=subject_id,
        period_start=period_start,
        period_end=period_end,
        search_terms=search_terms,
    )
