"""Common record fields shared by every entity (source doc §6, data-model.md).

`Record` is the base every domain model inherits from. It encodes the
identity, provenance and evidence fields that must appear "where applicable"
on every table, plus the state-transition rules for `status`/`review_status`.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from casino_intel.models.vocab import (
    RECORD_STATUS_TRANSITIONS,
    REVIEW_STATUS_TRANSITIONS,
    Confidence,
    EvidenceType,
    RecordStatus,
    ReviewStatus,
)


class InvalidStatusTransition(ValueError):
    """Raised when a status/review_status change is not a legal transition."""


class Record(BaseModel):
    """Base fields common to every entity in the workbook."""

    model_config = ConfigDict(use_enum_values=False, validate_assignment=True)

    record_id: str
    created_at: datetime
    created_by: str
    updated_at: datetime
    status: RecordStatus = RecordStatus.ACTIVE
    notes: str = ""

    # Provenance / evidence (source doc §6-§7). Optional at the base level
    # because Source/Document records do not cite themselves; subclasses that
    # represent facts (Observation and the domain views) require these.
    source_id: str | None = None
    document_id: str | None = None
    evidence_type: EvidenceType = EvidenceType.UNKNOWN
    confidence: Confidence = Confidence.UNKNOWN
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    captured_at: datetime | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    period_start: date | None = None
    period_end: date | None = None

    def transition_status(self, new_status: RecordStatus) -> None:
        """Move `status` to `new_status`, enforcing the legal-transition graph."""
        allowed = RECORD_STATUS_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidStatusTransition(
                f"Cannot transition status from {self.status!r} to {new_status!r}"
            )
        self.status = new_status

    def transition_review_status(self, new_review_status: ReviewStatus) -> None:
        """Move `review_status` forward, enforcing the legal-transition graph."""
        allowed = REVIEW_STATUS_TRANSITIONS.get(self.review_status, set())
        if new_review_status not in allowed:
            raise InvalidStatusTransition(
                f"Cannot transition review_status from "
                f"{self.review_status!r} to {new_review_status!r}"
            )
        self.review_status = new_review_status

    @field_validator("valid_to")
    @classmethod
    def _valid_to_after_valid_from(cls, v: date | None, info) -> date | None:
        valid_from = info.data.get("valid_from")
        if v is not None and valid_from is not None and v < valid_from:
            raise ValueError("valid_to must not be before valid_from")
        return v

    @field_validator("period_end")
    @classmethod
    def _period_end_after_period_start(cls, v: date | None, info) -> date | None:
        period_start = info.data.get("period_start")
        if v is not None and period_start is not None and v < period_start:
            raise ValueError("period_end must not be before period_start")
        return v
