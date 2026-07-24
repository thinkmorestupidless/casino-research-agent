"""Document entity (data-model.md "Entity: Document", spec FR-012/FR-019)."""

from __future__ import annotations

from casino_intel.models.base import Record
from casino_intel.models.vocab import DocumentTextExtractionStatus


class Document(Record):
    source_id: str
    filename: str
    mime_type: str
    downloaded_at: str
    content_hash: str
    storage_path: str  # Drive URI — never inline content in a sheet cell
    file_size_bytes: int = 0
    page_count: int | None = None
    text_extraction_status: DocumentTextExtractionStatus = DocumentTextExtractionStatus.NOT_STARTED
    ocr_used: bool = False
    parser_name: str = ""
    parser_version: str = ""
    raw_text_path: str = ""
    structured_data_path: str = ""
    ingestion_run_id: str = ""
