"""Journey-safety guard tests (spec FR-033/FR-046).

The guard is a hard safety boundary: it must actively raise, not just log a
warning, whenever a step that represents a completed restricted action
(KYC submission, deposit, wager, withdrawal, binding terms acceptance) is
about to be recorded.
"""

from __future__ import annotations

import pytest

from casino_intel.services.journey_safety import (
    PERMITTED_CAPTURE_STAGES,
    RESTRICTED_ACTIONS,
    JourneySafetyViolation,
    assert_no_completion_language,
    assert_step_not_completed,
    guard_journey,
    stop_before_restricted,
)


@pytest.mark.parametrize("action", sorted(RESTRICTED_ACTIONS))
def test_completed_restricted_action_is_blocked(action):
    """The guard actually raises — it does not silently allow or merely warn."""
    with pytest.raises(JourneySafetyViolation):
        assert_step_not_completed(action, completed=True)


@pytest.mark.parametrize("action", sorted(RESTRICTED_ACTIONS))
def test_reaching_a_restricted_action_without_completing_is_allowed(action):
    """Recording that a restricted step was *reached* (prompt shown) is fine."""
    assert_step_not_completed(action, completed=False)  # must not raise


def test_non_restricted_step_can_be_marked_completed():
    assert_step_not_completed("homepage", completed=True)  # must not raise


def test_guard_journey_blocks_any_completed_restricted_step_in_a_batch():
    steps = [("homepage", False), ("lobby", False), ("depositing_funds", True)]
    with pytest.raises(JourneySafetyViolation):
        guard_journey(steps)


def test_guard_journey_allows_a_batch_with_no_completed_restricted_steps():
    steps = [("homepage", True), ("lobby", True), ("depositing_funds", False)]
    guard_journey(steps)  # must not raise


def test_stop_before_restricted_halts_before_the_boundary():
    stages = ["homepage", "lobby", "depositing_funds", "placing_a_wager"]
    assert stop_before_restricted(stages) == ["homepage", "lobby"]


def test_stop_before_restricted_never_includes_a_restricted_stage():
    for action in RESTRICTED_ACTIONS:
        assert action not in stop_before_restricted(["homepage", action, "lobby"])


def test_permitted_capture_stages_contain_no_restricted_action():
    assert not (set(PERMITTED_CAPTURE_STAGES) & RESTRICTED_ACTIONS)


def test_completion_language_in_kyc_field_is_rejected():
    with pytest.raises(JourneySafetyViolation):
        assert_no_completion_language("identity_documents_submitted", field_name="kyc_requested_at")


def test_reached_language_in_kyc_field_is_accepted():
    assert_no_completion_language(
        "prompt_reached_before_first_deposit", field_name="kyc_requested_at"
    )
