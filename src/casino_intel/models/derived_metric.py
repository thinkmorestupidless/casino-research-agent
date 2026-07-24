"""The DerivedMetric model (data-model.md "Entity: DerivedMetric",
spec FR-035-FR-037, source doc §9.18).

Unlike every other entity in this codebase, `DerivedMetric` does NOT inherit
from `Record` — it has its own flat field list matching the `Derived
Metrics` sheet exactly (see `sheets/schema_definitions.py`'s
``SHEET_HEADERS["Derived Metrics"]``), not the generic provenance fields
every other tab shares.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from casino_intel.models.vocab import ComparabilityStatus, Confidence, ReviewStatus, SubjectType


class DerivedMetric(BaseModel):
    """One calculated result (FR-035). A row here always carries enough
    lineage — exact `input_observation_ids`, the literal `formula` string,
    and `formula_version` — for a human to verify it by hand."""

    model_config = ConfigDict(use_enum_values=False, validate_assignment=True)

    derived_metric_id: str
    subject_type: SubjectType
    subject_id: str
    metric_id: str

    period_start: date | None = None
    period_end: date | None = None

    value: float
    unit: str = ""

    formula_version: str
    formula: str

    #: Required, non-empty (FR-035/data-model.md): a derived metric with no
    #: lineage is a `derived_metric_without_inputs` data-quality violation.
    input_observation_ids: list[str] = Field(default_factory=list)
    assumptions: str = ""

    confidence: Confidence = Confidence.UNKNOWN
    comparability_status: ComparabilityStatus = ComparabilityStatus.UNKNOWN

    calculated_at: datetime
    calculated_by: str

    #: A derived row is always produced by the compatibility-gated engine
    #: (never hand-authored), so it starts past `unreviewed` — a machine
    #: check (the compatibility gate) has already run by construction.
    review_status: ReviewStatus = ReviewStatus.MACHINE_CHECKED

    @field_validator("input_observation_ids")
    @classmethod
    def _requires_lineage(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError(
                "DerivedMetric.input_observation_ids must be non-empty — a "
                "derived metric with no lineage is invalid (FR-035)"
            )
        return v

    @field_validator("period_end")
    @classmethod
    def _period_end_after_period_start(cls, v: date | None, info) -> date | None:
        period_start = info.data.get("period_start")
        if v is not None and period_start is not None and v < period_start:
            raise ValueError("period_end must not be before period_start")
        return v
