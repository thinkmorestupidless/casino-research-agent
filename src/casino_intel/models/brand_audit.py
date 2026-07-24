"""BrandAudit entity (data-model.md "Entity: BrandAudit", spec FR-031/FR-034,
source doc §9.15/§13).

One row per brand/date, capturing a structured visual/tone/positioning
assessment. Every populated `*_score` field must carry a non-empty paired
`*_score_rationale` (FR-031), and `brand_rationale` is always required,
mirroring UXAudit's rationale rule (data-model.md).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from casino_intel.models.base import Record
from casino_intel.validation.audit_validation import assert_scores_have_rationales


class IntensityLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


#: Rubric dimension score fields — must match `config/audit-rubrics.yaml`
#: `brand_audit_dimensions` keys exactly (asserted by
#: tests/unit/test_rubric_service.py).
BRAND_SCORE_FIELDS: tuple[str, ...] = (
    "premium_score",
    "playful_score",
    "trustworthy_score",
    "traditional_score",
    "crypto_native_score",
    "sports_led_score",
    "bonus_led_score",
    "distinctiveness_score",
    "coherence_score",
)


class BrandAudit(Record):
    brand_id: str
    audit_date: str | None = None
    auditor: str = ""

    primary_colour: str = ""
    secondary_colours: list[str] = Field(default_factory=list)
    background_style: str = ""
    typography_style: str = ""
    logo_type: str = ""
    mascot_present: bool = False
    photography_present: bool = False
    illustration_present: bool = False
    animation_intensity: IntensityLevel = IntensityLevel.LOW
    visual_density: IntensityLevel = IntensityLevel.MEDIUM

    tone_of_voice: str = ""
    primary_tagline: str = ""
    primary_proposition: str = ""
    target_audience_hypothesis: str = ""

    premium_score: int | None = None
    premium_score_rationale: str = ""
    playful_score: int | None = None
    playful_score_rationale: str = ""
    trustworthy_score: int | None = None
    trustworthy_score_rationale: str = ""
    traditional_score: int | None = None
    traditional_score_rationale: str = ""
    crypto_native_score: int | None = None
    crypto_native_score_rationale: str = ""
    sports_led_score: int | None = None
    sports_led_score_rationale: str = ""
    bonus_led_score: int | None = None
    bonus_led_score_rationale: str = ""
    distinctiveness_score: int | None = None
    distinctiveness_score_rationale: str = ""
    coherence_score: int | None = None
    coherence_score_rationale: str = ""

    #: Required overall rationale for the audit, regardless of which
    #: individual dimensions were scored (data-model.md: "mirrors UXAudit's
    #: rationale rule").
    brand_rationale: str = ""

    screenshot_set_path: str = ""
    rubric_version: str = ""

    @model_validator(mode="after")
    def _scores_in_range(self) -> BrandAudit:
        for field_name in BRAND_SCORE_FIELDS:
            value = getattr(self, field_name)
            if value is not None and not (1 <= value <= 5):
                raise ValueError(f"{field_name} must be between 1 and 5, got {value}")
        return self

    @model_validator(mode="after")
    def _scores_require_rationale(self) -> BrandAudit:
        assert_scores_have_rationales(self.model_dump(), BRAND_SCORE_FIELDS)
        return self

    @model_validator(mode="after")
    def _brand_rationale_required(self) -> BrandAudit:
        if not self.brand_rationale.strip():
            raise ValueError("brand_rationale is required for every brand audit (FR-031)")
        return self
