"""Audit-rubric loader tests (T075) — also guards against drift between
`config/audit-rubrics.yaml` and the hardcoded score-field tuples in
`models/ux_audit.py` / `models/brand_audit.py` / `services/journey_safety.py`.
"""

from __future__ import annotations

from casino_intel.models.brand_audit import BRAND_SCORE_FIELDS
from casino_intel.models.ux_audit import UX_SCORE_FIELDS
from casino_intel.services.journey_safety import RESTRICTED_ACTIONS
from casino_intel.services.rubric_service import RubricService

RUBRICS_PATH = "config/audit-rubrics.yaml"


def test_loads_rubric_version():
    service = RubricService(RUBRICS_PATH)
    assert service.rubric_version == "2026.07.1"


def test_ux_score_fields_match_the_model():
    service = RubricService(RUBRICS_PATH)
    assert set(service.ux_score_fields()) == set(UX_SCORE_FIELDS)


def test_brand_score_fields_match_the_model():
    service = RubricService(RUBRICS_PATH)
    assert set(service.brand_score_fields()) == set(BRAND_SCORE_FIELDS)


def test_journey_safety_stop_points_match_the_guard():
    service = RubricService(RUBRICS_PATH)
    assert set(service.journey_safety_stop_points) == set(RESTRICTED_ACTIONS)


def test_scale_lookup_for_a_ux_dimension():
    service = RubricService(RUBRICS_PATH)
    assert service.scale_for_ux_dimension("promotion_clarity_score") == (1, 5)


def test_scale_lookup_for_a_brand_dimension():
    service = RubricService(RUBRICS_PATH)
    assert service.scale_for_brand_dimension("premium_score") == (1, 5)
