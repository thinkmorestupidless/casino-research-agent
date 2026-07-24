"""Source entity (data-model.md "Entity: Source", spec FR-011/FR-013)."""

from __future__ import annotations

from casino_intel.models.base import Record
from casino_intel.models.vocab import SourceStatus, SourceType


class AccessDeniedError(PermissionError):
    """Raised when code attempts to fetch a paywalled/auth-required source."""


class Source(Record):
    # Source doc §9.5 gives the `status` column its own vocabulary
    # (active/unavailable/superseded/rejected) distinct from the generic
    # Record status — override rather than add a second status-like field.
    status: SourceStatus = SourceStatus.ACTIVE

    source_type: SourceType
    publisher: str = ""
    title: str = ""
    url: str
    publication_date: str | None = None
    accessed_at: str | None = None
    reporting_period_start: str | None = None
    reporting_period_end: str | None = None
    territory: str = ""
    language: str = ""
    is_primary_source: bool = False
    paywalled: bool = False
    authentication_required: bool = False
    robots_or_terms_note: str = ""
    content_hash: str = ""
    archive_path: str = ""
    citation_text: str = ""
    quality_score: int = 3

    def assert_fetchable(self) -> None:
        """Raise if this source must never be fetched automatically (FR-013)."""
        if self.paywalled or self.authentication_required:
            raise AccessDeniedError(
                f"Source {self.record_id!r} is paywalled/authentication-required — "
                "route to manual capture instead of fetching automatically."
            )
