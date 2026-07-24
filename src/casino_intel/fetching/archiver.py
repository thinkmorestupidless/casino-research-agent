"""Fetch archiving: Drive upload, content hashing, and `Document` row
creation/versioning (spec FR-012/FR-019, data-model.md "Entity: Document").

Re-fetching an unchanged source is a no-op (no new `Document` row, no Drive
re-upload) — the prior `Document` row is retained unmodified either way,
per the append-only write layer's guarantees. A changed content hash always
creates a brand-new `Document` row; it never edits the previous one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from casino_intel.cache.fingerprint_store import FingerprintStore
from casino_intel.drive.client import DriveClient, sha256_bytes
from casino_intel.models.document import Document
from casino_intel.models.ids import new_id
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.serialization import to_sheet_record
from casino_intel.sheets.writer import SheetsWriter

DOCUMENTS_SHEET = "Documents"


@dataclass(frozen=True)
class ArchiveResult:
    document_id: str
    content_hash: str
    is_new_version: bool
    storage_path: str


class DocumentArchiver:
    def __init__(
        self,
        drive_client: DriveClient,
        fingerprint_store: FingerprintStore,
        writer: SheetsWriter,
    ) -> None:
        self.drive_client = drive_client
        self.fingerprint_store = fingerprint_store
        self.writer = writer

    def archive_fetch(
        self,
        *,
        source_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
        relative_folder: str = "sources/regulators",
        actor: str,
        ingestion_run_id: str | None = None,
    ) -> ArchiveResult:
        """Archive one fetched/imported artifact for `source_id`.

        If the content hash matches the most recently recorded hash for
        this source, nothing is uploaded or written — the existing
        `document_id` is returned with `is_new_version=False` (FR-019's
        "no new row if unchanged" / contracts/cli-commands.md `fetch-source`
        postcondition).
        """
        content_hash = sha256_bytes(content)
        existing_document_id = self.fingerprint_store.has_document_hash(source_id, content_hash)
        if existing_document_id:
            return ArchiveResult(
                document_id=existing_document_id,
                content_hash=content_hash,
                is_new_version=False,
                storage_path="",
            )

        file_id, archive_path, _ = self.drive_client.upload(
            relative_folder, filename, content, mime_type
        )
        now = datetime.now(UTC)
        document = Document(
            record_id=new_id("document"),
            created_at=now,
            created_by=actor,
            updated_at=now,
            source_id=source_id,
            filename=filename,
            mime_type=mime_type,
            downloaded_at=now.isoformat(),
            content_hash=content_hash,
            storage_path=archive_path,
            file_size_bytes=len(content),
            ingestion_run_id=ingestion_run_id or "",
        )
        dumped = document.model_dump(mode="json")
        row = to_sheet_record(dumped, SHEET_HEADERS[DOCUMENTS_SHEET])
        result = self.writer.append_record(
            DOCUMENTS_SHEET, row, actor=actor, ingestion_run_id=ingestion_run_id
        )
        self.fingerprint_store.record_document_hash(source_id, content_hash, result.record_id)
        return ArchiveResult(
            document_id=result.record_id,
            content_hash=content_hash,
            is_new_version=True,
            storage_path=archive_path,
        )
