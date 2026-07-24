"""Unit tests for the UKGC HTML/XLSX importer (T055)."""

from __future__ import annotations

from pathlib import Path

from casino_intel.parsing.ukgc_importer import extract_ukgc_xlsx

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "ukgc_business_data.xlsx"


def test_extract_ukgc_xlsx_maps_known_rows_and_skips_unknown_ones():
    records = extract_ukgc_xlsx(
        FIXTURE_PATH.read_bytes(),
        source_id="source_1",
        subject_id="market_gb",
        period_start="2025-01-01",
        period_end="2025-12-31",
    )
    metric_ids = {r.metric_id for r in records}
    assert metric_ids == {
        "market_ggy",
        "market_active_accounts",
        "market_bets_or_spins",
        "market_average_session_minutes",
    }
    # The "Some unrecognised future statistic" row is skipped, not guessed.
    assert len(records) == 4
    for record in records:
        assert record.subject.type == "market"
        assert record.review_status == "unreviewed"
        assert record.evidence_type == "reported_primary"
        assert record.verbatim_excerpt
