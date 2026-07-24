"""The derived-metric formula registry (spec FR-035, source doc §9.18
"Initial calculations").

Each function takes the specific, already period-filtered numeric inputs it
needs and returns a `FormulaResult` — the value plus the literal formula
string that produced it, its unit, and any assumptions that must be
recorded alongside the value. Input *lookup* (finding compatible
observations, checking periods/definitions) is deliberately kept out of
this module — that is `derivation/compatibility.py` and
`derivation/engine.py`'s job. Formula functions here only compute.

`FORMULA_VERSION` is bumped whenever a formula's definition changes, so a
`DerivedMetric` row's `formula_version` always tells you exactly which
version of the calculation produced it.
"""

from __future__ import annotations

from dataclasses import dataclass

FORMULA_VERSION = "1.0.0"


@dataclass(frozen=True)
class FormulaResult:
    value: float
    formula: str
    unit: str
    assumptions: str = ""


# --------------------------------------------------------------------------
# Revenue per active customer
# --------------------------------------------------------------------------


def revenue_per_active_customer(revenue: float, active_customers: float) -> FormulaResult:
    if active_customers == 0:
        raise ZeroDivisionError("active_customers is zero")
    return FormulaResult(
        value=revenue / active_customers,
        formula="revenue_per_active_customer = revenue_for_period / active_customers_for_compatible_period",
        unit="gbp",
    )


# --------------------------------------------------------------------------
# GGY per average monthly active account
# --------------------------------------------------------------------------


def ggy_per_average_monthly_active_account(
    quarterly_ggy: float, average_monthly_active_accounts: float
) -> FormulaResult:
    if average_monthly_active_accounts == 0:
        raise ZeroDivisionError("average_monthly_active_accounts is zero")
    return FormulaResult(
        value=quarterly_ggy / average_monthly_active_accounts,
        formula="ggy_per_average_monthly_active_account = quarterly_ggy / average_monthly_active_accounts",
        unit="gbp",
        assumptions=(
            "Numerator covers the reporting period (typically a quarter) while the "
            "denominator is an average monthly active-account count; this is NOT "
            "equivalent to per-customer lifetime value."
        ),
    )


# --------------------------------------------------------------------------
# Marketing expense as percentage of revenue
# --------------------------------------------------------------------------


def marketing_pct_revenue(marketing_expense: float, revenue: float) -> FormulaResult:
    if revenue == 0:
        raise ZeroDivisionError("revenue is zero")
    return FormulaResult(
        value=(marketing_expense / revenue) * 100,
        formula="marketing_pct_revenue = marketing_expense / revenue",
        unit="percent",
    )


# --------------------------------------------------------------------------
# Adjusted EBITDA margin
# --------------------------------------------------------------------------


def adjusted_ebitda_margin(adjusted_ebitda: float, revenue: float) -> FormulaResult:
    if revenue == 0:
        raise ZeroDivisionError("revenue is zero")
    return FormulaResult(
        value=(adjusted_ebitda / revenue) * 100,
        formula="adjusted_ebitda_margin = adjusted_ebitda / revenue",
        unit="percent",
    )


# --------------------------------------------------------------------------
# Traffic growth, year on year
# --------------------------------------------------------------------------


def traffic_growth_yoy(
    visits_current_period: float, visits_prior_year_period: float
) -> FormulaResult:
    if visits_prior_year_period == 0:
        raise ZeroDivisionError("visits_prior_year_period is zero")
    return FormulaResult(
        value=((visits_current_period - visits_prior_year_period) / visits_prior_year_period) * 100,
        formula=(
            "traffic_growth_yoy = (visits_current_period - visits_prior_year_period) "
            "/ visits_prior_year_period"
        ),
        unit="percent",
    )


# --------------------------------------------------------------------------
# Share of search
# --------------------------------------------------------------------------


def share_of_search(
    brand_interest_index: float, interest_indices_in_same_comparison_set: list[float]
) -> FormulaResult:
    total = sum(interest_indices_in_same_comparison_set)
    if total == 0:
        raise ZeroDivisionError("sum of interest indices in comparison set is zero")
    return FormulaResult(
        value=(brand_interest_index / total) * 100,
        formula="share_of_search = brand_interest_index / sum(interest_indices_in_same_comparison_set)",
        unit="percent",
    )


# --------------------------------------------------------------------------
# Indicative CPA range — no single mandatory formula (source doc §9.18).
# Each method below is a distinct, independently-selectable calculation;
# the engine picks whichever inputs are available and always records which
# method/assumptions were used (docs/requirements.md §24, FR-024).
# --------------------------------------------------------------------------


def indicative_cpa_from_reported(cpa_reported: float) -> FormulaResult:
    return FormulaResult(
        value=cpa_reported,
        formula="indicative_cpa_range = cpa_reported",
        unit="gbp",
        assumptions="Directly reported CPA figure used as a point estimate.",
    )


def indicative_cpa_from_marketing_expense(
    marketing_expense: float, new_customers: float
) -> FormulaResult:
    if new_customers == 0:
        raise ZeroDivisionError("new_customers is zero")
    return FormulaResult(
        value=marketing_expense / new_customers,
        formula="indicative_cpa_range = marketing_expense / new_customers",
        unit="gbp",
        assumptions=(
            "GROUP-LEVEL PROXY (FR-024): derived from total group/operator marketing "
            "expense divided by new customers acquired; this is NOT a precise "
            "brand-level acquisition cost and must not be presented as one without "
            "this label."
        ),
    )


def indicative_cpa_from_affiliate_offer(affiliate_cpa_offer: float) -> FormulaResult:
    return FormulaResult(
        value=affiliate_cpa_offer,
        formula="indicative_cpa_range = affiliate_cpa_offer",
        unit="gbp",
        assumptions=(
            "Based on an advertised/contractual affiliate CPA offer, which is not "
            "necessarily the operator's realised average acquisition cost."
        ),
    )


def indicative_cpa_from_paid_search(cpc_low: float, cpc_high: float) -> FormulaResult:
    return FormulaResult(
        value=(cpc_low + cpc_high) / 2,
        formula="indicative_cpa_range = mean(paid_keyword_cpc_low, paid_keyword_cpc_high)",
        unit="gbp",
        assumptions=(
            f"Midpoint of a paid-search cost-per-click range (low={cpc_low}, "
            f"high={cpc_high}); a click cost is a proxy for acquisition cost, not a "
            "measured CPA."
        ),
    )
