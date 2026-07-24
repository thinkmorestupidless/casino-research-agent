"""Data Quality issue writer (spec FR-020/FR-039, source doc §9.21).

Every one of the 18 issue types below can be raised anywhere in the
codebase; this module only owns *writing* the resulting issue row. Records
failing validation are routed here instead of being silently accepted
(contracts/cli-commands.md `ingest-source`) or silently dropped.
"""

from __future__ import annotations

from datetime import UTC, datetime

from casino_intel.models.ids import new_id
from casino_intel.models.vocab import DataQualityIssueType, DataQualitySeverity, DataQualityStatus
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.safety import escape_row

SHEET_NAME = "Data Quality"

COLUMNS = [
    "issue_id",
    "detected_at",
    "severity",
    "issue_type",
    "sheet_name",
    "record_id",
    "field_name",
    "description",
    "suggested_fix",
    "assigned_to",
    "status",
    "resolved_at",
]

#: Default severity per issue type — callers may override with an explicit severity.
_DEFAULT_SEVERITY: dict[DataQualityIssueType, DataQualitySeverity] = {
    DataQualityIssueType.MISSING_SOURCE: DataQualitySeverity.HIGH,
    DataQualityIssueType.MISSING_REPORTING_PERIOD: DataQualitySeverity.MEDIUM,
    DataQualityIssueType.INVALID_ID: DataQualitySeverity.CRITICAL,
    DataQualityIssueType.DUPLICATE_ENTITY: DataQualitySeverity.HIGH,
    DataQualityIssueType.DUPLICATE_OBSERVATION: DataQualitySeverity.LOW,
    DataQualityIssueType.UNSUPPORTED_CURRENCY: DataQualitySeverity.HIGH,
    DataQualityIssueType.PERCENTAGE_OUTSIDE_0_100: DataQualitySeverity.HIGH,
    DataQualityIssueType.NEGATIVE_VALUE_WHERE_PROHIBITED: DataQualitySeverity.HIGH,
    DataQualityIssueType.NORMALISED_VALUE_WITHOUT_RAW_VALUE: DataQualitySeverity.HIGH,
    DataQualityIssueType.DERIVED_METRIC_WITHOUT_INPUTS: DataQualitySeverity.CRITICAL,
    DataQualityIssueType.SUBJECTIVE_SCORE_WITHOUT_RATIONALE: DataQualitySeverity.HIGH,
    DataQualityIssueType.STALE_OBSERVATION: DataQualitySeverity.LOW,
    DataQualityIssueType.CONFLICTING_HIGH_CONFIDENCE_OBSERVATIONS: DataQualitySeverity.MEDIUM,
    DataQualityIssueType.GROUP_FIGURE_INCORRECTLY_LABELLED_AS_BRAND_FIGURE: (
        DataQualitySeverity.CRITICAL
    ),
    DataQualityIssueType.SOURCE_URL_UNAVAILABLE: DataQualitySeverity.MEDIUM,
    DataQualityIssueType.CONTENT_HASH_CHANGED: DataQualitySeverity.LOW,
    DataQualityIssueType.UNKNOWN_METRIC_DEFINITION: DataQualitySeverity.HIGH,
    DataQualityIssueType.INVALID_CONTROLLED_VOCABULARY_VALUE: DataQualitySeverity.HIGH,
}


class DataQualityWriter:
    def __init__(self, client: SheetsClient, dry_run: bool = False) -> None:
        self.client = client
        self.dry_run = dry_run

    def raise_issue(
        self,
        *,
        issue_type: DataQualityIssueType,
        sheet_name: str,
        record_id: str = "",
        field_name: str = "",
        description: str,
        suggested_fix: str = "",
        assigned_to: str = "",
        severity: DataQualitySeverity | None = None,
    ) -> dict[str, str]:
        """Append a new Data Quality issue row. Never overwrites a prior issue."""
        entry = {
            "issue_id": new_id("data_quality_issue"),
            "detected_at": datetime.now(UTC).isoformat(),
            "severity": (
                severity or _DEFAULT_SEVERITY.get(issue_type, DataQualitySeverity.MEDIUM)
            ).value,
            "issue_type": issue_type.value,
            "sheet_name": sheet_name,
            "record_id": record_id,
            "field_name": field_name,
            "description": description,
            "suggested_fix": suggested_fix,
            "assigned_to": assigned_to,
            "status": DataQualityStatus.OPEN.value,
            "resolved_at": "",
        }
        if not self.dry_run:
            row = escape_row([entry[col] for col in COLUMNS])
            self.client.append_rows(SHEET_NAME, [row])
        return entry
