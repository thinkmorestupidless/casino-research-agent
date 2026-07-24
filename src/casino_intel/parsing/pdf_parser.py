"""PDF parser (`PyMuPDF`/`fitz` for text, `pdfplumber` for tables) —
source doc §11.1.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import pdfplumber


@dataclass
class PdfTable:
    page_number: int  # 1-indexed
    rows: list[list[str | None]]


@dataclass
class PdfParseResult:
    page_count: int
    page_texts: list[str] = field(default_factory=list)
    tables: list[PdfTable] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(self.page_texts)


def parse_pdf(content: bytes) -> PdfParseResult:
    """Extract per-page text (PyMuPDF) and any tables (pdfplumber)."""
    page_texts: list[str] = []
    with fitz.open(stream=content, filetype="pdf") as doc:
        page_count = doc.page_count
        for page in doc:
            page_texts.append(page.get_text())

    tables: list[PdfTable] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            for extracted in page.extract_tables():
                tables.append(PdfTable(page_number=page_number, rows=extracted))

    return PdfParseResult(page_count=page_count, page_texts=page_texts, tables=tables)
