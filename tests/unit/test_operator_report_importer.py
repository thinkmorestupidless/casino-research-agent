"""Unit tests for the operator annual-report PDF importer (T056)."""

from __future__ import annotations

from pathlib import Path

from casino_intel.parsing.operator_report_importer import extract_operator_report_pdf

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "operator_annual_report_excerpt.pdf"


def test_extract_operator_report_pdf_finds_kpis_with_page_locators_and_excerpts():
    records = extract_operator_report_pdf(
        FIXTURE_PATH.read_bytes(),
        source_id="source_1",
        subject_id="operator_1",
        period_start="2025-01-01",
        period_end="2025-12-31",
    )
    by_metric = {r.metric_id: r for r in records}

    assert by_metric["active_customers"].raw_value == "1.2 million"
    assert by_metric["ggr"].raw_value == "£450 million"
    assert by_metric["affiliate_expense"].raw_value == "£22 million"

    for record in records:
        assert record.subject.type == "operator"
        assert record.review_status == "unreviewed"
        assert record.source_locator.startswith("page ")
        assert record.verbatim_excerpt


def test_extract_operator_report_pdf_omits_terms_with_no_nearby_number():
    records = extract_operator_report_pdf(
        FIXTURE_PATH.read_bytes(),
        source_id="source_1",
        subject_id="operator_1",
        period_start="2025-01-01",
        period_end="2025-12-31",
        search_terms={"average_deposit": "average revenue per user"},
    )
    # The fixture never mentions ARPU — must not fabricate a value.
    assert records == []
