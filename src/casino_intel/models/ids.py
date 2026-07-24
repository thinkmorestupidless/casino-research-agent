"""Stable, prefixed, time-sortable identifiers (research.md decision #3).

IDs look like ``brand_01J...`` — a domain prefix plus a ULID. Never use a row
number or entity name as a key (spec FR-002).
"""

from __future__ import annotations

from ulid import ULID

#: Canonical prefix per entity type, matching source doc §6 and data-model.md.
PREFIXES: dict[str, str] = {
    "brand": "brand_",
    "operator": "operator_",
    "licence": "licence_",
    "source": "source_",
    "document": "document_",
    "observation": "obs_",
    "derived_metric": "derived_",
    "ux_audit": "audit_",
    "brand_audit": "audit_",
    "research_task": "task_",
    "change_log": "change_",
    "data_quality_issue": "issue_",
    "ingestion_run": "run_",
    # Domain-specific observation views (data-model.md "Domain-specific
    # observation views") — human-friendly projections that carry their own
    # identity alongside the canonical Observation rows they parallel
    # (User Story 2, T063-T069).
    "financial": "financial_",
    "traffic": "traffic_",
    "search_interest": "search_",
    "acquisition": "acquisition_",
    "offer": "offer_",
    "product_observation": "product_",
    "reputation": "reputation_",
    "app_presence": "app_presence_",
}


def new_id(entity_type: str) -> str:
    """Generate a new prefixed ULID for the given entity type.

    Raises ``KeyError`` if ``entity_type`` is not a recognised entity — an
    unrecognised entity type is a programming error, not a data condition to
    tolerate silently.
    """
    prefix = PREFIXES[entity_type]
    return f"{prefix}{ULID()}"


def entity_type_of(record_id: str) -> str | None:
    """Return the entity type implied by a record ID's prefix, or None."""
    for entity_type, prefix in PREFIXES.items():
        if record_id.startswith(prefix):
            return entity_type
    return None


def is_valid_id(record_id: str, entity_type: str | None = None) -> bool:
    """Check that ``record_id`` has a recognised prefix followed by a ULID.

    If ``entity_type`` is given, the prefix must match that specific type.
    """
    if not record_id:
        return False
    prefixes = [PREFIXES[entity_type]] if entity_type else PREFIXES.values()
    for prefix in prefixes:
        if record_id.startswith(prefix):
            candidate = record_id[len(prefix) :]
            try:
                ULID.from_str(candidate)
                return True
            except ValueError:
                continue
    return False
