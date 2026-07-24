import pytest

from casino_intel.services.observation_service import ObservationInput, ObservationService
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation.data_quality import DataQualityWriter

METRICS_PATH = "config/metrics.yaml"


@pytest.fixture
def metric_registry():
    return MetricRegistry(METRICS_PATH)


@pytest.fixture
def data_quality_writer(sheets_client, fake_service):
    fake_service.add_sheet(
        "Data Quality",
        [
            "issue_id",
            "detected_at",
            "severity",
            "issue_type",
            "sheet_name",
            "record_id",
            "field_name",
            "description",
            "suggested_fix",
            "assigned_to",
            "status",
            "resolved_at",
        ],
    )
    return DataQualityWriter(sheets_client)


@pytest.fixture
def observation_service(sheets_writer, data_quality_writer, metric_registry):
    return ObservationService(sheets_writer, data_quality_writer, metric_registry)


@pytest.fixture(autouse=True)
def _observations_sheet(fake_service):
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])


def _base_input(**overrides):
    defaults = dict(
        subject_type="brand",
        subject_id="brand_1",
        metric_id="estimated_monthly_visits",
        raw_value="1,200,000",
        source_id="source_1",
        evidence_type="third_party_estimate",
        confidence="medium",
        period_start="2026-06-01",
        period_end="2026-06-30",
        geography="GB",
    )
    defaults.update(overrides)
    return ObservationInput(**defaults)


def test_record_observation_appends_row(observation_service, fake_service):
    result = observation_service.record_observation(_base_input(), actor="tester")
    assert result is not None and result.written
    assert len(fake_service.sheets["Observations"]) == 2  # header + 1 row


def test_record_observation_is_append_only_across_two_dated_captures(
    observation_service, fake_service
):
    """User Story 1 independent test: two dated observations for the same
    brand/metric both persist without overwrite."""
    observation_service.record_observation(
        _base_input(raw_value="1,000,000", period_start="2026-05-01", period_end="2026-05-31"),
        actor="tester",
    )
    observation_service.record_observation(
        _base_input(raw_value="1,200,000", period_start="2026-06-01", period_end="2026-06-30"),
        actor="tester",
    )
    assert len(fake_service.sheets["Observations"]) == 3  # header + 2 distinct-period rows


def test_record_observation_deduplicates_identical_refetch(observation_service, fake_service):
    observation_service.record_observation(_base_input(), actor="tester")
    result = observation_service.record_observation(_base_input(), actor="tester")
    assert result.duplicate
    assert len(fake_service.sheets["Observations"]) == 2  # still just one data row


def test_record_observation_retains_conflicting_sources_separately(
    observation_service, fake_service
):
    """Two different sources reporting different values for the same
    brand/metric/period must both be retained (spec Edge Cases)."""
    observation_service.record_observation(
        _base_input(raw_value="1,000,000", source_id="source_1"), actor="tester"
    )
    observation_service.record_observation(
        _base_input(raw_value="1,500,000", source_id="source_2"), actor="tester"
    )
    assert len(fake_service.sheets["Observations"]) == 3  # both retained


def test_record_observation_unknown_metric_routes_to_data_quality(
    observation_service, fake_service
):
    result = observation_service.record_observation(
        _base_input(metric_id="not_a_real_metric"), actor="tester"
    )
    assert result is None
    assert len(fake_service.sheets["Observations"]) == 1  # header only — nothing written
    assert len(fake_service.sheets["Data Quality"]) == 2  # header + 1 issue
    assert fake_service.sheets["Data Quality"][1][3] == "unknown_metric_definition"


def test_record_observation_missing_source_routes_to_data_quality(
    observation_service, fake_service
):
    result = observation_service.record_observation(_base_input(source_id=""), actor="tester")
    assert result is None
    assert fake_service.sheets["Data Quality"][1][3] == "missing_source"


def test_record_observation_currency_conversion_retains_raw_and_normalised(
    observation_service, fake_service
):
    result = observation_service.record_observation(
        _base_input(
            metric_id="revenue",
            subject_type="operator",
            subject_id="operator_1",
            raw_value="450000000",
            normalised_numeric_value=450_000_000,
            currency="EUR",
            evidence_type="reported_primary",
            confidence="high",
            as_of_date="2026-06-30",
        ),
        actor="tester",
    )
    assert result.written
    row = fake_service.sheets["Observations"][1]
    header = SHEET_HEADERS["Observations"]
    as_dict = dict(zip(header, row, strict=False))
    assert as_dict["currency"] == "EUR"
    assert as_dict["normalised_currency"] == "GBP"
    assert as_dict["raw_value"] == "450000000"
    assert float(as_dict["fx_rate"]) == pytest.approx(0.86)
