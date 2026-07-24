"""Unit tests for the CSV/XLSX parser (T048)."""

from __future__ import annotations

from pathlib import Path

from casino_intel.parsing.tabular_parser import parse_csv, parse_xlsx

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_csv_reads_traffic_export():
    df = parse_csv((FIXTURES / "traffic_export.csv").read_bytes())
    assert list(df["brand_id"]) == ["brand_example001", "brand_example002"]


def test_parse_xlsx_reads_ukgc_statistics():
    df = parse_xlsx((FIXTURES / "ukgc_business_data.xlsx").read_bytes())
    assert "Metric" in df.columns
    assert "Gross gambling yield" in df["Metric"].tolist()
