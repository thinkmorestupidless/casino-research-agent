"""Brand/Operator/Licence registration service (User Story 1, FR-001-FR-002).

Supports both one-at-a-time registration and bulk-loading a seed file (used
by `scripts/seed_pilot_brands.py`, T038).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from casino_intel.models.brand import Brand
from casino_intel.models.ids import new_id
from casino_intel.models.licence import Licence
from casino_intel.models.operator import Operator
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.serialization import to_sheet_record
from casino_intel.sheets.writer import AppendResult, SheetsWriter

OPERATORS_SHEET = "Operators"
BRANDS_SHEET = "Brands"
LICENCES_SHEET = "Licences"


class RegistryService:
    def __init__(self, writer: SheetsWriter) -> None:
        self.writer = writer

    def register_operator(
        self, fields: dict[str, Any], *, actor: str, ingestion_run_id: str | None = None
    ) -> AppendResult:
        now = datetime.now(UTC)
        operator = Operator(
            record_id=fields.get("record_id") or new_id("operator"),
            created_at=now,
            created_by=actor,
            updated_at=now,
            **{k: v for k, v in fields.items() if k != "record_id"},
        )
        row = to_sheet_record(operator.model_dump(mode="json"), SHEET_HEADERS[OPERATORS_SHEET])
        return self.writer.append_record(
            OPERATORS_SHEET, row, actor=actor, ingestion_run_id=ingestion_run_id
        )

    def register_brand(
        self, fields: dict[str, Any], *, actor: str, ingestion_run_id: str | None = None
    ) -> AppendResult:
        now = datetime.now(UTC)
        brand = Brand(
            record_id=fields.get("record_id") or new_id("brand"),
            created_at=now,
            created_by=actor,
            updated_at=now,
            **{k: v for k, v in fields.items() if k != "record_id"},
        )
        row = to_sheet_record(brand.model_dump(mode="json"), SHEET_HEADERS[BRANDS_SHEET])
        return self.writer.append_record(
            BRANDS_SHEET, row, actor=actor, ingestion_run_id=ingestion_run_id
        )

    def register_licence(
        self, fields: dict[str, Any], *, actor: str, ingestion_run_id: str | None = None
    ) -> AppendResult:
        now = datetime.now(UTC)
        licence = Licence(
            record_id=fields.get("record_id") or new_id("licence"),
            created_at=now,
            created_by=actor,
            updated_at=now,
            **{k: v for k, v in fields.items() if k != "record_id"},
        )
        row = to_sheet_record(licence.model_dump(mode="json"), SHEET_HEADERS[LICENCES_SHEET])
        return self.writer.append_record(
            LICENCES_SHEET, row, actor=actor, ingestion_run_id=ingestion_run_id
        )

    def bulk_load(
        self,
        *,
        operators: list[dict[str, Any]],
        brands: list[dict[str, Any]],
        licences: list[dict[str, Any]] | None = None,
        actor: str,
        ingestion_run_id: str | None = None,
    ) -> dict[str, list[AppendResult]]:
        """Register operators, then brands (so `operator_id` FKs resolve),
        then licences. Returns the generated IDs mapped by input index, so
        the caller (the seed loader) can cross-reference alias -> record_id.
        """
        operator_results = [
            self.register_operator(o, actor=actor, ingestion_run_id=ingestion_run_id)
            for o in operators
        ]
        brand_results = [
            self.register_brand(b, actor=actor, ingestion_run_id=ingestion_run_id) for b in brands
        ]
        licence_results = [
            self.register_licence(licence, actor=actor, ingestion_run_id=ingestion_run_id)
            for licence in (licences or [])
        ]
        return {
            "operators": operator_results,
            "brands": brand_results,
            "licences": licence_results,
        }
