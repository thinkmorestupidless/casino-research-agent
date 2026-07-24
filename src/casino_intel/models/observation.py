"""The canonical Observation model (data-model.md "Entity: Observation",
spec FR-004/FR-006-FR-008, source doc §9.7).

This is the generic, time-indexed fact table every domain-specific view
(Financials, Traffic, ...) either writes alongside or is generated from.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from casino_intel.models.base import Record
from casino_intel.models.vocab import ComparabilityStatus, EvidenceType, SubjectType


class Observation(Record):
    subject_type: SubjectType
    subject_id: str
    metric_id: str

    raw_value: str
    raw_unit: str = ""
    normalised_numeric_value: float | None = None
    normalised_text_value: str = ""
    normalised_unit: str = ""

    currency: str = ""
    normalised_currency: str = ""
    fx_rate: float | None = None
    fx_rate_date: str | None = None

    as_of_date: str | None = None
    geography: str = ""
    segment: str = ""

    source_locator: str = ""
    verbatim_excerpt: str = Field(default="", max_length=500)

    definition_id: str = ""
    comparability_group: str = ""
    comparability_status: ComparabilityStatus = ComparabilityStatus.UNKNOWN

    calculation_formula: str = ""
    input_observation_ids: list[str] = Field(default_factory=list)
    methodology_note: str = ""

    #: Computed by validation/fingerprint.py at write time — not hand-set.
    fingerprint: str = ""

    @model_validator(mode="after")
    def _derived_requires_formula_and_inputs(self) -> Observation:
        """FR-023/data-model.md: a derived observation must carry its
        formula and non-empty input lineage — enforced at the model level
        so it can never slip through even if a caller forgets the
        ingestion-time validator (data_quality.py raises the DQ issue
        separately for machine-extracted candidates that fail this)."""
        if self.evidence_type == EvidenceType.DERIVED:
            if not self.calculation_formula or not self.input_observation_ids:
                raise ValueError(
                    "evidence_type=derived requires calculation_formula and "
                    "a non-empty input_observation_ids"
                )
        return self

    @model_validator(mode="after")
    def _fx_fields_required_together(self) -> Observation:
        if self.currency and self.normalised_currency and self.currency != self.normalised_currency:
            if self.fx_rate is None or not self.fx_rate_date:
                raise ValueError("A currency conversion requires both fx_rate and fx_rate_date")
        return self
