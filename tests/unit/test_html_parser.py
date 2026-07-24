"""Unit tests for the HTML parser (T046)."""

from __future__ import annotations

from pathlib import Path

from casino_intel.parsing.html_parser import find_elements, parse_html

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "promotion_terms.html"


def test_parse_html_extracts_text_and_tables():
    result = parse_html(FIXTURE_PATH.read_bytes())
    assert "Full Promotion Terms" in result.text
    assert len(result.tables) == 1
    assert "Field" in result.tables[0].columns.tolist() or "Field" in result.text


def test_find_elements_returns_matching_element_text():
    result = parse_html(FIXTURE_PATH.read_bytes())
    values = find_elements(result, ".offer-minimum-deposit")
    assert values == ["10"]
