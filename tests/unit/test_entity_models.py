from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from casino_intel.models.brand import Brand
from casino_intel.models.ids import new_id
from casino_intel.models.observation import Observation
from casino_intel.models.operator import Operator
from casino_intel.models.source import AccessDeniedError, Source
from casino_intel.models.vocab import BrandType, EvidenceType, SourceType, SubjectType


def _now() -> datetime:
    return datetime(2026, 7, 24, tzinfo=UTC)


def test_operator_and_brand_construct_and_link():
    operator = Operator(
        record_id=new_id("operator"),
        created_at=_now(),
        created_by="tester",
        updated_at=_now(),
        operator_name="Example Group plc",
    )
    brand = Brand(
        record_id=new_id("brand"),
        created_at=_now(),
        created_by="tester",
        updated_at=_now(),
        brand_name="Example Casino",
        operator_id=operator.record_id,
        primary_domain="example-casino.example",
        brand_type=BrandType.CASINO_ONLY,
        sampling_rationale="Challenger casino-only brand, mid traffic tier.",
    )
    assert brand.operator_id == operator.record_id


def test_brand_rejects_out_of_range_research_priority():
    with pytest.raises(ValidationError):
        Brand(
            record_id=new_id("brand"),
            created_at=_now(),
            created_by="tester",
            updated_at=_now(),
            brand_name="Example Casino",
            operator_id=new_id("operator"),
            primary_domain="example-casino.example",
            brand_type=BrandType.CASINO_ONLY,
            research_priority=9,
        )


def test_source_assert_fetchable_blocks_paywalled_sources():
    source = Source(
        record_id=new_id("source"),
        created_at=_now(),
        created_by="tester",
        updated_at=_now(),
        source_type=SourceType.REVIEW_PLATFORM,
        url="https://example.com/paywalled-report",
        paywalled=True,
    )
    with pytest.raises(AccessDeniedError):
        source.assert_fetchable()


def test_source_assert_fetchable_allows_open_sources():
    source = Source(
        record_id=new_id("source"),
        created_at=_now(),
        created_by="tester",
        updated_at=_now(),
        source_type=SourceType.REGULATOR_STATISTICS,
        url="https://example.gov/stats",
    )
    source.assert_fetchable()  # should not raise


def test_observation_derived_requires_formula_and_inputs():
    with pytest.raises(ValidationError):
        Observation(
            record_id=new_id("observation"),
            created_at=_now(),
            created_by="tester",
            updated_at=_now(),
            source_id=new_id("source"),
            evidence_type=EvidenceType.DERIVED,
            subject_type=SubjectType.BRAND,
            subject_id=new_id("brand"),
            metric_id="revenue_per_active_customer",
            raw_value="42.0",
        )


def test_observation_currency_conversion_requires_fx_fields():
    with pytest.raises(ValidationError):
        Observation(
            record_id=new_id("observation"),
            created_at=_now(),
            created_by="tester",
            updated_at=_now(),
            source_id=new_id("source"),
            subject_type=SubjectType.OPERATOR,
            subject_id=new_id("operator"),
            metric_id="revenue",
            raw_value="450000000",
            currency="EUR",
            normalised_currency="GBP",
        )


def test_observation_valid_currency_conversion_succeeds():
    obs = Observation(
        record_id=new_id("observation"),
        created_at=_now(),
        created_by="tester",
        updated_at=_now(),
        source_id=new_id("source"),
        subject_type=SubjectType.OPERATOR,
        subject_id=new_id("operator"),
        metric_id="revenue",
        raw_value="450000000",
        currency="EUR",
        normalised_currency="GBP",
        fx_rate=0.86,
        fx_rate_date="2026-06-30",
    )
    assert obs.fx_rate == 0.86
