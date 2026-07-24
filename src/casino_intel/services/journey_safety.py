"""Journey-safety guard (spec FR-033, FR-046; `config/audit-rubrics.yaml`
`journey_safety_stop_points`).

No automated or guided research journey may ever proceed through, or be
*recorded* as having completed, an action reserved for a real customer:
submitting identity documents, accepting legally binding terms on the
researcher's behalf, depositing funds, placing a wager, or withdrawing
funds. An audit may only record that such a step was *reached* (a prompt
appeared) — never that it was carried out.

This is a hard safety boundary, not an advisory check: every function here
raises rather than warns, and `fetching/audit_capture.py` /
`models/ux_audit.py` both call into it so the guarantee holds regardless of
which entry point (Playwright-assisted or manual) produced the audit.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

#: Mirrors `config/audit-rubrics.yaml` `journey_safety_stop_points` exactly.
#: Kept as a plain constant (rather than loaded from YAML at import time) so
#: this module has no I/O and can be imported anywhere — including from
#: Pydantic model modules — without a config-loading dependency.
#: `tests/unit/test_journey_safety.py` asserts the two stay in sync.
RESTRICTED_ACTIONS: frozenset[str] = frozenset(
    {
        "submitting_identity_documents",
        "accepting_binding_terms_on_behalf_of_researcher",
        "depositing_funds",
        "placing_a_wager",
        "withdrawing_funds",
    }
)

#: The only stages a guided/automated capture may ever visit (source doc §13.2).
PERMITTED_CAPTURE_STAGES: tuple[str, ...] = (
    "homepage",
    "lobby",
    "promotions",
    "registration_up_to_stop_point",
    "footer_licence",
    "responsible_gambling",
)

#: Words that, if found describing a journey stage, imply the restricted
#: action was actually carried out rather than merely reached/prompted.
_COMPLETION_LANGUAGE: tuple[str, ...] = (
    "submitted",
    "completed",
    "approved",
    "verified",
    "uploaded",
    "deposited",
    "wagered",
    "placed_bet",
    "withdrawn",
    "accepted_terms",
)


class JourneySafetyViolation(ValueError):
    """Raised when a step would represent a completed restricted action."""


def assert_step_not_completed(step_name: str, *, completed: bool) -> None:
    """Hard-block recording `step_name` as completed if it is a restricted
    action. Reaching/prompting a restricted step is fine — completing it is
    never permitted to be recorded (FR-033/FR-046)."""
    if completed and step_name in RESTRICTED_ACTIONS:
        raise JourneySafetyViolation(
            f"Refusing to record {step_name!r} as completed — audits may only record "
            "that a restricted step was reached, never that it was completed "
            "(FR-033, FR-046)."
        )


def guard_journey(steps: Iterable[tuple[str, bool]]) -> None:
    """Batch form of `assert_step_not_completed` over `(step_name, completed)` pairs."""
    for step_name, completed in steps:
        assert_step_not_completed(step_name, completed=completed)


def stop_before_restricted(stages: Sequence[str]) -> list[str]:
    """Return the prefix of `stages` up to (never including) the first
    restricted stage. This is the mechanism by which a guided/automated
    journey physically stops before the boundary, rather than merely being
    told to (FR-033)."""
    allowed: list[str] = []
    for stage in stages:
        if stage in RESTRICTED_ACTIONS:
            break
        allowed.append(stage)
    return allowed


def assert_no_completion_language(value: str, *, field_name: str) -> None:
    """Reject free-text journey-stage values implying a restricted action was
    completed rather than merely reached (guards fields like
    `UXAudit.kyc_requested_at`, which must record only that a prompt
    appeared)."""
    lowered = (value or "").lower()
    for word in _COMPLETION_LANGUAGE:
        if word in lowered:
            raise JourneySafetyViolation(
                f"{field_name}={value!r} implies a restricted action was completed "
                f"(matched {word!r}) — only 'reached' language is permitted (FR-033, FR-046)."
            )
