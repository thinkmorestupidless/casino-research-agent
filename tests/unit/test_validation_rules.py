"""Unit tests (T071): extraction-record schema conformance
(contracts/extraction-record.schema.json) and ingestion-time
validation-rule routing to Data Quality (spec FR-020)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from casino_intel.extraction.schema import ExtractionRecord
from casino_intel.models.vocab import DataQualityIssueType
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.validation import rules_ingestion

METRICS_PATH = "config/metrics.yaml"


@pytest.fixture
def metric_registry() -> MetricRegistry:
    return MetricRegistry(METRICS_PATH)


def _base_record(**overrides: object) -> ExtractionRecord:
    defaults: dict[str, object] = dict(
        subject={"type": "brand", "id": "brand_1"},
        metric_id="estimated_monthly_visits",
        raw_value="1,200,000",
        source_id="source_1",
        source_locator="table 2, row 4",
        evidence_type="third_party_estimate",
        confidence="medium",
    )
    defaults.update(overrides)
    return ExtractionRecord(**defaults)


# --- Extraction-record schema conformance -----------------------------------------


def test_extraction_record_accepts_a_minimal_valid_candidate() -> None:
    record = _base_record()
    assert record.review_status == "unreviewed"
    assert record.subject.type == "brand"
    assert record.subject.id == "brand_1"


def test_extraction_record_always_unreviewed_even_if_overridden() -> None:
    """FR-017: no extractor may self-approve — the schema only accepts the
    literal 'unreviewed' value."""
    with pytest.raises(ValidationError):
        _base_record(review_status="approved")


def test_extraction_record_rejects_additional_properties() -> None:
    """The JSON schema sets additionalProperties: false."""
    with pytest.raises(ValidationError):
        _base_record(unexpected_field="oops")


def test_extraction_record_rejects_source_id_without_prefix() -> None:
    with pytest.raises(ValidationError):
        _base_record(source_id="not-a-source-id")


def test_extraction_record_rejects_document_id_without_prefix() -> None:
    with pytest.raises(ValidationError):
        _base_record(document_id="not-a-document-id")


def test_extraction_record_rejects_malformed_currency() -> None:
    with pytest.raises(ValidationError):
        _base_record(currency="pounds")


def test_extraction_record_rejects_malformed_geography() -> None:
    with pytest.raises(ValidationError):
        _base_record(geography="GBR")  # must be 2-letter alpha-2, not 3


def test_extraction_record_rejects_excerpt_over_max_length() -> None:
    with pytest.raises(ValidationError):
        _base_record(verbatim_excerpt="x" * 501)


def test_extraction_record_rejects_unknown_subject_type() -> None:
    with pytest.raises(ValidationError):
        _base_record(subject={"type": "not_a_real_subject_type", "id": "brand_1"})


def test_extraction_record_rejects_unknown_evidence_type() -> None:
    with pytest.raises(ValidationError):
        _base_record(evidence_type="made_up_evidence_type")


# --- Ingestion-time validation-rule routing ----------------------------------------


def test_validate_extraction_record_clean_candidate_has_no_failures(metric_registry) -> None:
    record = _base_record(normalised_numeric_value=1_200_000.0)
    assert rules_ingestion.validate_extraction_record(record, metric_registry=metric_registry) == []


def test_validate_extraction_record_missing_source_routes_to_missing_source(
    metric_registry,
) -> None:
    # The model itself requires a non-empty, prefixed source_id, so the
    # "missing source" rule is exercised directly rather than via a
    # constructed ExtractionRecord.
    from casino_intel.validation import rules_core

    failures = rules_core.validate_has_source("")
    assert failures and failures[0][0] == DataQualityIssueType.MISSING_SOURCE


def test_validate_extraction_record_unknown_metric_routes_to_data_quality(metric_registry) -> None:
    record = _base_record(metric_id="not_a_real_metric")
    failures = rules_ingestion.validate_extraction_record(record, metric_registry=metric_registry)
    issue_types = {issue_type for issue_type, _ in failures}
    assert DataQualityIssueType.UNKNOWN_METRIC_DEFINITION in issue_types


def test_validate_extraction_record_normalised_without_raw_routes_to_data_quality(
    metric_registry,
) -> None:
    record = _base_record(raw_value="", normalised_numeric_value=42.0)
    failures = rules_ingestion.validate_extraction_record(record, metric_registry=metric_registry)
    issue_types = {issue_type for issue_type, _ in failures}
    assert DataQualityIssueType.NORMALISED_VALUE_WITHOUT_RAW_VALUE in issue_types


def test_validate_extraction_record_percentage_outside_range_routes_to_data_quality(
    metric_registry,
) -> None:
    record = _base_record(metric_id="bounce_rate", raw_value="150", normalised_numeric_value=150.0)
    failures = rules_ingestion.validate_extraction_record(record, metric_registry=metric_registry)
    issue_types = {issue_type for issue_type, _ in failures}
    assert DataQualityIssueType.PERCENTAGE_OUTSIDE_0_100 in issue_types


def test_validate_extraction_record_group_only_metric_on_brand_routes_to_data_quality(
    metric_registry,
) -> None:
    # `employees` is defined in the registry as subject_types: [operator]
    # only — recording it against a brand is FR-022's mislabelling case.
    record = _base_record(metric_id="employees", raw_value="500")
    failures = rules_ingestion.validate_extraction_record(record, metric_registry=metric_registry)
    issue_types = {issue_type for issue_type, _ in failures}
    assert DataQualityIssueType.GROUP_FIGURE_INCORRECTLY_LABELLED_AS_BRAND_FIGURE in issue_types


def test_validate_extraction_record_negative_value_where_prohibited(metric_registry) -> None:
    record = _base_record(
        metric_id="revenue",
        raw_value="-100",
        normalised_numeric_value=-100.0,
        subject={"type": "operator", "id": "operator_1"},
    )
    failures = rules_ingestion.validate_extraction_record(
        record, metric_registry=metric_registry, negative_prohibited_metrics=frozenset({"revenue"})
    )
    issue_types = {issue_type for issue_type, _ in failures}
    assert DataQualityIssueType.NEGATIVE_VALUE_WHERE_PROHIBITED in issue_types


def test_validate_not_stale_flags_old_as_of_date() -> None:
    import datetime as dt

    failures = rules_ingestion.validate_not_stale("2020-01-01", today=dt.date(2026, 7, 24))
    assert failures and failures[0][0] == DataQualityIssueType.STALE_OBSERVATION


def test_validate_not_stale_accepts_recent_as_of_date() -> None:
    import datetime as dt

    failures = rules_ingestion.validate_not_stale("2026-07-01", today=dt.date(2026, 7, 24))
    assert failures == []


def test_validate_no_conflicting_high_confidence_flags_material_disagreement() -> None:
    failures = rules_ingestion.validate_no_conflicting_high_confidence(
        1_500_000.0, [1_000_000.0], metric_id="estimated_monthly_visits"
    )
    assert (
        failures and failures[0][0] == DataQualityIssueType.CONFLICTING_HIGH_CONFIDENCE_OBSERVATIONS
    )


def test_validate_no_conflicting_high_confidence_allows_matching_values() -> None:
    failures = rules_ingestion.validate_no_conflicting_high_confidence(
        1_000_000.0, [1_000_000.0], metric_id="estimated_monthly_visits"
    )
    assert failures == []
