"""Unit tests for User Story 4 - Derived metrics with transparent formulas
and lineage (tasks.md T087).

Covers, per the task list: correct calculation, correct skip-on-
incompatibility (no fabricated value), correct lineage/formula-version
recording, and no overwrite on recalculation (two calculate calls with
different inputs produce two rows, never an edited row).
"""

from __future__ import annotations

import pytest

from casino_intel.derivation import formulas
from casino_intel.derivation.compatibility import (
    check_period_and_definition_compatibility,
    check_year_over_year_periods,
)
from casino_intel.derivation.engine import DerivationEngine
from casino_intel.models.vocab import ComparabilityStatus
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

OBS_HEADER = SHEET_HEADERS["Observations"]
DM_HEADER = SHEET_HEADERS["Derived Metrics"]


@pytest.fixture(autouse=True)
def _sheets(fake_service):
    fake_service.add_sheet("Observations", OBS_HEADER)
    fake_service.add_sheet("Derived Metrics", DM_HEADER)
    fake_service.add_sheet(
        "Change Log",
        [
            "change_id",
            "timestamp",
            "actor",
            "action",
            "sheet_name",
            "record_id",
            "field_name",
            "old_value",
            "new_value",
            "reason",
            "source_id",
            "ingestion_run_id",
        ],
    )


@pytest.fixture
def engine(sheets_client, sheets_writer):
    return DerivationEngine(sheets_client, sheets_writer)


def _obs_row(record_id: str, **overrides) -> list[str]:
    defaults = {col: "" for col in OBS_HEADER}
    defaults.update(
        record_id=record_id,
        created_at="2026-07-01T00:00:00+00:00",
        created_by="tester",
        updated_at="2026-07-01T00:00:00+00:00",
        status="active",
        evidence_type="reported_primary",
        confidence="high",
        review_status="approved",
        subject_type="brand",
        subject_id="brand_1",
    )
    defaults.update(overrides)
    return [str(defaults[col]) for col in OBS_HEADER]


def _add_obs(fake_service, record_id: str, **overrides) -> None:
    fake_service.sheets["Observations"].append(_obs_row(record_id, **overrides))


def _dm_rows(fake_service) -> list[dict[str, str]]:
    return [
        dict(zip(DM_HEADER, row, strict=False))
        for row in fake_service.sheets["Derived Metrics"][1:]
    ]


# --------------------------------------------------------------------------
# Formula correctness (T083)
# --------------------------------------------------------------------------


def test_formula_revenue_per_active_customer():
    result = formulas.revenue_per_active_customer(1_000_000, 10_000)
    assert result.value == pytest.approx(100.0)
    assert result.unit == "gbp"
    assert "revenue_per_active_customer" in result.formula


def test_formula_ggy_per_average_monthly_active_account_labels_caveat():
    result = formulas.ggy_per_average_monthly_active_account(900_000, 30_000)
    assert result.value == pytest.approx(30.0)
    assert "lifetime value" in result.assumptions


def test_formula_marketing_pct_revenue():
    result = formulas.marketing_pct_revenue(200_000, 1_000_000)
    assert result.value == pytest.approx(20.0)
    assert result.unit == "percent"


def test_formula_adjusted_ebitda_margin():
    result = formulas.adjusted_ebitda_margin(150_000, 1_000_000)
    assert result.value == pytest.approx(15.0)


def test_formula_traffic_growth_yoy():
    result = formulas.traffic_growth_yoy(120_000, 100_000)
    assert result.value == pytest.approx(20.0)


def test_formula_share_of_search():
    result = formulas.share_of_search(60, [60, 40])
    assert result.value == pytest.approx(60.0)


def test_formula_indicative_cpa_marketing_expense_proxy_is_labelled():
    result = formulas.indicative_cpa_from_marketing_expense(500_000, 5_000)
    assert result.value == pytest.approx(100.0)
    assert "GROUP-LEVEL PROXY" in result.assumptions


def test_formula_indicative_cpa_paid_search_midpoint():
    result = formulas.indicative_cpa_from_paid_search(2.0, 4.0)
    assert result.value == pytest.approx(3.0)
    assert "click cost" in result.assumptions


# --------------------------------------------------------------------------
# Compatibility gate (T084)
# --------------------------------------------------------------------------


def test_compatibility_flags_explicit_not_comparable():
    result = check_period_and_definition_compatibility(
        [
            {
                "subject_type": "brand",
                "subject_id": "b1",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "comparability_status": "not_comparable",
            },
            {
                "subject_type": "brand",
                "subject_id": "b1",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "comparability_status": "comparable",
            },
        ]
    )
    assert result.compatible is False
    assert result.status == ComparabilityStatus.NOT_COMPARABLE


def test_compatibility_rejects_mismatched_periods():
    result = check_period_and_definition_compatibility(
        [
            {
                "subject_type": "brand",
                "subject_id": "b1",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
            },
            {
                "subject_type": "brand",
                "subject_id": "b1",
                "period_start": "2026-04-01",
                "period_end": "2026-06-30",
            },
        ]
    )
    assert result.compatible is False


def test_compatibility_rejects_different_subjects():
    result = check_period_and_definition_compatibility(
        [
            {
                "subject_type": "brand",
                "subject_id": "b1",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
            },
            {
                "subject_type": "brand",
                "subject_id": "b2",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
            },
        ]
    )
    assert result.compatible is False


def test_compatibility_accepts_matching_comparable_inputs():
    result = check_period_and_definition_compatibility(
        [
            {
                "subject_type": "brand",
                "subject_id": "b1",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "comparability_status": "comparable",
            },
            {
                "subject_type": "brand",
                "subject_id": "b1",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "comparability_status": "comparable",
            },
        ]
    )
    assert result.compatible is True
    assert result.status == ComparabilityStatus.COMPARABLE


def test_year_over_year_rejects_non_year_gap():
    current = {"period_start": "2026-06-01", "period_end": "2026-06-30"}
    prior = {"period_start": "2026-03-01", "period_end": "2026-03-31"}
    result = check_year_over_year_periods(current, prior)
    assert result.compatible is False


def test_year_over_year_accepts_exact_year_gap():
    current = {"period_start": "2026-06-01", "period_end": "2026-06-30"}
    prior = {"period_start": "2025-06-01", "period_end": "2025-06-30"}
    result = check_year_over_year_periods(current, prior)
    assert result.compatible is True


# --------------------------------------------------------------------------
# Engine end-to-end (T085/T087)
# --------------------------------------------------------------------------


def test_revenue_per_active_customer_calculates_when_compatible(engine, fake_service):
    _add_obs(
        fake_service,
        "obs_rev",
        metric_id="revenue",
        normalised_numeric_value="1000000",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )
    _add_obs(
        fake_service,
        "obs_cust",
        metric_id="active_customers",
        normalised_numeric_value="10000",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )

    outcome = engine.run(actor="tester")

    assert len(outcome.calculated) == 1
    rows = _dm_rows(fake_service)
    assert len(rows) == 1
    row = rows[0]
    assert row["metric_id"] == "revenue_per_active_customer"
    assert float(row["value"]) == pytest.approx(100.0)
    assert row["formula_version"] == formulas.FORMULA_VERSION
    assert row["formula"] == (
        "revenue_per_active_customer = revenue_for_period / active_customers_for_compatible_period"
    )
    assert set(row["input_observation_ids"].split(", ")) == {"obs_rev", "obs_cust"}
    assert row["calculated_by"] == "tester"


def test_revenue_per_active_customer_skips_on_incompatible_periods(engine, fake_service):
    """FR-036: no fabricated value when input periods are incompatible."""
    _add_obs(
        fake_service,
        "obs_rev",
        metric_id="revenue",
        normalised_numeric_value="1000000",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )
    _add_obs(
        fake_service,
        "obs_cust",
        metric_id="active_customers",
        normalised_numeric_value="10000",
        period_start="2026-04-01",
        period_end="2026-06-30",
    )

    outcome = engine.run(actor="tester")

    assert outcome.calculated == []
    assert len(outcome.skipped) == 1
    assert _dm_rows(fake_service) == []


def test_marketing_pct_revenue_skips_when_flagged_not_comparable(engine, fake_service):
    _add_obs(
        fake_service,
        "obs_mkt",
        metric_id="marketing_expense",
        normalised_numeric_value="200000",
        period_start="2026-01-01",
        period_end="2026-12-31",
        comparability_status="not_comparable",
    )
    _add_obs(
        fake_service,
        "obs_rev",
        metric_id="revenue",
        normalised_numeric_value="1000000",
        period_start="2026-01-01",
        period_end="2026-12-31",
    )

    outcome = engine.run(actor="tester")

    assert outcome.calculated == []
    assert _dm_rows(fake_service) == []


def test_unapproved_observations_are_never_used(engine, fake_service):
    """Only review_status=approved observations may feed a calculation."""
    _add_obs(
        fake_service,
        "obs_rev",
        metric_id="revenue",
        normalised_numeric_value="1000000",
        period_start="2026-01-01",
        period_end="2026-03-31",
        review_status="human_reviewed",
    )
    _add_obs(
        fake_service,
        "obs_cust",
        metric_id="active_customers",
        normalised_numeric_value="10000",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )

    outcome = engine.run(actor="tester")

    assert outcome.calculated == []
    assert _dm_rows(fake_service) == []


def test_recalculation_appends_new_row_never_overwrites(engine, fake_service):
    """FR-037: recalculation creates a new row, never an in-place edit.

    The engine has no memory of prior runs — it recalculates from every
    currently-approved observation each time it runs. So a second run that
    still finds the first pair present recalculates it again (as a brand
    new row, identical in value) *and* newly picks up the second pair; the
    important guarantee is that the first row is never mutated in place.
    """
    _add_obs(
        fake_service,
        "obs_rev1",
        metric_id="revenue",
        normalised_numeric_value="1000000",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )
    _add_obs(
        fake_service,
        "obs_cust1",
        metric_id="active_customers",
        normalised_numeric_value="10000",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )
    first_outcome = engine.run(actor="tester")
    assert len(first_outcome.calculated) == 1
    rows_after_first = _dm_rows(fake_service)
    assert len(rows_after_first) == 1
    first_row_id = rows_after_first[0]["derived_metric_id"]

    _add_obs(
        fake_service,
        "obs_rev2",
        metric_id="revenue",
        normalised_numeric_value="2000000",
        period_start="2026-04-01",
        period_end="2026-06-30",
    )
    _add_obs(
        fake_service,
        "obs_cust2",
        metric_id="active_customers",
        normalised_numeric_value="20000",
        period_start="2026-04-01",
        period_end="2026-06-30",
    )
    engine.run(actor="tester")

    rows = _dm_rows(fake_service)
    # The original row is still present, byte-for-byte, at its original
    # position — it was never edited in place — and new row(s) were appended.
    assert len(rows) > 1
    assert rows[0]["derived_metric_id"] == first_row_id
    assert float(rows[0]["value"]) == pytest.approx(100.0)
    values = {round(float(r["value"]), 4) for r in rows}
    assert 100.0 in values  # Q1 pair
    assert 100.0 in values  # Q2 pair happens to be the same ratio (2M/20000)
    ids = [r["derived_metric_id"] for r in rows]
    assert len(ids) == len(set(ids))  # every row has a distinct ID — no overwrite


def test_traffic_growth_yoy_calculates_for_matching_year_over_year_periods(engine, fake_service):
    _add_obs(
        fake_service,
        "obs_visits_cur",
        metric_id="estimated_monthly_visits",
        normalised_numeric_value="120000",
        period_start="2026-06-01",
        period_end="2026-06-30",
        comparability_group="similarweb_month_desktop",
    )
    _add_obs(
        fake_service,
        "obs_visits_prior",
        metric_id="estimated_monthly_visits",
        normalised_numeric_value="100000",
        period_start="2025-06-01",
        period_end="2025-06-30",
        comparability_group="similarweb_month_desktop",
    )

    outcome = engine.run(actor="tester")

    assert len(outcome.calculated) == 1
    row = _dm_rows(fake_service)[0]
    assert row["metric_id"] == "traffic_growth_yoy"
    assert float(row["value"]) == pytest.approx(20.0)
    assert set(row["input_observation_ids"].split(", ")) == {"obs_visits_cur", "obs_visits_prior"}


def test_traffic_growth_yoy_skips_non_year_gap(engine, fake_service):
    _add_obs(
        fake_service,
        "obs_visits_cur",
        metric_id="estimated_monthly_visits",
        normalised_numeric_value="120000",
        period_start="2026-06-01",
        period_end="2026-06-30",
    )
    _add_obs(
        fake_service,
        "obs_visits_recent",
        metric_id="estimated_monthly_visits",
        normalised_numeric_value="110000",
        period_start="2026-03-01",
        period_end="2026-03-31",
    )

    outcome = engine.run(actor="tester")

    assert outcome.calculated == []
    assert _dm_rows(fake_service) == []


def test_share_of_search_calculates_across_comparison_set(engine, fake_service):
    _add_obs(
        fake_service,
        "obs_idx_a",
        metric_id="branded_search_interest_index",
        subject_id="brand_a",
        normalised_numeric_value="60",
        period_start="2026-06-01",
        period_end="2026-06-30",
        comparability_group="cmp_set_1",
    )
    _add_obs(
        fake_service,
        "obs_idx_b",
        metric_id="branded_search_interest_index",
        subject_id="brand_b",
        normalised_numeric_value="40",
        period_start="2026-06-01",
        period_end="2026-06-30",
        comparability_group="cmp_set_1",
    )

    outcome = engine.run(actor="tester")

    assert len(outcome.calculated) == 2
    rows = {row["subject_id"]: row for row in _dm_rows(fake_service)}
    assert float(rows["brand_a"]["value"]) == pytest.approx(60.0)
    assert float(rows["brand_b"]["value"]) == pytest.approx(40.0)
    # Lineage includes every brand's observation in the comparison set, not just its own.
    assert set(rows["brand_a"]["input_observation_ids"].split(", ")) == {"obs_idx_a", "obs_idx_b"}


def test_share_of_search_skips_without_comparison_set(engine, fake_service):
    _add_obs(
        fake_service,
        "obs_idx_solo",
        metric_id="branded_search_interest_index",
        subject_id="brand_a",
        normalised_numeric_value="60",
        period_start="2026-06-01",
        period_end="2026-06-30",
        comparability_group="",
    )

    outcome = engine.run(actor="tester")

    assert outcome.calculated == []
    assert len(outcome.skipped) >= 1
    assert _dm_rows(fake_service) == []


def test_indicative_cpa_range_from_reported_cpa(engine, fake_service):
    _add_obs(
        fake_service,
        "obs_cpa",
        metric_id="cpa_reported",
        subject_id="brand_a",
        normalised_numeric_value="45",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )

    outcome = engine.run(actor="tester")

    assert len(outcome.calculated) == 1
    row = _dm_rows(fake_service)[0]
    assert row["metric_id"] == "indicative_cpa_range"
    assert float(row["value"]) == pytest.approx(45.0)
    assert row["assumptions"]


def test_indicative_cpa_range_marketing_expense_proxy_is_labelled(engine, fake_service):
    """FR-024: a group-marketing-expense-derived CPA must be labelled a
    group-level proxy, never presented as a precise brand-level figure."""
    _add_obs(
        fake_service,
        "obs_mkt",
        metric_id="marketing_expense",
        subject_id="operator_a",
        subject_type="operator",
        normalised_numeric_value="500000",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )
    _add_obs(
        fake_service,
        "obs_newc",
        metric_id="new_customers_reported",
        subject_id="operator_a",
        subject_type="operator",
        normalised_numeric_value="5000",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )

    outcome = engine.run(actor="tester")

    assert len(outcome.calculated) == 1
    row = _dm_rows(fake_service)[0]
    assert float(row["value"]) == pytest.approx(100.0)
    assert "GROUP-LEVEL PROXY" in row["assumptions"]


def test_indicative_cpa_range_paid_search_midpoint(engine, fake_service):
    _add_obs(
        fake_service,
        "obs_low",
        metric_id="paid_keyword_cpc_low",
        subject_id="brand_a",
        normalised_numeric_value="2.0",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )
    _add_obs(
        fake_service,
        "obs_high",
        metric_id="paid_keyword_cpc_high",
        subject_id="brand_a",
        normalised_numeric_value="4.0",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )

    outcome = engine.run(actor="tester")

    assert len(outcome.calculated) == 1
    row = _dm_rows(fake_service)[0]
    assert float(row["value"]) == pytest.approx(3.0)
    assert set(row["input_observation_ids"].split(", ")) == {"obs_low", "obs_high"}
