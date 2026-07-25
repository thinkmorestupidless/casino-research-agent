"""User Story 5 independent test (quickstart.md Step 9, spec Acceptance
Scenarios 1-3, SC-001/SC-008/SC-013): generate the comparative Summary
across brands with mixed data completeness and confirm:

1. every displayed figure carries a confidence/evidence marker;
2. an operator-level financial figure shown for a brand is explicitly
   labelled as operator-level, never presented as brand-specific;
3. a brand with no recent observation for some signal shows a visible gap
   flag rather than a blank/fabricated value.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.reporting.completeness import (
    ACTIVE_CUSTOMERS,
    BRAND_POSITIONING,
    FIGURE_LEVEL_OPERATOR,
    MARKETING_PCT_REVENUE,
    OPERATOR_REVENUE,
    REPUTATION_SCORE,
    REVENUE_PER_ACTIVE_CUSTOMER,
    SEARCH_INTEREST,
    TRAFFIC,
    UX_SCORE,
    WELCOME_OFFER,
    compute_all_brands,
)
from casino_intel.reporting.summary_generator import (
    NoBrandsRegisteredError,
    build_summary_row,
    refresh_summary_sheet,
)
from casino_intel.services.observation_service import ObservationInput, ObservationService
from casino_intel.services.registry_service import RegistryService
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation.data_quality import DataQualityWriter

runner = CliRunner()

NOW = datetime(2026, 7, 24, tzinfo=UTC)


@pytest.fixture
def metric_registry() -> MetricRegistry:
    return MetricRegistry("config/metrics.yaml")


@pytest.fixture(autouse=True)
def _seed_tabs(fake_service):
    for sheet_name in [
        "Operators",
        "Brands",
        "Sources",
        "Observations",
        "Derived Metrics",
        "Offers",
        "UX Audits",
        "Brand Audits",
        "Data Quality",
        "Summary",
    ]:
        fake_service.add_sheet(sheet_name, SHEET_HEADERS[sheet_name])


@pytest.fixture
def data_quality_writer(sheets_client):
    return DataQualityWriter(sheets_client)


@pytest.fixture
def observation_service(sheets_writer, data_quality_writer, metric_registry):
    return ObservationService(sheets_writer, data_quality_writer, metric_registry)


@pytest.fixture(autouse=True)
def _patch_sheets_client(monkeypatch, sheets_client):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", ":memory:")
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )


def _seed_two_brands(registry, observation_service, fake_service):
    """Brand A: comprehensive data across every tracked signal.
    Brand B: only a traffic estimate, plus an *operator-level-only*
    active-customer figure — deliberately no brand-level equivalent."""
    operator_a = registry.register_operator(
        {"operator_name": "Comprehensive Group plc", "ownership_type": "public"}, actor="tester"
    ).record_id
    operator_b = registry.register_operator(
        {"operator_name": "Minimal Group Ltd", "ownership_type": "private"}, actor="tester"
    ).record_id

    brand_a = registry.register_brand(
        {
            "brand_name": "Comprehensive Casino",
            "operator_id": operator_a,
            "primary_domain": "comprehensive-casino.example",
            "brand_type": "casino_only",
            "sampling_rationale": "Full-coverage fixture brand.",
        },
        actor="tester",
    ).record_id
    brand_b = registry.register_brand(
        {
            "brand_name": "Traffic Only Casino",
            "operator_id": operator_b,
            "primary_domain": "traffic-only-casino.example",
            "brand_type": "casino_only",
            "sampling_rationale": "Minimal-coverage fixture brand.",
        },
        actor="tester",
    ).record_id

    source_id = "source_fixture_1"

    def record(**kwargs):
        result = observation_service.record_observation(
            ObservationInput(source_id=source_id, **kwargs), actor="tester"
        )
        assert result is not None and result.written, kwargs
        return result

    # --- Brand A: comprehensive signals -------------------------------------------
    record(
        subject_type="brand",
        subject_id=brand_a,
        metric_id="estimated_monthly_visits",
        raw_value="1,500,000",
        evidence_type="third_party_estimate",
        confidence="medium",
        as_of_date="2026-07-01",
        captured_at="2026-07-01T00:00:00+00:00",
    )
    record(
        subject_type="brand",
        subject_id=brand_a,
        metric_id="branded_search_interest_index",
        raw_value="40",
        normalised_numeric_value=40,
        evidence_type="third_party_estimate",
        confidence="medium",
        as_of_date="2026-06-01",
        captured_at="2026-06-01T00:00:00+00:00",
    )
    record(
        subject_type="brand",
        subject_id=brand_a,
        metric_id="branded_search_interest_index",
        raw_value="55",
        normalised_numeric_value=55,
        evidence_type="third_party_estimate",
        confidence="medium",
        as_of_date="2026-07-01",
        captured_at="2026-07-01T00:00:00+00:00",
    )
    record(
        subject_type="operator",
        subject_id=operator_a,
        metric_id="revenue",
        raw_value="450000000",
        normalised_numeric_value=450_000_000,
        evidence_type="reported_primary",
        confidence="high",
        as_of_date="2026-06-30",
        captured_at="2026-06-30T00:00:00+00:00",
    )
    record(
        subject_type="brand",
        subject_id=brand_a,
        metric_id="active_customers",
        raw_value="120000",
        normalised_numeric_value=120000,
        evidence_type="reported_secondary",
        confidence="medium",
        as_of_date="2026-06-30",
        captured_at="2026-06-30T00:00:00+00:00",
    )
    record(
        subject_type="brand",
        subject_id=brand_a,
        metric_id="review_platform_score",
        raw_value="82",
        normalised_numeric_value=82,
        evidence_type="third_party_estimate",
        confidence="medium",
        as_of_date="2026-06-15",
        captured_at="2026-06-15T00:00:00+00:00",
    )

    fake_service.sheets["Derived Metrics"].append(
        [
            "derived_1",
            "brand",
            brand_a,
            "revenue_per_active_customer",
            "2026-06-01",
            "2026-06-30",
            "480.5",
            "gbp",
            "v1",
            "revenue / active_customers",
            "obs_1, obs_2",
            "",
            "medium",
            "comparable",
            "2026-07-01T00:00:00+00:00",
            "derivation_engine",
            "approved",
        ]
    )
    fake_service.sheets["Derived Metrics"].append(
        [
            "derived_2",
            "brand",
            brand_a,
            "marketing_pct_revenue",
            "2026-06-01",
            "2026-06-30",
            "18.2",
            "percent",
            "v1",
            "marketing_expense / revenue",
            "obs_3, obs_4",
            "",
            "high",
            "comparable",
            "2026-07-01T00:00:00+00:00",
            "derivation_engine",
            "approved",
        ]
    )

    offers_header = SHEET_HEADERS["Offers"]
    offer_row = {col: "" for col in offers_header}
    offer_row.update(
        {
            "record_id": "offer_1",
            "created_at": "2026-07-01T00:00:00+00:00",
            "created_by": "tester",
            "updated_at": "2026-07-01T00:00:00+00:00",
            "status": "active",
            "source_id": source_id,
            "evidence_type": "direct_observation",
            "confidence": "high",
            "review_status": "human_reviewed",
            "captured_at": "2026-07-01T00:00:00+00:00",
            "brand_id": brand_a,
            "geography": "GB",
            "customer_type": "new_customer",
            "offer_type": "welcome_bonus",
            "headline": "100% up to £200 + 50 free spins",
            "bonus_percentage": "100",
            "wagering_multiplier": "35",
        }
    )
    fake_service.sheets["Offers"].append([offer_row[col] for col in offers_header])

    ux_header = SHEET_HEADERS["UX Audits"]
    ux_row = {col: "" for col in ux_header}
    ux_row.update(
        {
            "record_id": "audit_ux_1",
            "created_at": "2026-07-01T00:00:00+00:00",
            "created_by": "tester",
            "updated_at": "2026-07-01T00:00:00+00:00",
            "status": "active",
            "source_id": source_id,
            "evidence_type": "subjective_audit",
            "confidence": "high",
            "review_status": "human_reviewed",
            "captured_at": "2026-07-01T00:00:00+00:00",
            "brand_id": brand_a,
            "audit_date": "2026-07-01",
            "auditor": "tester",
            "overall_ux_score": "4",
            "overall_ux_score_rationale": "Clear navigation, minor friction at deposit.",
        }
    )
    fake_service.sheets["UX Audits"].append([ux_row[col] for col in ux_header])

    brand_audit_header = SHEET_HEADERS["Brand Audits"]
    brand_audit_row = {col: "" for col in brand_audit_header}
    brand_audit_row.update(
        {
            "record_id": "audit_brand_1",
            "created_at": "2026-07-01T00:00:00+00:00",
            "created_by": "tester",
            "updated_at": "2026-07-01T00:00:00+00:00",
            "status": "active",
            "source_id": source_id,
            "evidence_type": "subjective_audit",
            "confidence": "high",
            "review_status": "human_reviewed",
            "captured_at": "2026-07-01T00:00:00+00:00",
            "brand_id": brand_a,
            "audit_date": "2026-07-01",
            "auditor": "tester",
            "premium_score": "4",
            "premium_score_rationale": "Polished visual system.",
            "playful_score": "2",
            "playful_score_rationale": "Restrained tone.",
            "trustworthy_score": "5",
            "trustworthy_score_rationale": "Prominent licensing info.",
            "brand_rationale": "Positions as a premium, trustworthy operator.",
        }
    )
    fake_service.sheets["Brand Audits"].append([brand_audit_row[col] for col in brand_audit_header])

    # --- Brand B: minimal data -------------------------------------------------------
    record(
        subject_type="brand",
        subject_id=brand_b,
        metric_id="estimated_monthly_visits",
        raw_value="80,000",
        evidence_type="third_party_estimate",
        confidence="low",
        as_of_date="2026-07-01",
        captured_at="2026-07-01T00:00:00+00:00",
    )
    # Active customers only ever reported at group/operator level for Brand B.
    record(
        subject_type="operator",
        subject_id=operator_b,
        metric_id="active_customers",
        raw_value="9000",
        normalised_numeric_value=9000,
        evidence_type="reported_primary",
        confidence="high",
        as_of_date="2026-06-30",
        captured_at="2026-06-30T00:00:00+00:00",
    )

    return brand_a, brand_b


def test_full_user_story_5_flow(fake_service, sheets_writer, sheets_client, observation_service):
    registry = RegistryService(sheets_writer)
    brand_a, brand_b = _seed_two_brands(registry, observation_service, fake_service)

    completions = compute_all_brands(sheets_client, now=NOW)
    by_id = {c.brand_id: c for c in completions}
    comp_a = by_id[brand_a]
    comp_b = by_id[brand_b]

    # --- Scenario 1: every populated figure carries confidence + evidence markers ---
    for label in [
        TRAFFIC,
        SEARCH_INTEREST,
        OPERATOR_REVENUE,
        ACTIVE_CUSTOMERS,
        REVENUE_PER_ACTIVE_CUSTOMER,
        MARKETING_PCT_REVENUE,
        WELCOME_OFFER,
        UX_SCORE,
        BRAND_POSITIONING,
        REPUTATION_SCORE,
    ]:
        sig = comp_a.signals[label]
        assert not sig.is_gap, f"expected brand A to have data for {label}"
        assert sig.confidence, f"{label} missing a confidence marker"
        assert sig.evidence_type, f"{label} missing an evidence-type marker"
        rendered = sig.display()
        assert "confidence=" in rendered
        assert "evidence=" in rendered

    # --- Scenario 2: operator-level figures are explicitly, visibly labelled -------
    # Brand A: revenue is only ever reported at operator level -> must be flagged.
    assert comp_a.signals[OPERATOR_REVENUE].figure_level == FIGURE_LEVEL_OPERATOR
    assert "[OPERATOR-LEVEL]" in comp_a.signals[OPERATOR_REVENUE].display()
    # Brand A does have its own brand-level active-customer figure -> not flagged.
    assert comp_a.signals[ACTIVE_CUSTOMERS].figure_level != FIGURE_LEVEL_OPERATOR

    # Brand B: active-customer figure only exists at operator/group level and must
    # be shown *as* an operator figure, never presented as brand-specific.
    active_signal_b = comp_b.signals[ACTIVE_CUSTOMERS]
    assert not active_signal_b.is_gap
    assert active_signal_b.figure_level == FIGURE_LEVEL_OPERATOR
    assert "[OPERATOR-LEVEL]" in active_signal_b.display()
    assert brand_b not in active_signal_b.display()  # sanity: no brand-id leakage into the label

    # The row-level note also surfaces this instead of hiding it.
    assert "latest_active_customer_figure" in comp_b.figure_level_note
    assert "operator-level" in comp_b.figure_level_note

    # --- Scenario 3: missing signals are visible gaps, never blank/fabricated ------
    for label in [
        SEARCH_INTEREST,
        REVENUE_PER_ACTIVE_CUSTOMER,
        MARKETING_PCT_REVENUE,
        WELCOME_OFFER,
        UX_SCORE,
        BRAND_POSITIONING,
        REPUTATION_SCORE,
    ]:
        sig = comp_b.signals[label]
        assert sig.is_gap, f"expected brand B to have a gap for {label}"
        assert sig.display() == "GAP: no data on record"

    assert any("missing" in gap for gap in comp_b.research_gaps)
    assert comp_b.pilot_coverage_status in {"partial", "no_data"}
    assert comp_a.pilot_coverage_status == "comprehensive"

    # --- Row building never leaves a populated-looking blank for a real gap --------
    row_b = build_summary_row(comp_b)
    header = SHEET_HEADERS["Summary"]
    row_b_dict = dict(zip(header, row_b, strict=False))
    assert row_b_dict["current_welcome_offer"] == "GAP: no data on record"
    assert row_b_dict["ux_score"] == "GAP: no data on record"
    assert "[OPERATOR-LEVEL]" in row_b_dict["latest_active_customer_figure"]
    assert "operator-level" in row_b_dict["figure_level_note"]

    # --- Full refresh writes one row per brand and is CLI-reachable -----------------
    completions_written = refresh_summary_sheet(sheets_client, now=NOW)
    assert len(completions_written) == 2
    summary_rows = fake_service.sheets["Summary"][1:]
    assert len(summary_rows) == 2
    written_brand_ids = {dict(zip(header, row, strict=False))["brand_id"] for row in summary_rows}
    assert written_brand_ids == {brand_a, brand_b}


def test_refresh_summary_regenerates_and_shrinks_cleanly(
    fake_service, sheets_client, sheets_writer, observation_service
):
    """A second, smaller run must not leave stale rows behind from a larger
    prior run (this sheet is regenerated wholesale, not appended to)."""
    registry = RegistryService(sheets_writer)
    _seed_two_brands(registry, observation_service, fake_service)
    refresh_summary_sheet(sheets_client, now=NOW)
    assert len(fake_service.sheets["Summary"]) == 3  # header + 2 brands

    # Reject one brand out from under the summary and re-run: the sheet must
    # shrink to match, not retain a stale leftover row.
    fake_service.sheets["Brands"][-1][SHEET_HEADERS["Brands"].index("status")] = "rejected"
    refresh_summary_sheet(sheets_client, now=NOW)
    remaining = [row for row in fake_service.sheets["Summary"][1:] if any(cell for cell in row)]
    assert len(remaining) == 1


def test_refresh_summary_cli_exits_10_when_no_brands(monkeypatch, sheets_client):
    result = runner.invoke(app, ["refresh-summary"])
    assert result.exit_code == 10, result.output


def test_refresh_summary_cli_success(
    fake_service, sheets_writer, sheets_client, observation_service
):
    registry = RegistryService(sheets_writer)
    _seed_two_brands(registry, observation_service, fake_service)
    result = runner.invoke(app, ["refresh-summary"])
    assert result.exit_code == 0, result.output
    assert len(fake_service.sheets["Summary"]) == 3  # header + 2 brands


def test_refresh_summary_dry_run_does_not_write(
    fake_service, sheets_writer, sheets_client, observation_service
):
    registry = RegistryService(sheets_writer)
    _seed_two_brands(registry, observation_service, fake_service)
    result = runner.invoke(app, ["--dry-run", "refresh-summary"])
    assert result.exit_code == 0, result.output
    assert len(fake_service.sheets["Summary"]) == 1  # header only -- nothing written


def test_compute_all_brands_raises_when_registry_empty(sheets_client):
    assert compute_all_brands(sheets_client, now=NOW) == []
    with pytest.raises(NoBrandsRegisteredError):
        refresh_summary_sheet(sheets_client, now=NOW)


def test_observation_value_labels_normalised_figure_in_gbp_not_raw_currency():
    """Regression: a USD figure normalised to GBP must be labelled GBP, not the
    raw currency (previously the GBP value was tagged with the USD unit)."""
    from casino_intel.reporting.completeness import _observation_value

    usd_to_gbp = {
        "normalised_numeric_value": "11097920000",
        "normalised_currency": "GBP",
        "normalised_unit": "USD",  # raw currency — must NOT be used as the label
        "raw_value": "14048000000",
        "raw_unit": "USD",
        "currency": "USD",
    }
    out = _observation_value(usd_to_gbp)
    assert "GBP" in out and "USD" not in out

    # non-currency figure still keeps its own unit
    customers = {"normalised_numeric_value": "13898000", "normalised_unit": "customers"}
    assert _observation_value(customers) == "13898000 customers"


def test_prefer_approved_favours_approved_else_all():
    """Regression: an unapproved figure must not beat an approved one for the
    same signal, but unreviewed data still shows when nothing is approved."""
    from casino_intel.reporting.completeness import _prefer_approved

    mixed = [{"review_status": "unreviewed", "v": 1}, {"review_status": "approved", "v": 2}]
    assert _prefer_approved(mixed) == [{"review_status": "approved", "v": 2}]

    only_unreviewed = [{"review_status": "unreviewed", "v": 3}]
    assert _prefer_approved(only_unreviewed) == only_unreviewed
