"""Source-changed-at-same-URL handling (spec FR-019).

When a fetch/import produces a content hash that differs from the most
recent `Document` for a `Source`, `DocumentArchiver` already creates a new
`Document` row and leaves the prior row untouched. This service is the
thin orchestration point that turns "a new Document version was created"
into "hold the resulting observations for human review before they could
ever supersede a prior approved fact" — observations always start at
`review_status=unreviewed` (data-model.md), so this simply makes that
policy explicit and inspectable rather than leaving it implicit in
`Observation`'s default.
"""

from __future__ import annotations

from dataclasses import dataclass

from casino_intel.fetching.archiver import ArchiveResult, DocumentArchiver
from casino_intel.fetching.fetcher import FetchResult


@dataclass(frozen=True)
class VersioningOutcome:
    document_id: str
    is_new_version: bool
    requires_review: bool


class DocumentVersioningService:
    """Coordinates `DocumentArchiver` so a source-changed re-fetch is
    recorded as a new `Document` (never overwriting the prior one) and
    explicitly flagged as requiring review before its observations are
    trusted over prior approved ones."""

    def __init__(self, archiver: DocumentArchiver) -> None:
        self.archiver = archiver

    def version_fetch(
        self,
        *,
        source_id: str,
        fetch_result: FetchResult,
        filename: str,
        relative_folder: str = "sources/regulators",
        actor: str,
        ingestion_run_id: str | None = None,
    ) -> VersioningOutcome:
        archive_result: ArchiveResult = self.archiver.archive_fetch(
            source_id=source_id,
            filename=filename,
            content=fetch_result.content,
            mime_type=fetch_result.content_type or "application/octet-stream",
            relative_folder=relative_folder,
            actor=actor,
            ingestion_run_id=ingestion_run_id,
        )
        return VersioningOutcome(
            document_id=archive_result.document_id,
            is_new_version=archive_result.is_new_version,
            requires_review=archive_result.is_new_version,
        )
