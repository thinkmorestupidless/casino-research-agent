"""The comparability/compatibility gate (spec FR-036).

This is the single most important behavioural rule in User Story 4: a
derived-metric calculation must be **skipped entirely** — no row written —
rather than computed with a fabricated value, whenever its input
observations' periods or definitions are not sufficiently compatible
(docs/requirements.md §24: "A range with explicit assumptions is preferable
to a fabricated point estimate"; "Quarterly active counts should not be
naively summed").

Callers (derivation/engine.py) never compute a value before calling one of
these checks, and never write a row when `compatible` is False.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from casino_intel.models.vocab import ComparabilityStatus

#: An observation-like row: any mapping exposing at least the fields this
#: module inspects (as read straight off an `Observations` sheet row, so
#: values are typically strings).
ObservationLike = Mapping[str, Any]


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    status: ComparabilityStatus
    reason: str = ""


def _get(obs: ObservationLike, key: str) -> str:
    value = obs.get(key)
    return "" if value is None else str(value)


def check_period_and_definition_compatibility(
    observations: Sequence[ObservationLike],
    *,
    require_same_subject: bool = True,
    require_identical_period: bool = True,
) -> CompatibilityResult:
    """Decide whether a set of input observations may be combined into one
    derived-metric calculation.

    Checks, in order:
    1. None of the inputs is already explicitly flagged `not_comparable`.
    2. (optional) All inputs describe the same subject (`subject_type` +
       `subject_id`) — required for ratio metrics like
       `revenue_per_active_customer`.
    3. Inputs that specify a `definition_id` all agree — mixing two
       differently-defined variants of "the same" metric is not safe to
       combine.
    4. (optional) All inputs share an identical `period_start`/`period_end`
       — required whenever a formula assumes matching reporting periods.
    """
    if not observations:
        return CompatibilityResult(
            False, ComparabilityStatus.UNKNOWN, "No input observations supplied"
        )

    for obs in observations:
        if _get(obs, "comparability_status") == ComparabilityStatus.NOT_COMPARABLE.value:
            return CompatibilityResult(
                False,
                ComparabilityStatus.NOT_COMPARABLE,
                "An input observation is explicitly flagged not_comparable",
            )

    if require_same_subject:
        subjects = {(_get(o, "subject_type"), _get(o, "subject_id")) for o in observations}
        if len(subjects) > 1:
            return CompatibilityResult(
                False,
                ComparabilityStatus.NOT_COMPARABLE,
                "Input observations describe different subjects",
            )

    definition_ids = {_get(o, "definition_id") for o in observations if _get(o, "definition_id")}
    if len(definition_ids) > 1:
        return CompatibilityResult(
            False,
            ComparabilityStatus.NOT_COMPARABLE,
            "Input observations use different metric definitions (definition_id)",
        )

    if require_identical_period:
        for obs in observations:
            if not _get(obs, "period_start") or not _get(obs, "period_end"):
                return CompatibilityResult(
                    False,
                    ComparabilityStatus.UNKNOWN,
                    "An input observation is missing period_start/period_end",
                )
        periods = {(_get(o, "period_start"), _get(o, "period_end")) for o in observations}
        if len(periods) > 1:
            return CompatibilityResult(
                False,
                ComparabilityStatus.NOT_COMPARABLE,
                "Input observations cover different reporting periods",
            )

    statuses = {_get(o, "comparability_status") for o in observations}
    if statuses == {ComparabilityStatus.COMPARABLE.value}:
        return CompatibilityResult(True, ComparabilityStatus.COMPARABLE, "")
    if ComparabilityStatus.PARTIALLY_COMPARABLE.value in statuses:
        return CompatibilityResult(
            True,
            ComparabilityStatus.PARTIALLY_COMPARABLE,
            "At least one input observation is only partially comparable",
        )
    return CompatibilityResult(
        True,
        ComparabilityStatus.UNKNOWN,
        "Comparability could not be fully confirmed from input metadata",
    )


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def check_year_over_year_periods(
    current: ObservationLike, prior: ObservationLike
) -> CompatibilityResult:
    """`traffic_growth_yoy` needs `prior` to cover a period of the same
    length exactly one year before `current`, from the same
    provider/comparability group — never an arbitrary earlier period."""
    for obs in (current, prior):
        if _get(obs, "comparability_status") == ComparabilityStatus.NOT_COMPARABLE.value:
            return CompatibilityResult(
                False,
                ComparabilityStatus.NOT_COMPARABLE,
                "An input observation is explicitly flagged not_comparable",
            )

    current_group = _get(current, "comparability_group")
    prior_group = _get(prior, "comparability_group")
    if current_group and prior_group and current_group != prior_group:
        return CompatibilityResult(
            False,
            ComparabilityStatus.NOT_COMPARABLE,
            "Current and prior-year observations come from different providers/comparability groups",
        )

    cur_start, cur_end = _parse_date(current.get("period_start")), _parse_date(
        current.get("period_end")
    )
    pri_start, pri_end = _parse_date(prior.get("period_start")), _parse_date(
        prior.get("period_end")
    )
    if not all([cur_start, cur_end, pri_start, pri_end]):
        return CompatibilityResult(
            False,
            ComparabilityStatus.UNKNOWN,
            "Missing period_start/period_end on an input observation",
        )

    if (cur_end - cur_start) != (pri_end - pri_start):
        return CompatibilityResult(
            False,
            ComparabilityStatus.NOT_COMPARABLE,
            "Current and prior-year periods differ in length",
        )

    delta_start_days = (cur_start - pri_start).days
    delta_end_days = (cur_end - pri_end).days
    if not (360 <= delta_start_days <= 370) or not (360 <= delta_end_days <= 370):
        return CompatibilityResult(
            False,
            ComparabilityStatus.NOT_COMPARABLE,
            "Prior-year period is not exactly one year before the current period",
        )

    status = (
        ComparabilityStatus.COMPARABLE
        if current_group and current_group == prior_group
        else ComparabilityStatus.UNKNOWN
    )
    return CompatibilityResult(True, status, "")
