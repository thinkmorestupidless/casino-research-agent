"""Ingestion-time business-rule validator (spec FR-020).

Builds on the shared checks in `validation/rules_core.py` and adds the
rules specific to freshly-extracted candidate facts: negative-value
prohibition, staleness, and conflicting-high-confidence detection. Callers
(the ingestion orchestrator, `casino-intel validate`) route every failure
returned here to `validation/data_quality.py` — a validation failure is
never silently dropped and never silently accepted (contracts/cli-commands.md
`ingest-source`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from casino_intel.extraction.schema import ExtractionRecord
from casino_intel.models.vocab import DataQualityIssueType
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.validation import rules_core
from casino_intel.validation.rules_core import Failure

#: A same-metric fact whose `as_of_date` is older than this is flagged as
#: stale (source doc §11.3) — a soft warning, not a hard rejection.
STALE_AFTER_DAYS = 400


def validate_extraction_record(
    record: ExtractionRecord,
    *,
    metric_registry: MetricRegistry,
    negative_prohibited_metrics: frozenset[str] = frozenset(),
) -> list[Failure]:
    """Run every ingestion-time business rule against one extraction
    candidate, returning the accumulated list of `(issue_type, description)`
    failures (empty if the record is clean)."""
    failures: list[Failure] = []
    failures += rules_core.validate_has_source(record.source_id)
    failures += rules_core.validate_metric_known(record.metric_id, metric_registry)
    failures += rules_core.validate_normalised_requires_raw(
        record.raw_value, record.normalised_numeric_value
    )

    failures += rules_core.validate_percentage_for_metric(
        record.metric_id, record.normalised_numeric_value, metric_registry
    )

    metric_def = metric_registry.get(record.metric_id)
    if metric_def:
        subject_types = metric_def.get("subject_types", [])
        if record.subject.type == "brand" and subject_types and "brand" not in subject_types:
            # A metric the registry only defines for operator/market level
            # has turned up recorded against a brand — FR-022's
            # "never allocate group->brand silently".
            failures += rules_core.validate_group_figure_not_mislabelled(
                record.subject.type, record.metric_id, {record.metric_id}
            )

    if (
        record.metric_id in negative_prohibited_metrics
        and record.normalised_numeric_value is not None
        and record.normalised_numeric_value < 0
    ):
        failures.append(
            (
                DataQualityIssueType.NEGATIVE_VALUE_WHERE_PROHIBITED,
                f"{record.metric_id} value {record.normalised_numeric_value} "
                "must not be negative",
            )
        )

    failures += validate_not_stale(record.as_of_date)

    return failures


def validate_not_stale(as_of_date_str: str | None, *, today: date | None = None) -> list[Failure]:
    """FR-020 `stale_observation`: flag (not reject) a fact whose point-in-time
    date is older than `STALE_AFTER_DAYS`."""
    if not as_of_date_str:
        return []
    try:
        as_of = datetime.fromisoformat(as_of_date_str).date()
    except ValueError:
        return []
    today = today or datetime.now(UTC).date()
    age_days = (today - as_of).days
    if age_days > STALE_AFTER_DAYS:
        return [
            (
                DataQualityIssueType.STALE_OBSERVATION,
                f"as_of_date {as_of_date_str} is {age_days} days old "
                f"(older than the {STALE_AFTER_DAYS}-day freshness threshold)",
            )
        ]
    return []


def validate_no_conflicting_high_confidence(
    new_value: float | None,
    existing_high_confidence_values: list[float],
    *,
    metric_id: str,
    tolerance: float = 0.0,
) -> list[Failure]:
    """FR-020 `conflicting_high_confidence_observations`: two high-confidence
    facts for the same subject/metric/period that materially disagree are
    both retained (never silently merged/averaged) but flagged so a human
    can reconcile them."""
    if new_value is None:
        return []
    for existing in existing_high_confidence_values:
        threshold = tolerance * max(abs(existing), 1.0)
        if abs(existing - new_value) > threshold:
            return [
                (
                    DataQualityIssueType.CONFLICTING_HIGH_CONFIDENCE_OBSERVATIONS,
                    f"{metric_id}: new high-confidence value {new_value} conflicts with "
                    f"existing high-confidence value {existing}",
                )
            ]
    return []
