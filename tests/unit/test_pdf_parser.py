"""Unit tests for the PDF parser (T047)."""

from __future__ import annotations

from pathlib import Path

from casino_intel.parsing.pdf_parser import parse_pdf

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "operator_annual_report_excerpt.pdf"


def test_parse_pdf_extracts_text_per_page():
    result = parse_pdf(FIXTURE_PATH.read_bytes())
    assert result.page_count == 2
    assert len(result.page_texts) == 2
    assert "Active customers" in result.full_text
    assert "Financial review" in result.page_texts[1]
