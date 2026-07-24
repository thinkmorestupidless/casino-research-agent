"""Core validation rules for FR-001-FR-010: identity, required evidence,
controlled-vocabulary enforcement, and comparability fields.

Returns a list of `(DataQualityIssueType, description)` failures rather than
raising — callers decide whether to route each failure to
`validation/data_quality.py` and/or refuse the write.
"""

from __future__ import annotations

from casino_intel.models.ids import is_valid_id
from casino_intel.models.vocab import DataQualityIssueType
from casino_intel.sheets.config_loader import MetricRegistry

Failure = tuple[DataQualityIssueType, str]


def validate_record_id(record_id: str) -> list[Failure]:
    if not is_valid_id(record_id):
        return [(DataQualityIssueType.INVALID_ID, f"{record_id!r} is not a valid prefixed ULID")]
    return []


def validate_has_source(source_id: str | None) -> list[Failure]:
    if not source_id:
        return [(DataQualityIssueType.MISSING_SOURCE, "source_id is required but missing")]
    return []


def validate_reporting_period(
    period_start: str | None, period_end: str | None, *, required: bool = False
) -> list[Failure]:
    if required and not (period_start and period_end):
        return [
            (
                DataQualityIssueType.MISSING_REPORTING_PERIOD,
                "period_start/period_end are required for this metric but missing",
            )
        ]
    return []


def validate_metric_known(metric_id: str, registry: MetricRegistry) -> list[Failure]:
    if metric_id not in registry:
        return [
            (
                DataQualityIssueType.UNKNOWN_METRIC_DEFINITION,
                f"metric_id {metric_id!r} is not in the metric-definition registry",
            )
        ]
    return []


def validate_percentage_range(
    metric_id: str, value: float | None, *, is_percentage: bool
) -> list[Failure]:
    if is_percentage and value is not None and not (0 <= value <= 100):
        return [
            (
                DataQualityIssueType.PERCENTAGE_OUTSIDE_0_100,
                f"{metric_id} value {value} is outside the valid 0-100 range",
            )
        ]
    return []


def validate_normalised_requires_raw(
    raw_value: str | None, normalised_value: float | None
) -> list[Failure]:
    if normalised_value is not None and not raw_value:
        return [
            (
                DataQualityIssueType.NORMALISED_VALUE_WITHOUT_RAW_VALUE,
                "normalised_numeric_value is set but raw_value is missing",
            )
        ]
    return []


def validate_currency_supported(currency: str, allowed_currencies: set[str]) -> list[Failure]:
    if currency and currency not in allowed_currencies:
        return [
            (
                DataQualityIssueType.UNSUPPORTED_CURRENCY,
                f"currency {currency!r} is not in the supported currency list",
            )
        ]
    return []


def validate_controlled_vocabulary(
    field_name: str, value: str, allowed_values: set[str]
) -> list[Failure]:
    if value and value not in allowed_values:
        return [
            (
                DataQualityIssueType.INVALID_CONTROLLED_VOCABULARY_VALUE,
                f"{field_name}={value!r} is not in the allowed controlled-vocabulary set",
            )
        ]
    return []


def validate_group_figure_not_mislabelled(
    subject_type: str, metric_id: str, group_only_metric_ids: set[str]
) -> list[Failure]:
    """FR-022: a metric known to be disclosed only at group/operator level
    must never be recorded as if it were brand-specific without an explicit
    allocation record (handled separately in the Financials service)."""
    if subject_type == "brand" and metric_id in group_only_metric_ids:
        return [
            (
                DataQualityIssueType.GROUP_FIGURE_INCORRECTLY_LABELLED_AS_BRAND_FIGURE,
                f"{metric_id!r} is a group-only metric but was recorded against a brand "
                "without an allocation record",
            )
        ]
    return []
