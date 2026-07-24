"""UX/brand audit append service (User Story 3): validates and appends
`UXAudit`/`BrandAudit` rows through the append-only write layer, stamping
the active rubric version (FR-034) and refusing the save outright if any
populated score lacks its rationale (FR-031).

Mirrors the shape of `services/observation_service.py` and
`services/registry_service.py` so the CLI commands
(`cli/commands/record_ux_audit.py`, `record_brand_audit.py`) stay thin.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from casino_intel.models.brand_audit import BrandAudit
from casino_intel.models.ids import new_id
from casino_intel.models.ux_audit import UXAudit
from casino_intel.models.vocab import DataQualityIssueType, EvidenceType
from casino_intel.services.rubric_service import RubricService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.serialization import to_sheet_record
from casino_intel.sheets.writer import AppendResult, SheetsWriter
from casino_intel.validation.data_quality import DataQualityWriter

UX_AUDITS_SHEET = "UX Audits"
BRAND_AUDITS_SHEET = "Brand Audits"


class AuditServiceError(ValueError):
    """Raised when an audit fails validation and the save is refused."""


class AuditService:
    def __init__(
        self,
        writer: SheetsWriter,
        data_quality: DataQualityWriter,
        rubric_service: RubricService | None = None,
    ) -> None:
        self.writer = writer
        self.data_quality = data_quality
        self.rubric_service = rubric_service or RubricService()

    def record_ux_audit(
        self, fields: dict[str, Any], *, actor: str, ingestion_run_id: str | None = None
    ) -> AppendResult:
        """Validate and append one UX audit row (spec FR-031-FR-034)."""
        return self._record(
            UXAudit,
            "ux_audit",
            UX_AUDITS_SHEET,
            fields,
            actor=actor,
            ingestion_run_id=ingestion_run_id,
        )

    def record_brand_audit(
        self, fields: dict[str, Any], *, actor: str, ingestion_run_id: str | None = None
    ) -> AppendResult:
        """Validate and append one brand audit row (spec FR-031-FR-034)."""
        return self._record(
            BrandAudit,
            "brand_audit",
            BRAND_AUDITS_SHEET,
            fields,
            actor=actor,
            ingestion_run_id=ingestion_run_id,
        )

    def _record(
        self,
        model_cls: type[UXAudit] | type[BrandAudit],
        id_kind: str,
        sheet_name: str,
        fields: dict[str, Any],
        *,
        actor: str,
        ingestion_run_id: str | None,
    ) -> AppendResult:
        now = datetime.now(UTC)
        payload = dict(fields)
        payload.setdefault("rubric_version", self.rubric_service.rubric_version)
        payload.setdefault("evidence_type", EvidenceType.SUBJECTIVE_AUDIT)
        record_id = payload.pop("record_id", None) or new_id(id_kind)

        try:
            record = model_cls(
                record_id=record_id, created_at=now, created_by=actor, updated_at=now, **payload
            )
        except PydanticValidationError as exc:
            description = "; ".join(str(err["msg"]) for err in exc.errors())
            issue_type = (
                DataQualityIssueType.SUBJECTIVE_SCORE_WITHOUT_RATIONALE
                if "rationale" in description.lower()
                else DataQualityIssueType.INVALID_CONTROLLED_VOCABULARY_VALUE
            )
            self.data_quality.raise_issue(
                issue_type=issue_type,
                sheet_name=sheet_name,
                record_id=record_id,
                description=description,
            )
            raise AuditServiceError(description) from exc

        row = to_sheet_record(record.model_dump(mode="json"), SHEET_HEADERS[sheet_name])
        return self.writer.append_record(
            sheet_name, row, actor=actor, ingestion_run_id=ingestion_run_id
        )
