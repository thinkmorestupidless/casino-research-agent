"""Summary sheet generator (User Story 5, source doc §9.22, FR-041,
SC-001/SC-008/SC-013, contracts/cli-commands.md `refresh-summary`).

The `Summary` sheet is a regenerated/overwritten *report view*, not an
append-only fact sheet like Observations/Financials/etc. — every run
recomputes the full picture from current data and replaces the sheet's
contents wholesale. Because `SheetsWriter` (sheets/writer.py) intentionally
only supports append-only writes and single-field status transitions (the
guarantee that matters for fact provenance), this module talks to
`SheetsClient.batch_update_values` directly instead — a deliberate,
documented exception scoped to this one read-only derived report, not a
bypass of the fact-write contract.
"""

from __future__ import annotations

from datetime import UTC, datetime

from casino_intel.reporting.completeness import (
    ACTIVE_CUSTOMERS,
    BRAND_POSITIONING,
    MARKETING_PCT_REVENUE,
    OPERATOR_REVENUE,
    REPUTATION_SCORE,
    REVENUE_PER_ACTIVE_CUSTOMER,
    SEARCH_INTEREST,
    TRAFFIC,
    UX_SCORE,
    WELCOME_OFFER,
    BrandCompleteness,
    compute_all_brands,
)
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.safety import escape_rows
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

SUMMARY_SHEET = "Summary"


class NoBrandsRegisteredError(RuntimeError):
    """Raised when there are no `Brand` rows to summarise — the CLI maps
    this to exit code 10 per contracts/cli-commands.md."""


def build_summary_row(completeness: BrandCompleteness) -> list[str]:
    """Project one brand's `BrandCompleteness` onto `SHEET_HEADERS["Summary"]`
    column order."""
    signals = completeness.signals
    age = completeness.freshest_age_days
    values: dict[str, str] = {
        "brand_id": completeness.brand_id,
        "brand_name": completeness.brand_name,
        "pilot_coverage_status": completeness.pilot_coverage_status,
        "completeness_by_domain": completeness.completeness_by_domain,
        TRAFFIC: signals[TRAFFIC].display(),
        SEARCH_INTEREST: signals[SEARCH_INTEREST].display(),
        OPERATOR_REVENUE: signals[OPERATOR_REVENUE].display(),
        ACTIVE_CUSTOMERS: signals[ACTIVE_CUSTOMERS].display(),
        REVENUE_PER_ACTIVE_CUSTOMER: signals[REVENUE_PER_ACTIVE_CUSTOMER].display(),
        MARKETING_PCT_REVENUE: signals[MARKETING_PCT_REVENUE].display(),
        WELCOME_OFFER: signals[WELCOME_OFFER].display(),
        UX_SCORE: signals[UX_SCORE].display(),
        BRAND_POSITIONING: signals[BRAND_POSITIONING].display(),
        REPUTATION_SCORE: signals[REPUTATION_SCORE].display(),
        "data_confidence_indicator": completeness.overall_confidence,
        "age_of_latest_observation_days": str(age) if age is not None else "unknown",
        "research_gaps": (
            "; ".join(completeness.research_gaps) if completeness.research_gaps else "none"
        ),
        "figure_level_note": completeness.figure_level_note,
    }
    header = SHEET_HEADERS[SUMMARY_SHEET]
    return [str(values.get(col, "")) for col in header]


def _overwrite_summary_rows(client: SheetsClient, header: list[str], rows: list[list[str]]) -> None:
    """Replace the Summary sheet's data rows wholesale.

    `SheetsClient` has no dedicated "clear" call, so a shrinking summary
    (e.g. brands removed) is handled by padding the write with blank rows
    covering any previously-written rows beyond the new row count — this
    still goes through the single batched `batch_update_values` call, never
    cell-by-cell.
    """
    existing = client.batch_get_values([f"{SUMMARY_SHEET}!A2:A"]).get(f"{SUMMARY_SHEET}!A2:A", [])
    existing_count = len(existing)
    padded_rows = list(rows)
    if existing_count > len(rows):
        blank_row = [""] * len(header)
        padded_rows += [list(blank_row) for _ in range(existing_count - len(rows))]
    client.batch_update_values(
        [{"range": f"{SUMMARY_SHEET}!A2", "values": escape_rows(padded_rows)}]
    )


def refresh_summary_sheet(
    client: SheetsClient, now: datetime | None = None, dry_run: bool = False
) -> list[BrandCompleteness]:
    """Regenerate the `Summary` sheet from current data.

    Raises :class:`NoBrandsRegisteredError` if no brands are registered yet.
    When `dry_run` is True, the completeness picture is still fully
    computed (so the caller can report on what *would* be written) but no
    write is performed.
    """
    now = now or datetime.now(UTC)
    completions = compute_all_brands(client, now=now)
    if not completions:
        raise NoBrandsRegisteredError(
            "No brands registered — run `casino-intel initialise-workbook` and register "
            "brands before refreshing the summary."
        )
    if not dry_run:
        header = SHEET_HEADERS[SUMMARY_SHEET]
        rows = [build_summary_row(c) for c in completions]
        _overwrite_summary_rows(client, header, rows)
    return completions
