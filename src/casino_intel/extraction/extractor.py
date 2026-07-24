"""Generic extraction helpers: build `ExtractionRecord` candidates from
parsed HTML/PDF/tabular content, capturing a source locator and short
excerpt for every fact (spec FR-016), and always emitting
`review_status=unreviewed` (FR-017) — enforced by the schema's default,
never overridable by a caller here.

Domain-specific importers (`parsing/ukgc_importer.py`,
`parsing/operator_report_importer.py`, ...) build on top of these helpers
rather than constructing `ExtractionRecord` ad hoc, so every extractor
shares the same provenance discipline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from casino_intel.extraction.schema import ExtractionRecord, ExtractionSubject

MAX_EXCERPT_LENGTH = 500


def make_extraction_record(
    *,
    subject_type: str,
    subject_id: str,
    metric_id: str,
    raw_value: str,
    source_id: str,
    source_locator: str,
    evidence_type: str,
    confidence: str,
    verbatim_excerpt: str = "",
    **kwargs: object,
) -> ExtractionRecord:
    """Build one `ExtractionRecord` candidate fact.

    `subject_id` MUST already be an existing subject record_id — extractors
    resolve subjects via a lookup table supplied by the caller (e.g. a
    domain->brand_id map), never by guessing a new id.
    """
    return ExtractionRecord(
        subject=ExtractionSubject(type=subject_type, id=subject_id),  # type: ignore[arg-type]
        metric_id=metric_id,
        raw_value=raw_value,
        source_id=source_id,
        source_locator=source_locator,
        evidence_type=evidence_type,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        verbatim_excerpt=verbatim_excerpt[:MAX_EXCERPT_LENGTH] if verbatim_excerpt else "",
        **kwargs,
    )


@dataclass(frozen=True)
class KpiMatch:
    metric_id: str
    raw_value: str
    excerpt: str
    locator: str


_NUMBER_PATTERN = re.compile(
    r"[£$€]?\s*\(?-?[\d][\d,.]*\)?\s*(?:%|million|billion|thousand|m|bn|k)?",
    re.IGNORECASE,
)


_FORWARD_WINDOW_CHARS = 60


def find_kpi_mentions(
    text: str, search_terms: dict[str, str], *, page_label: str = ""
) -> list[KpiMatch]:
    """Scan `text` for each of `search_terms` (`{metric_id: literal term}`),
    returning the first plausible numeric value found shortly after each
    match (the common report phrasing "<term> was/is/increased to <value>"),
    with a short surrounding excerpt for provenance.

    A search term with no nearby number is simply omitted — extractors
    MUST NOT guess a value, and MUST NOT reach backward across a sentence
    boundary for a number that belongs to a neighbouring KPI mention
    (source doc §10.4's KPI search-term approach for operator annual reports).
    """
    matches: list[KpiMatch] = []
    for metric_id, term in search_terms.items():
        for occurrence in re.finditer(re.escape(term), text, re.IGNORECASE):
            forward_window = text[occurrence.end() : occurrence.end() + _FORWARD_WINDOW_CHARS]
            # Never cross a sentence boundary into the next KPI's mention —
            # but don't mistake a decimal point (e.g. "1.2 million") for one.
            sentence_end_match = re.search(r"(?<!\d)\.(?!\d)", forward_window)
            if sentence_end_match:
                forward_window = forward_window[: sentence_end_match.end()]

            number_match = _NUMBER_PATTERN.search(forward_window)
            if not number_match or not any(ch.isdigit() for ch in number_match.group()):
                continue

            excerpt_start = max(0, occurrence.start() - 40)
            excerpt_end = occurrence.end() + len(forward_window)
            excerpt = text[excerpt_start:excerpt_end].strip().replace("\n", " ")
            matches.append(
                KpiMatch(
                    metric_id=metric_id,
                    raw_value=number_match.group().strip(),
                    excerpt=excerpt[:MAX_EXCERPT_LENGTH],
                    locator=page_label,
                )
            )
            break  # first match per term per page is enough for one candidate fact
    return matches
