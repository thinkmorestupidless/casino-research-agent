"""Audit-rubric loader (`config/audit-rubrics.yaml`, spec FR-031/FR-034, T075).

Exposes the active `rubric_version` and the UX/brand dimension definitions
so every recorded audit is stamped with the exact rubric version used at
capture time, supporting inter-rater calibration (source doc §13.3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from casino_intel.sheets.config_loader import load_yaml

DEFAULT_RUBRICS_PATH = "config/audit-rubrics.yaml"


class RubricService:
    """In-memory audit-rubric registry loaded from `config/audit-rubrics.yaml`."""

    def __init__(self, path: str | Path = DEFAULT_RUBRICS_PATH) -> None:
        data = load_yaml(path)
        self.rubric_version: str = data["rubric_version"]
        self.ux_audit_dimensions: dict[str, dict[str, Any]] = data.get("ux_audit_dimensions", {})
        self.brand_audit_dimensions: dict[str, dict[str, Any]] = data.get(
            "brand_audit_dimensions", {}
        )
        self.journey_safety_stop_points: list[str] = data.get("journey_safety_stop_points", [])

    def ux_score_fields(self) -> list[str]:
        """The `*_score` field names for every UX audit rubric dimension."""
        return list(self.ux_audit_dimensions.keys())

    def brand_score_fields(self) -> list[str]:
        """The `*_score` field names for every brand audit rubric dimension."""
        return list(self.brand_audit_dimensions.keys())

    def scale_for_ux_dimension(self, dimension: str) -> tuple[int, int]:
        low, high = self.ux_audit_dimensions[dimension]["scale"]
        return low, high

    def scale_for_brand_dimension(self, dimension: str) -> tuple[int, int]:
        low, high = self.brand_audit_dimensions[dimension]["scale"]
        return low, high
