"""Extraction-record model matching `contracts/extraction-record.schema.json`
verbatim (source doc §11.5). This is the internal contract every
parser/extractor (HTML, PDF, XLSX/CSV) emits, and every
normalisation/validation stage consumes — independent parser
implementations must all produce this shape identically.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_GEOGRAPHY_PATTERN = re.compile(r"^[A-Z]{2}$")

SubjectTypeLiteral = Literal["brand", "operator", "market", "licence", "offer", "app"]
EvidenceTypeLiteral = Literal[
    "reported_primary",
    "reported_secondary",
    "derived",
    "third_party_estimate",
    "direct_observation",
    "subjective_audit",
    "inferred_range",
    "unknown",
]
ConfidenceLiteral = Literal["high", "medium", "low", "unknown"]
ComparabilityStatusLiteral = Literal[
    "comparable", "partially_comparable", "not_comparable", "unknown"
]


class ExtractionSubject(BaseModel):
    """The fact's subject — extractors MUST NOT invent a new subject id;
    an unresolved subject is routed to Data Quality instead of guessed."""

    model_config = ConfigDict(extra="forbid")

    type: SubjectTypeLiteral
    id: str


class ExtractionRecord(BaseModel):
    """One candidate fact emitted by a parser/extractor, always
    ``review_status="unreviewed"`` (FR-017: no extractor self-approves)."""

    model_config = ConfigDict(extra="forbid")

    subject: ExtractionSubject
    metric_id: str
    raw_value: str
    raw_unit: str = ""

    normalised_numeric_value: float | None = None
    normalised_text_value: str | None = None
    normalised_unit: str | None = None

    currency: str | None = None
    normalised_currency: str | None = None
    fx_rate: float | None = Field(default=None, gt=0)
    fx_rate_date: str | None = None

    period_start: str | None = None
    period_end: str | None = None
    as_of_date: str | None = None

    geography: str | None = None
    segment: str | None = None

    source_id: str
    document_id: str | None = None
    source_locator: str
    verbatim_excerpt: str | None = Field(default=None, max_length=500)

    evidence_type: EvidenceTypeLiteral
    confidence: ConfidenceLiteral

    definition_id: str | None = None
    comparability_status: ComparabilityStatusLiteral | None = None
    methodology_note: str | None = None

    #: Extractors MUST always emit unreviewed — enforced as a fixed default
    #: rather than a caller-supplied value.
    review_status: Literal["unreviewed"] = "unreviewed"

    @field_validator("currency", "normalised_currency")
    @classmethod
    def _validate_currency(cls, v: str | None) -> str | None:
        if v is not None and not _CURRENCY_PATTERN.match(v):
            raise ValueError(f"{v!r} is not a 3-letter ISO 4217 currency code")
        return v

    @field_validator("geography")
    @classmethod
    def _validate_geography(cls, v: str | None) -> str | None:
        if v is not None and not _GEOGRAPHY_PATTERN.match(v):
            raise ValueError(f"{v!r} is not a 2-letter ISO 3166-1 alpha-2 code")
        return v

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        if not v.startswith("source_"):
            raise ValueError(f"source_id {v!r} must start with 'source_'")
        return v

    @field_validator("document_id")
    @classmethod
    def _validate_document_id(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("document_"):
            raise ValueError(f"document_id {v!r} must start with 'document_'")
        return v
