"""Observation append service (User Story 1): validates, normalises
currency, and appends canonical Observation rows through the append-only,
idempotent write layer (spec FR-001-FR-010).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from casino_intel.models.ids import new_id
from casino_intel.models.observation import Observation
from casino_intel.normalisation.currency import FxRateProvider, normalise_currency
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.serialization import to_sheet_record
from casino_intel.sheets.writer import AppendResult, SheetsWriter
from casino_intel.validation import rules_core
from casino_intel.validation.data_quality import DataQualityWriter

OBSERVATIONS_SHEET = "Observations"


@dataclass
class ObservationInput:
    """Caller-facing parameters for recording one fact — a superset of
    `Observation` fields for convenience (e.g. raw currency + numeric value
    before FX normalisation is applied)."""

    subject_type: str
    subject_id: str
    metric_id: str
    raw_value: str
    source_id: str
    evidence_type: str
    confidence: str = "unknown"
    raw_unit: str = ""
    normalised_numeric_value: float | None = None
    currency: str = ""
    target_currency: str = "GBP"
    period_start: str | None = None
    period_end: str | None = None
    as_of_date: str | None = None
    geography: str = ""
    segment: str = ""
    source_locator: str = ""
    verbatim_excerpt: str = ""
    definition_id: str = ""
    comparability_group: str = ""
    comparability_status: str = "unknown"
    methodology_note: str = ""
    document_id: str | None = None
    captured_at: str | None = None
    created_by: str = "observation_service"
    notes: str = field(default="")


class ObservationValidationError(ValueError):
    def __init__(self, failures: list[rules_core.Failure]) -> None:
        self.failures = failures
        super().__init__("; ".join(desc for _, desc in failures))


class ObservationService:
    def __init__(
        self,
        writer: SheetsWriter,
        data_quality: DataQualityWriter,
        metric_registry: MetricRegistry,
        fx_provider: FxRateProvider | None = None,
    ) -> None:
        self.writer = writer
        self.data_quality = data_quality
        self.metric_registry = metric_registry
        self.fx_provider = fx_provider

    def record_observation(
        self, obs_input: ObservationInput, *, actor: str, ingestion_run_id: str | None = None
    ) -> AppendResult | None:
        """Validate and append one observation. Returns None (and raises no
        exception) if validation fails — the failure is instead written to
        Data Quality, per FR-020's "route to Data Quality, don't reject silently".
        """
        failures = self._validate(obs_input)
        if failures:
            for issue_type, description in failures:
                self.data_quality.raise_issue(
                    issue_type=issue_type,
                    sheet_name=OBSERVATIONS_SHEET,
                    field_name=obs_input.metric_id,
                    description=description,
                )
            return None

        normalised_currency = ""
        fx_rate = None
        fx_rate_date = None
        normalised_numeric_value = obs_input.normalised_numeric_value
        if obs_input.currency and obs_input.normalised_numeric_value is not None:
            kwargs = {"provider": self.fx_provider} if self.fx_provider else {}
            converted = normalise_currency(
                obs_input.normalised_numeric_value,
                obs_input.currency,
                obs_input.target_currency,
                as_of_date=obs_input.as_of_date or "",
                **kwargs,
            )
            normalised_currency = converted.normalised_currency
            normalised_numeric_value = converted.normalised_value
            fx_rate = converted.fx_rate
            fx_rate_date = converted.fx_rate_date

        now = datetime.now(UTC)
        observation = Observation(
            record_id=new_id("observation"),
            created_at=now,
            created_by=obs_input.created_by,
            updated_at=now,
            source_id=obs_input.source_id,
            document_id=obs_input.document_id,
            evidence_type=obs_input.evidence_type,
            confidence=obs_input.confidence,
            captured_at=obs_input.captured_at or now,
            period_start=obs_input.period_start,
            period_end=obs_input.period_end,
            notes=obs_input.notes,
            subject_type=obs_input.subject_type,
            subject_id=obs_input.subject_id,
            metric_id=obs_input.metric_id,
            raw_value=obs_input.raw_value,
            raw_unit=obs_input.raw_unit,
            normalised_numeric_value=normalised_numeric_value,
            normalised_unit=obs_input.raw_unit,
            currency=obs_input.currency,
            normalised_currency=normalised_currency,
            fx_rate=fx_rate,
            fx_rate_date=fx_rate_date,
            as_of_date=obs_input.as_of_date,
            geography=obs_input.geography,
            segment=obs_input.segment,
            source_locator=obs_input.source_locator,
            verbatim_excerpt=obs_input.verbatim_excerpt,
            definition_id=obs_input.definition_id,
            comparability_group=obs_input.comparability_group,
            comparability_status=obs_input.comparability_status,
            methodology_note=obs_input.methodology_note,
        )

        dumped = observation.model_dump(mode="json")
        row_for_sheet = to_sheet_record(dumped, SHEET_HEADERS[OBSERVATIONS_SHEET])
        return self.writer.append_observation(
            OBSERVATIONS_SHEET, row_for_sheet, actor=actor, ingestion_run_id=ingestion_run_id
        )

    def _validate(self, obs_input: ObservationInput) -> list[rules_core.Failure]:
        failures: list[rules_core.Failure] = []
        failures += rules_core.validate_has_source(obs_input.source_id)
        failures += rules_core.validate_metric_known(obs_input.metric_id, self.metric_registry)
        failures += rules_core.validate_normalised_requires_raw(
            obs_input.raw_value, obs_input.normalised_numeric_value
        )
        # FR-020 percentage range: enforced on every write path, not just the
        # extraction pipeline — a percentage-typed metric recorded directly
        # (e.g. traffic_share via the traffic importer) is range-checked too.
        failures += rules_core.validate_percentage_for_metric(
            obs_input.metric_id, obs_input.normalised_numeric_value, self.metric_registry
        )
        return failures
