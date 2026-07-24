"""Score-requires-rationale validation tests (spec FR-031, T076).

This is the single most important invariant in User Story 3: a populated
score without a non-empty paired rationale must never be accepted.
"""

from __future__ import annotations

import pytest

from casino_intel.validation.audit_validation import (
    AuditValidationError,
    assert_scores_have_rationales,
    validate_score_rationale_pairs,
)

FIELDS = ("game_discovery_score", "trust_signal_score")


def test_unset_scores_require_no_rationale():
    data = {"game_discovery_score": None, "trust_signal_score": ""}
    assert validate_score_rationale_pairs(data, FIELDS) == []


def test_populated_score_with_rationale_passes():
    data = {
        "game_discovery_score": 4,
        "game_discovery_score_rationale": "Found the target game in two clicks.",
    }
    assert validate_score_rationale_pairs(data, FIELDS) == []


def test_populated_score_without_rationale_fails():
    data = {"game_discovery_score": 4, "game_discovery_score_rationale": ""}
    failures = validate_score_rationale_pairs(data, FIELDS)
    assert len(failures) == 1
    assert failures[0][0].value == "subjective_score_without_rationale"


def test_populated_score_with_whitespace_only_rationale_fails():
    data = {"game_discovery_score": 4, "game_discovery_score_rationale": "   "}
    failures = validate_score_rationale_pairs(data, FIELDS)
    assert len(failures) == 1


def test_populated_score_with_missing_rationale_key_fails():
    data = {"game_discovery_score": 4}
    failures = validate_score_rationale_pairs(data, FIELDS)
    assert len(failures) == 1


def test_multiple_missing_rationales_are_all_reported():
    data = {
        "game_discovery_score": 4,
        "trust_signal_score": 2,
    }
    failures = validate_score_rationale_pairs(data, FIELDS)
    assert len(failures) == 2


def test_assert_scores_have_rationales_raises_and_rejects_the_save():
    data = {"game_discovery_score": 4}
    with pytest.raises(AuditValidationError):
        assert_scores_have_rationales(data, FIELDS)


def test_assert_scores_have_rationales_passes_when_all_satisfied():
    data = {
        "game_discovery_score": 4,
        "game_discovery_score_rationale": "Clear and quick.",
        "trust_signal_score": 5,
        "trust_signal_score_rationale": "Licence badge visible above the fold.",
    }
    assert_scores_have_rationales(data, FIELDS)  # must not raise
