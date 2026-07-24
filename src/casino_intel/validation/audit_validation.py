"""Score-requires-rationale validation for UX/brand audits (spec FR-031, T076).

"A score without rationale is invalid" (spec Edge Cases): any populated
`<dimension>_score` field must have a non-empty, non-whitespace paired
`<dimension>_score_rationale` field, or the save is rejected outright — this
is a hard validation error, not a soft Data Quality flag.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from casino_intel.models.vocab import DataQualityIssueType

Failure = tuple[DataQualityIssueType, str]


class AuditValidationError(ValueError):
    """Raised when one or more populated scores lack a required rationale."""

    def __init__(self, failures: list[Failure]) -> None:
        self.failures = failures
        super().__init__("; ".join(desc for _, desc in failures))


def validate_score_rationale_pairs(
    data: dict[str, Any], score_fields: Iterable[str]
) -> list[Failure]:
    """Return one failure per populated `*_score` field lacking a non-empty
    paired `*_score_rationale` field. Score fields not present/None/"" are
    treated as not-yet-scored and require no rationale."""
    failures: list[Failure] = []
    for score_field in score_fields:
        score_value = data.get(score_field)
        if score_value is None or score_value == "":
            continue
        rationale_field = f"{score_field}_rationale"
        rationale_value = data.get(rationale_field)
        if not (isinstance(rationale_value, str) and rationale_value.strip()):
            failures.append(
                (
                    DataQualityIssueType.SUBJECTIVE_SCORE_WITHOUT_RATIONALE,
                    f"{score_field}={score_value!r} is set but {rationale_field!r} is "
                    "empty — a score without rationale is invalid (FR-031)",
                )
            )
    return failures


def assert_scores_have_rationales(data: dict[str, Any], score_fields: Iterable[str]) -> None:
    """Raise `AuditValidationError` (rejecting the save) if any populated
    score lacks its paired rationale."""
    failures = validate_score_rationale_pairs(data, score_fields)
    if failures:
        raise AuditValidationError(failures)
