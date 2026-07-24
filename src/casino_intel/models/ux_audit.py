"""UXAudit entity (data-model.md "Entity: UXAudit", spec FR-031-FR-034,
source doc §9.14/§13).

One row per brand/device/geography/date. Every populated `*_score` field
must carry a non-empty paired `*_score_rationale` (FR-031), and no field may
ever describe a completed KYC submission or deposit — only that the
corresponding prompt/step was reached (FR-033, FR-046).
"""

from __future__ import annotations

from pydantic import Field, model_validator

from casino_intel.models.base import Record
from casino_intel.models.capture_environment import CookieState, DeviceType, VisitorState
from casino_intel.services.journey_safety import assert_no_completion_language
from casino_intel.validation.audit_validation import assert_scores_have_rationales

#: Rubric dimension score fields — must match `config/audit-rubrics.yaml`
#: `ux_audit_dimensions` keys exactly (asserted by
#: tests/unit/test_rubric_service.py).
UX_SCORE_FIELDS: tuple[str, ...] = (
    "game_discovery_score",
    "search_quality_score",
    "navigation_clarity_score",
    "promotion_clarity_score",
    "trust_signal_score",
    "responsible_gambling_score",
    "accessibility_score",
    "mobile_usability_score",
    "visual_clutter_score",
    "performance_score",
    "overall_ux_score",
)


class UXAudit(Record):
    brand_id: str
    audit_date: str | None = None
    auditor: str = ""

    geography: str = "GB"
    device_type: DeviceType = DeviceType.DESKTOP
    viewport: str = ""
    logged_in_state: bool = False
    new_or_returning_visitor: VisitorState = VisitorState.NEW
    cookie_state: CookieState = CookieState.ACCEPTED
    homepage_url: str = ""

    registration_steps: int = 0
    registration_fields: list[str] = Field(default_factory=list)
    registration_required_fields: list[str] = Field(default_factory=list)

    #: Records only that the KYC prompt/stage was *reached* during the
    #: guided journey — never that identity documents were actually
    #: submitted (FR-033/FR-046). Validated below.
    kyc_requested_at: str = ""
    #: Number of deposit-flow steps reached before the guided journey
    #: stopped — never a record of funds actually being deposited.
    deposit_steps: int = 0

    game_discovery_score: int | None = None
    game_discovery_score_rationale: str = ""
    search_quality_score: int | None = None
    search_quality_score_rationale: str = ""
    navigation_clarity_score: int | None = None
    navigation_clarity_score_rationale: str = ""
    promotion_clarity_score: int | None = None
    promotion_clarity_score_rationale: str = ""
    trust_signal_score: int | None = None
    trust_signal_score_rationale: str = ""
    responsible_gambling_score: int | None = None
    responsible_gambling_score_rationale: str = ""
    accessibility_score: int | None = None
    accessibility_score_rationale: str = ""
    mobile_usability_score: int | None = None
    mobile_usability_score_rationale: str = ""
    visual_clutter_score: int | None = None
    visual_clutter_score_rationale: str = ""
    performance_score: int | None = None
    performance_score_rationale: str = ""
    overall_ux_score: int | None = None
    overall_ux_score_rationale: str = ""

    screen_recording_document_id: str | None = None
    screenshot_set_path: str = ""
    rubric_version: str = ""

    @model_validator(mode="after")
    def _scores_in_range(self) -> UXAudit:
        for field_name in UX_SCORE_FIELDS:
            value = getattr(self, field_name)
            if value is not None and not (1 <= value <= 5):
                raise ValueError(f"{field_name} must be between 1 and 5, got {value}")
        return self

    @model_validator(mode="after")
    def _scores_require_rationale(self) -> UXAudit:
        assert_scores_have_rationales(self.model_dump(), UX_SCORE_FIELDS)
        return self

    @model_validator(mode="after")
    def _kyc_field_never_records_completion(self) -> UXAudit:
        assert_no_completion_language(self.kyc_requested_at, field_name="kyc_requested_at")
        return self
