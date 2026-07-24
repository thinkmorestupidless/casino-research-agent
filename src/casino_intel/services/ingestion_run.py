"""Ingestion orchestrator (source doc §11.3):

    fetch -> archive -> parse -> extract -> normalise -> validate -> dedup
    -> append-unreviewed -> data-quality-issue-creation

Every fact-writing importer (UKGC, operator report, traffic, ...) plugs its
own `extract_fn` into this pipeline rather than reimplementing
fetch/archive/validate/dedup/append. Idempotency comes for free from two
layers: (1) an unchanged document short-circuits before parsing even
happens (`DocumentArchiver.archive_fetch` returns `is_new_version=False`),
and (2) `ObservationService.record_observation` dedups by fingerprint for
any candidate that does reach the append step (contracts/observation-write-contract.md §2).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from casino_intel.extraction.schema import ExtractionRecord
from casino_intel.fetching.archiver import DocumentArchiver
from casino_intel.fetching.fetcher import Fetcher, FetchResult
from casino_intel.models.source import Source
from casino_intel.normalisation.pipeline import normalise_extraction_record
from casino_intel.services.observation_service import ObservationInput, ObservationService
from casino_intel.sheets.config_loader import MetricRegistry
from casino_intel.validation import rules_ingestion
from casino_intel.validation.data_quality import DataQualityWriter

#: (content, content_type) -> candidate facts for this document.
ExtractFn = Callable[[bytes, str], list[ExtractionRecord]]

OBSERVATIONS_SHEET = "Observations"


def build_extract_fn(
    importer: str,
    *,
    source_id: str,
    subject_id: str = "",
    period_start: str = "",
    period_end: str = "",
) -> ExtractFn:
    """Resolve a named domain importer (`ukgc`, `operator_report`, or
    `generic`/anything else) to an `ExtractFn` the orchestrator can call.

    `generic` (the default for a source with no known domain-specific
    shape) returns zero candidates — fetch/archive still succeeds and the
    command still exits `0` with "0 new observations" per
    contracts/cli-commands.md, rather than guessing at an unknown format.
    """
    if importer == "ukgc":
        from casino_intel.parsing.ukgc_importer import extract_ukgc_xlsx

        def _ukgc(content: bytes, content_type: str) -> list[ExtractionRecord]:
            return extract_ukgc_xlsx(
                content,
                source_id=source_id,
                subject_id=subject_id,
                period_start=period_start,
                period_end=period_end,
            )

        return _ukgc

    if importer == "operator_report":
        from casino_intel.parsing.operator_report_importer import extract_operator_report_pdf

        def _operator_report(content: bytes, content_type: str) -> list[ExtractionRecord]:
            return extract_operator_report_pdf(
                content,
                source_id=source_id,
                subject_id=subject_id,
                period_start=period_start,
                period_end=period_end,
            )

        return _operator_report

    def _generic(content: bytes, content_type: str) -> list[ExtractionRecord]:
        return []

    return _generic


@dataclass
class IngestionOutcome:
    document_id: str | None = None
    skipped_no_content_change: bool = False
    new_observations: int = 0
    duplicate_observations: int = 0
    data_quality_issues: int = 0
    errors: list[str] = field(default_factory=list)


class IngestionRun:
    def __init__(
        self,
        *,
        fetcher: Fetcher,
        archiver: DocumentArchiver,
        observation_service: ObservationService,
        data_quality: DataQualityWriter,
        metric_registry: MetricRegistry,
    ) -> None:
        self.fetcher = fetcher
        self.archiver = archiver
        self.observation_service = observation_service
        self.data_quality = data_quality
        self.metric_registry = metric_registry

    def run(
        self,
        *,
        source: Source,
        extract_fn: ExtractFn,
        relative_folder: str = "sources/regulators",
        actor: str = "ingestion_run",
        ingestion_run_id: str | None = None,
        content: bytes | None = None,
        content_type: str = "",
        filename: str = "",
    ) -> IngestionOutcome:
        """Run the full pipeline for one source.

        If `content` is supplied directly (the `import-file` path), fetching
        is skipped — this is also how tests avoid any live network call.
        Otherwise `content` is retrieved via `self.fetcher.fetch(source)`.
        """
        outcome = IngestionOutcome()

        if content is None:
            fetch_result: FetchResult = self.fetcher.fetch(source)
            content = fetch_result.content
            content_type = content_type or fetch_result.content_type

        archive_result = self.archiver.archive_fetch(
            source_id=source.record_id,
            filename=filename or (source.url.rsplit("/", 1)[-1] or "document"),
            content=content,
            mime_type=content_type or "application/octet-stream",
            relative_folder=relative_folder,
            actor=actor,
            ingestion_run_id=ingestion_run_id,
        )
        outcome.document_id = archive_result.document_id

        if not archive_result.is_new_version:
            # Unchanged content: no-op, per FR-018/contracts/cli-commands.md
            # `fetch-source` — never re-parse, never re-append.
            outcome.skipped_no_content_change = True
            return outcome

        try:
            candidates = extract_fn(content, content_type)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller, never swallowed
            outcome.errors.append(f"extraction failed: {exc}")
            return outcome

        for candidate in candidates:
            candidate = candidate.model_copy(update={"document_id": archive_result.document_id})
            normalised = normalise_extraction_record(candidate)
            failures = rules_ingestion.validate_extraction_record(
                normalised, metric_registry=self.metric_registry
            )
            if failures:
                for issue_type, description in failures:
                    self.data_quality.raise_issue(
                        issue_type=issue_type,
                        sheet_name=OBSERVATIONS_SHEET,
                        field_name=normalised.metric_id,
                        description=description,
                    )
                outcome.data_quality_issues += len(failures)
                continue

            obs_input = ObservationInput(
                subject_type=normalised.subject.type,
                subject_id=normalised.subject.id,
                metric_id=normalised.metric_id,
                raw_value=normalised.raw_value,
                source_id=normalised.source_id,
                evidence_type=normalised.evidence_type,
                confidence=normalised.confidence,
                raw_unit=normalised.raw_unit or "",
                normalised_numeric_value=normalised.normalised_numeric_value,
                currency=normalised.currency or "",
                period_start=normalised.period_start,
                period_end=normalised.period_end,
                as_of_date=normalised.as_of_date,
                geography=normalised.geography or "",
                segment=normalised.segment or "",
                source_locator=normalised.source_locator,
                verbatim_excerpt=normalised.verbatim_excerpt or "",
                definition_id=normalised.definition_id or "",
                comparability_status=normalised.comparability_status or "unknown",
                methodology_note=normalised.methodology_note or "",
                document_id=normalised.document_id,
                created_by=actor,
            )
            result = self.observation_service.record_observation(
                obs_input, actor=actor, ingestion_run_id=ingestion_run_id
            )
            if result is None:
                outcome.data_quality_issues += 1
            elif result.duplicate:
                outcome.duplicate_observations += 1
            else:
                outcome.new_observations += 1

        return outcome
