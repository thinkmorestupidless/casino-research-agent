"""The derived-metric engine (spec FR-035-FR-037): reads only `approved`
observations, evaluates the `formulas.py` registry gated by the
`compatibility.py` compatibility check, and writes new `Derived Metrics`
rows through the shared append-only write layer.

Never overwrites a prior result: every call to `run()` only ever appends —
a recalculation (e.g. after an input observation is superseded and a new
approved one exists) produces a brand-new `DerivedMetric` row, preserving
the previous one as history (FR-037).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from casino_intel.derivation import compatibility, formulas
from casino_intel.models.derived_metric import DerivedMetric
from casino_intel.models.ids import new_id
from casino_intel.models.vocab import ComparabilityStatus, Confidence
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.serialization import to_sheet_record
from casino_intel.sheets.writer import SheetsWriter

OBSERVATIONS_SHEET = "Observations"
DERIVED_METRICS_SHEET = "Derived Metrics"

APPROVED_REVIEW_STATUS = "approved"

_CONFIDENCE_ORDER: dict[Confidence, int] = {
    Confidence.HIGH: 3,
    Confidence.MEDIUM: 2,
    Confidence.LOW: 1,
    Confidence.UNKNOWN: 0,
}


@dataclass
class DerivationOutcome:
    """Result of one `derive` run: which derived metrics were written, and
    a human-readable reason for every candidate that was skipped rather
    than fabricated."""

    calculated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _numeric_value(obs: dict[str, str]) -> float | None:
    value = _to_float(obs.get("normalised_numeric_value"))
    if value is not None:
        return value
    return _to_float(obs.get("raw_value"))


def _confidence_of(obs: dict[str, str]) -> Confidence:
    try:
        return Confidence(obs.get("confidence") or "unknown")
    except ValueError:
        return Confidence.UNKNOWN


def _min_confidence(observations: list[dict[str, str]]) -> Confidence:
    confidences = [_confidence_of(o) for o in observations]
    return min(confidences, key=lambda c: _CONFIDENCE_ORDER[c])


def _row_to_dict(row: list[str], header: list[str]) -> dict[str, str]:
    return {col: (row[i] if i < len(row) else "") for i, col in enumerate(header)}


class DerivationEngine:
    def __init__(self, client: SheetsClient, writer: SheetsWriter) -> None:
        self.client = client
        self.writer = writer

    # -- reading -------------------------------------------------------

    def _load_approved_observations(self) -> list[dict[str, str]]:
        header = SHEET_HEADERS[OBSERVATIONS_SHEET]
        rows = self.client.batch_get_values([f"{OBSERVATIONS_SHEET}!A2:ZZ"]).get(
            f"{OBSERVATIONS_SHEET}!A2:ZZ", []
        )
        observations = [_row_to_dict(row, header) for row in rows]
        return [o for o in observations if o.get("review_status") == APPROVED_REVIEW_STATUS]

    @staticmethod
    def _by_metric(observations: list[dict[str, str]], metric_id: str) -> list[dict[str, str]]:
        return [o for o in observations if o.get("metric_id") == metric_id]

    # -- writing ---------------------------------------------------------

    def _write_derived_metric(
        self,
        *,
        subject_type: str,
        subject_id: str,
        metric_id: str,
        period_start: str,
        period_end: str,
        value: float,
        unit: str,
        formula: str,
        input_observation_ids: list[str],
        assumptions: str,
        confidence: Confidence,
        comparability_status: ComparabilityStatus,
        actor: str,
        ingestion_run_id: str | None,
    ) -> str:
        now = datetime.now(UTC)
        derived = DerivedMetric(
            derived_metric_id=new_id("derived_metric"),
            subject_type=subject_type,
            subject_id=subject_id,
            metric_id=metric_id,
            period_start=period_start or None,
            period_end=period_end or None,
            value=value,
            unit=unit,
            formula_version=formulas.FORMULA_VERSION,
            formula=formula,
            input_observation_ids=input_observation_ids,
            assumptions=assumptions,
            confidence=confidence,
            comparability_status=comparability_status,
            calculated_at=now,
            calculated_by=actor,
        )
        dumped = derived.model_dump(mode="json")
        row = to_sheet_record(dumped, SHEET_HEADERS[DERIVED_METRICS_SHEET])
        result = self.writer.append_record(
            DERIVED_METRICS_SHEET, row, actor=actor, ingestion_run_id=ingestion_run_id
        )
        return result.record_id

    # -- orchestration -----------------------------------------------------

    def run(self, *, actor: str, ingestion_run_id: str | None = None) -> DerivationOutcome:
        observations = self._load_approved_observations()
        outcome = DerivationOutcome()

        ratio_metrics: list[
            tuple[str, str, str, Callable[[float, float], formulas.FormulaResult], str]
        ] = [
            (
                "revenue_per_active_customer",
                "revenue",
                "active_customers",
                formulas.revenue_per_active_customer,
                "",
            ),
            (
                "ggy_per_average_monthly_active_account",
                "ggy",
                "average_monthly_active_accounts",
                formulas.ggy_per_average_monthly_active_account,
                "",
            ),
            (
                "marketing_pct_revenue",
                "marketing_expense",
                "revenue",
                formulas.marketing_pct_revenue,
                "",
            ),
            # Many operators report a combined "sales & marketing" line rather
            # than a standalone marketing_expense; accept it as the marketing
            # proxy so marketing_pct_revenue still derives (recorded in the
            # assumptions). An operator that reports BOTH would yield two rows,
            # each labelled by its input line.
            (
                "marketing_pct_revenue",
                "sales_and_marketing_expense",
                "revenue",
                formulas.marketing_pct_revenue,
                "Marketing proxied by the reported sales & marketing (S&M) expense line.",
            ),
            (
                "adjusted_ebitda_margin",
                "adjusted_ebitda",
                "revenue",
                formulas.adjusted_ebitda_margin,
                "",
            ),
        ]
        for (
            output_metric_id,
            numerator_metric_id,
            denominator_metric_id,
            compute,
            extra,
        ) in ratio_metrics:
            self._derive_ratio_metric(
                observations,
                actor,
                ingestion_run_id,
                output_metric_id=output_metric_id,
                numerator_metric_id=numerator_metric_id,
                denominator_metric_id=denominator_metric_id,
                compute=compute,
                extra_assumptions=extra,
                outcome=outcome,
            )

        self._derive_traffic_growth(observations, actor, ingestion_run_id, outcome)
        self._derive_share_of_search(observations, actor, ingestion_run_id, outcome)
        self._derive_indicative_cpa_range(observations, actor, ingestion_run_id, outcome)

        return outcome

    # -- individual calculation families ------------------------------------

    def _derive_ratio_metric(
        self,
        observations: list[dict[str, str]],
        actor: str,
        ingestion_run_id: str | None,
        *,
        output_metric_id: str,
        numerator_metric_id: str,
        denominator_metric_id: str,
        compute: Callable[[float, float], formulas.FormulaResult],
        extra_assumptions: str,
        outcome: DerivationOutcome,
    ) -> None:
        numerators = self._by_metric(observations, numerator_metric_id)
        denominators = self._by_metric(observations, denominator_metric_id)
        for num in numerators:
            for den in denominators:
                if num is den:
                    continue
                if (num.get("subject_type"), num.get("subject_id")) != (
                    den.get("subject_type"),
                    den.get("subject_id"),
                ):
                    continue
                result = compatibility.check_period_and_definition_compatibility([num, den])
                subject_id = num.get("subject_id", "")
                if not result.compatible:
                    outcome.skipped.append(
                        f"{output_metric_id} skipped for subject={subject_id}: {result.reason}"
                    )
                    continue

                num_val, den_val = _numeric_value(num), _numeric_value(den)
                if num_val is None or den_val is None or den_val == 0:
                    outcome.skipped.append(
                        f"{output_metric_id} skipped for subject={subject_id}: "
                        "missing or zero numeric input value"
                    )
                    continue
                try:
                    fr = compute(num_val, den_val)
                except ZeroDivisionError as exc:
                    outcome.skipped.append(
                        f"{output_metric_id} skipped for subject={subject_id}: {exc}"
                    )
                    continue

                assumptions = " ".join(a for a in (fr.assumptions, extra_assumptions) if a).strip()
                record_id = self._write_derived_metric(
                    subject_type=num.get("subject_type", ""),
                    subject_id=subject_id,
                    metric_id=output_metric_id,
                    period_start=num.get("period_start", ""),
                    period_end=num.get("period_end", ""),
                    value=fr.value,
                    unit=fr.unit,
                    formula=fr.formula,
                    input_observation_ids=[num.get("record_id", ""), den.get("record_id", "")],
                    assumptions=assumptions,
                    confidence=_min_confidence([num, den]),
                    comparability_status=result.status,
                    actor=actor,
                    ingestion_run_id=ingestion_run_id,
                )
                outcome.calculated.append(record_id)

    def _derive_traffic_growth(
        self,
        observations: list[dict[str, str]],
        actor: str,
        ingestion_run_id: str | None,
        outcome: DerivationOutcome,
    ) -> None:
        visits = self._by_metric(observations, "estimated_monthly_visits")
        by_subject: dict[tuple[str, str], list[dict[str, str]]] = {}
        for obs in visits:
            key = (obs.get("subject_type", ""), obs.get("subject_id", ""))
            by_subject.setdefault(key, []).append(obs)

        for (subject_type, subject_id), obs_list in by_subject.items():
            for current in obs_list:
                for prior in obs_list:
                    if current is prior:
                        continue
                    yoy = compatibility.check_year_over_year_periods(current, prior)
                    if not yoy.compatible:
                        continue

                    cur_val, pri_val = _numeric_value(current), _numeric_value(prior)
                    if cur_val is None or pri_val is None:
                        outcome.skipped.append(
                            f"traffic_growth_yoy skipped for subject={subject_id}: missing numeric value"
                        )
                        continue
                    try:
                        fr = formulas.traffic_growth_yoy(cur_val, pri_val)
                    except ZeroDivisionError as exc:
                        outcome.skipped.append(
                            f"traffic_growth_yoy skipped for subject={subject_id}: {exc}"
                        )
                        continue

                    record_id = self._write_derived_metric(
                        subject_type=subject_type,
                        subject_id=subject_id,
                        metric_id="traffic_growth_yoy",
                        period_start=current.get("period_start", ""),
                        period_end=current.get("period_end", ""),
                        value=fr.value,
                        unit=fr.unit,
                        formula=fr.formula,
                        input_observation_ids=[
                            current.get("record_id", ""),
                            prior.get("record_id", ""),
                        ],
                        assumptions=fr.assumptions,
                        confidence=_min_confidence([current, prior]),
                        comparability_status=yoy.status,
                        actor=actor,
                        ingestion_run_id=ingestion_run_id,
                    )
                    outcome.calculated.append(record_id)

    def _derive_share_of_search(
        self,
        observations: list[dict[str, str]],
        actor: str,
        ingestion_run_id: str | None,
        outcome: DerivationOutcome,
    ) -> None:
        interest_obs = self._by_metric(observations, "branded_search_interest_index")
        groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
        for obs in interest_obs:
            key = (
                obs.get("comparability_group", ""),
                obs.get("period_start", ""),
                obs.get("period_end", ""),
            )
            groups.setdefault(key, []).append(obs)

        for (comparison_set_id, period_start, period_end), obs_list in groups.items():
            if not comparison_set_id:
                outcome.skipped.append(
                    "share_of_search skipped: observation has no comparison_set "
                    "(comparability_group) — cannot determine what it is comparable against"
                )
                continue
            if len(obs_list) < 2:
                outcome.skipped.append(
                    f"share_of_search skipped for comparison_set={comparison_set_id}: "
                    "fewer than two brands present in the set for this period"
                )
                continue

            result = compatibility.check_period_and_definition_compatibility(
                obs_list, require_same_subject=False, require_identical_period=True
            )
            if not result.compatible:
                outcome.skipped.append(
                    f"share_of_search skipped for comparison_set={comparison_set_id}: {result.reason}"
                )
                continue

            values = [_numeric_value(o) for o in obs_list]
            if any(v is None for v in values):
                outcome.skipped.append(
                    f"share_of_search skipped for comparison_set={comparison_set_id}: "
                    "an observation in the set is missing a numeric value"
                )
                continue

            input_ids = [o.get("record_id", "") for o in obs_list]
            for obs, value in zip(obs_list, values, strict=True):
                assert value is not None
                try:
                    fr = formulas.share_of_search(value, [v for v in values if v is not None])
                except ZeroDivisionError as exc:
                    outcome.skipped.append(
                        f"share_of_search skipped for comparison_set={comparison_set_id}: {exc}"
                    )
                    continue

                record_id = self._write_derived_metric(
                    subject_type=obs.get("subject_type", ""),
                    subject_id=obs.get("subject_id", ""),
                    metric_id="share_of_search",
                    period_start=period_start,
                    period_end=period_end,
                    value=fr.value,
                    unit=fr.unit,
                    formula=fr.formula,
                    input_observation_ids=input_ids,
                    assumptions=f"Comparison set: {comparison_set_id}",
                    confidence=_min_confidence(obs_list),
                    comparability_status=result.status,
                    actor=actor,
                    ingestion_run_id=ingestion_run_id,
                )
                outcome.calculated.append(record_id)

    def _derive_indicative_cpa_range(
        self,
        observations: list[dict[str, str]],
        actor: str,
        ingestion_run_id: str | None,
        outcome: DerivationOutcome,
    ) -> None:
        # Method 1 (highest priority): directly reported CPA.
        for obs in self._by_metric(observations, "cpa_reported"):
            value = _numeric_value(obs)
            if value is None:
                continue
            fr = formulas.indicative_cpa_from_reported(value)
            record_id = self._write_derived_metric(
                subject_type=obs.get("subject_type", ""),
                subject_id=obs.get("subject_id", ""),
                metric_id="indicative_cpa_range",
                period_start=obs.get("period_start", ""),
                period_end=obs.get("period_end", ""),
                value=fr.value,
                unit=fr.unit,
                formula=fr.formula,
                input_observation_ids=[obs.get("record_id", "")],
                assumptions=fr.assumptions,
                confidence=_confidence_of(obs),
                comparability_status=ComparabilityStatus.COMPARABLE,
                actor=actor,
                ingestion_run_id=ingestion_run_id,
            )
            outcome.calculated.append(record_id)

        # Method 2: group-level marketing-expense proxy — always labelled (FR-024).
        marketing = self._by_metric(observations, "marketing_expense")
        new_customers = self._by_metric(observations, "new_customers_reported")
        for mkt in marketing:
            for nc in new_customers:
                if (mkt.get("subject_type"), mkt.get("subject_id")) != (
                    nc.get("subject_type"),
                    nc.get("subject_id"),
                ):
                    continue
                result = compatibility.check_period_and_definition_compatibility([mkt, nc])
                if not result.compatible:
                    outcome.skipped.append(
                        "indicative_cpa_range (marketing-expense proxy) skipped for "
                        f"subject={mkt.get('subject_id')}: {result.reason}"
                    )
                    continue
                mkt_val, nc_val = _numeric_value(mkt), _numeric_value(nc)
                if mkt_val is None or nc_val is None or nc_val == 0:
                    continue
                try:
                    fr = formulas.indicative_cpa_from_marketing_expense(mkt_val, nc_val)
                except ZeroDivisionError:
                    continue
                record_id = self._write_derived_metric(
                    subject_type=mkt.get("subject_type", ""),
                    subject_id=mkt.get("subject_id", ""),
                    metric_id="indicative_cpa_range",
                    period_start=mkt.get("period_start", ""),
                    period_end=mkt.get("period_end", ""),
                    value=fr.value,
                    unit=fr.unit,
                    formula=fr.formula,
                    input_observation_ids=[mkt.get("record_id", ""), nc.get("record_id", "")],
                    assumptions=fr.assumptions,
                    confidence=Confidence.LOW,
                    comparability_status=result.status,
                    actor=actor,
                    ingestion_run_id=ingestion_run_id,
                )
                outcome.calculated.append(record_id)

        # Method 3: affiliate CPA offer.
        for obs in self._by_metric(observations, "affiliate_cpa_offer"):
            value = _numeric_value(obs)
            if value is None:
                continue
            fr = formulas.indicative_cpa_from_affiliate_offer(value)
            record_id = self._write_derived_metric(
                subject_type=obs.get("subject_type", ""),
                subject_id=obs.get("subject_id", ""),
                metric_id="indicative_cpa_range",
                period_start=obs.get("period_start", ""),
                period_end=obs.get("period_end", ""),
                value=fr.value,
                unit=fr.unit,
                formula=fr.formula,
                input_observation_ids=[obs.get("record_id", "")],
                assumptions=fr.assumptions,
                confidence=_confidence_of(obs),
                comparability_status=ComparabilityStatus.PARTIALLY_COMPARABLE,
                actor=actor,
                ingestion_run_id=ingestion_run_id,
            )
            outcome.calculated.append(record_id)

        # Method 4: paid-search CPC range midpoint.
        cpc_low_by_key = {
            (
                o.get("subject_type"),
                o.get("subject_id"),
                o.get("period_start"),
                o.get("period_end"),
            ): o
            for o in self._by_metric(observations, "paid_keyword_cpc_low")
        }
        for high in self._by_metric(observations, "paid_keyword_cpc_high"):
            key = (
                high.get("subject_type"),
                high.get("subject_id"),
                high.get("period_start"),
                high.get("period_end"),
            )
            low = cpc_low_by_key.get(key)
            if low is None:
                continue
            low_val, high_val = _numeric_value(low), _numeric_value(high)
            if low_val is None or high_val is None:
                continue
            fr = formulas.indicative_cpa_from_paid_search(low_val, high_val)
            record_id = self._write_derived_metric(
                subject_type=high.get("subject_type", ""),
                subject_id=high.get("subject_id", ""),
                metric_id="indicative_cpa_range",
                period_start=high.get("period_start", ""),
                period_end=high.get("period_end", ""),
                value=fr.value,
                unit=fr.unit,
                formula=fr.formula,
                input_observation_ids=[low.get("record_id", ""), high.get("record_id", "")],
                assumptions=fr.assumptions,
                confidence=Confidence.LOW,
                comparability_status=ComparabilityStatus.PARTIALLY_COMPARABLE,
                actor=actor,
                ingestion_run_id=ingestion_run_id,
            )
            outcome.calculated.append(record_id)
