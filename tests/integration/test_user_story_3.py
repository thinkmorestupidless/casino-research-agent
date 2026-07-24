"""User Story 3 independent test (quickstart.md Step 8): complete one UX
audit and one brand audit end-to-end via the CLI, confirm a missing
rationale is rejected, and confirm no restricted-action step is ever
recorded as completed (spec FR-031-FR-034, FR-033, FR-046)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.services.journey_safety import JourneySafetyViolation, assert_step_not_completed
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

runner = CliRunner()

UX_SCORES = {
    "game_discovery_score": {"score": 4, "rationale": "Slots findable via search in two clicks."},
    "search_quality_score": {"score": 3, "rationale": "Search surfaces near-matches, no synonyms."},
    "navigation_clarity_score": {"score": 4, "rationale": "Primary nav labels match content."},
    "promotion_clarity_score": {"score": 5, "rationale": "Offer and wagering terms both visible."},
    "trust_signal_score": {"score": 4, "rationale": "Licence badge visible above the fold."},
    "responsible_gambling_score": {"score": 3, "rationale": "RG link present in footer only."},
    "accessibility_score": {"score": 3, "rationale": "Adequate contrast; no skip-nav link."},
    "mobile_usability_score": {"score": 4, "rationale": "Mobile nav collapses cleanly."},
    "visual_clutter_score": {"score": 3, "rationale": "Homepage carousel adds visual noise."},
    "performance_score": {"score": 4, "rationale": "Homepage interactive within ~2s."},
    "overall_ux_score": {"score": 4, "rationale": "Above-average clarity, minor RG gap."},
}

BRAND_SCORES = {
    "premium_score": {"score": 4, "rationale": "Muted palette, minimal promo noise."},
    "playful_score": {"score": 2, "rationale": "Tone is measured, not playful."},
    "trustworthy_score": {"score": 4, "rationale": "Licence and security marks prominent."},
    "traditional_score": {"score": 3, "rationale": "Classic iconography, not overly modern."},
    "crypto_native_score": {"score": 1, "rationale": "No crypto payment or branding present."},
    "sports_led_score": {"score": 1, "rationale": "No sportsbook cross-sell visible."},
    "bonus_led_score": {"score": 2, "rationale": "Welcome offer present but not dominant."},
    "distinctiveness_score": {"score": 3, "rationale": "Recognisable but shares cues with rivals."},
    "coherence_score": {"score": 4, "rationale": "Consistent palette/type across pages."},
}


@pytest.fixture(autouse=True)
def _setup(monkeypatch, sheets_client, fake_service):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", ":memory:")
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )
    fake_service.add_sheet("UX Audits", SHEET_HEADERS["UX Audits"])
    fake_service.add_sheet("Brand Audits", SHEET_HEADERS["Brand Audits"])
    fake_service.add_sheet("Data Quality", SHEET_HEADERS["Data Quality"])
    fake_service.add_sheet("Change Log", SHEET_HEADERS["Change Log"])
    return fake_service


def _write_scores_file(tmp_path, name, scores):
    path = tmp_path / name
    path.write_text(json.dumps(scores), encoding="utf-8")
    return str(path)


def test_full_user_story_3_flow(fake_service, tmp_path):
    ux_scores_path = _write_scores_file(tmp_path, "ux_scores.json", UX_SCORES)

    ux_result = runner.invoke(
        app,
        [
            "record-ux-audit",
            "--brand-id",
            "brand_1",
            "--auditor",
            "trevor",
            "--scores-file",
            ux_scores_path,
            "--geography",
            "GB",
            "--device-type",
            "desktop",
            "--viewport",
            "1920x1080",
            "--homepage-url",
            "https://example-casino.example",
            "--logged-out",
            "--kyc-requested-at",
            "prompt_reached_before_deposit",
            "--deposit-steps",
            "1",
        ],
    )
    assert ux_result.exit_code == 0, ux_result.output

    brand_scores_path = _write_scores_file(tmp_path, "brand_scores.json", BRAND_SCORES)
    brand_result = runner.invoke(
        app,
        [
            "record-brand-audit",
            "--brand-id",
            "brand_1",
            "--auditor",
            "trevor",
            "--brand-rationale",
            "Premium, understated identity with strong trust signals.",
            "--scores-file",
            brand_scores_path,
        ],
    )
    assert brand_result.exit_code == 0, brand_result.output

    # Every populated score has a non-empty paired rationale (FR-031).
    ux_header = SHEET_HEADERS["UX Audits"]
    ux_row = dict(zip(ux_header, fake_service.sheets["UX Audits"][1], strict=False))
    for dimension in UX_SCORES:
        assert ux_row[dimension] != ""
        assert ux_row[f"{dimension}_rationale"].strip() != ""
    assert ux_row["rubric_version"] == "2026.07.1"

    brand_header = SHEET_HEADERS["Brand Audits"]
    brand_row = dict(zip(brand_header, fake_service.sheets["Brand Audits"][1], strict=False))
    for dimension in BRAND_SCORES:
        assert brand_row[dimension] != ""
        assert brand_row[f"{dimension}_rationale"].strip() != ""
    assert brand_row["brand_rationale"].strip() != ""
    assert brand_row["rubric_version"] == "2026.07.1"

    # Journey never recorded a completed restricted action: kyc_requested_at
    # only ever describes a *reached* prompt, and deposit_steps is a step
    # count, not a completion flag.
    assert "submitted" not in ux_row["kyc_requested_at"]
    assert "completed" not in ux_row["kyc_requested_at"]


def test_ux_audit_with_missing_rationale_is_rejected(fake_service, tmp_path):
    broken_scores = dict(UX_SCORES)
    broken_scores["trust_signal_score"] = {"score": 4, "rationale": ""}
    scores_path = _write_scores_file(tmp_path, "broken_ux_scores.json", broken_scores)

    result = runner.invoke(
        app,
        [
            "record-ux-audit",
            "--brand-id",
            "brand_1",
            "--auditor",
            "trevor",
            "--scores-file",
            scores_path,
        ],
    )

    assert result.exit_code == 1
    assert "rejected" in result.output.lower()
    assert len(fake_service.sheets["UX Audits"]) == 1  # header only — nothing written


def test_brand_audit_with_missing_rationale_is_rejected(fake_service, tmp_path):
    broken_scores = dict(BRAND_SCORES)
    broken_scores["coherence_score"] = {"score": 4, "rationale": ""}
    scores_path = _write_scores_file(tmp_path, "broken_brand_scores.json", broken_scores)

    result = runner.invoke(
        app,
        [
            "record-brand-audit",
            "--brand-id",
            "brand_1",
            "--auditor",
            "trevor",
            "--brand-rationale",
            "Overall notes present.",
            "--scores-file",
            scores_path,
        ],
    )

    assert result.exit_code == 1
    assert "rejected" in result.output.lower()
    assert len(fake_service.sheets["Brand Audits"]) == 1  # header only — nothing written


def test_ux_audit_rejects_kyc_field_that_claims_completion(fake_service, tmp_path):
    scores_path = _write_scores_file(tmp_path, "ux_scores.json", UX_SCORES)

    result = runner.invoke(
        app,
        [
            "record-ux-audit",
            "--brand-id",
            "brand_1",
            "--auditor",
            "trevor",
            "--scores-file",
            scores_path,
            "--kyc-requested-at",
            "identity_documents_submitted",
        ],
    )

    assert result.exit_code == 1
    assert len(fake_service.sheets["UX Audits"]) == 1


@pytest.mark.parametrize(
    "restricted_action",
    [
        "submitting_identity_documents",
        "accepting_binding_terms_on_behalf_of_researcher",
        "depositing_funds",
        "placing_a_wager",
        "withdrawing_funds",
    ],
)
def test_no_restricted_action_can_ever_be_recorded_as_completed(restricted_action):
    """Hard safety proof (FR-033/FR-046): the journey-safety guard blocks
    every restricted action from being recorded as completed, by name."""
    with pytest.raises(JourneySafetyViolation):
        assert_step_not_completed(restricted_action, completed=True)
