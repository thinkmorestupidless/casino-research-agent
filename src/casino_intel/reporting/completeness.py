"""Per-brand completeness/gap scoring (User Story 5, spec FR-041/SC-001/SC-008/SC-013,
source doc §9.22).

This module reads the workbook state already produced by the other user
stories (Brands, Observations, Derived Metrics, Offers, UX Audits, Brand
Audits) and, per brand, finds the latest value for each tracked signal
while preserving:

- the `evidence_type`/`confidence` markers carried by the underlying row —
  never invented or upgraded;
- an explicit operator-vs-brand `figure_level` marker for any figure that
  is sourced from an operator-subject row rather than a brand-specific one
  (spec Edge Cases, FR-022, source doc §9.22's "never hide whether a value
  is operator-level or brand-level" rule);
- the age, in days, of the observation used, relative to a caller-supplied
  `now` (never `datetime.now()` inside this module, for deterministic
  tests).

Nothing here fabricates or backfills a value: a signal with no matching row
is represented as a :class:`SignalValue` with ``value=None`` — a visible
gap — never as a blank cell that could be mistaken for zero or "fine".

Design note on filtering: rows with `status` of `rejected` or `superseded`
are excluded (a rejected/superseded row is not a current fact; its
replacement, if any, will already be picked up by the latest-value lookup).
`review_status` is deliberately *not* used as a hard filter — an
`unreviewed`/`machine_checked` observation is still shown, honestly labelled
with its own evidence/confidence markers, because hiding it would work
against this feature's purpose (an honest picture rather than a falsely
tidy one). The `refresh-summary` contract's "current active/approved data"
phrasing is read as a description of the workbook's overall data quality
bar, not a literal `review_status == approved` gate on every domain sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

#: Sheets read to build the summary — all are read-only inputs here.
_BRANDS_SHEET = "Brands"
_OBSERVATIONS_SHEET = "Observations"
_DERIVED_METRICS_SHEET = "Derived Metrics"
_OFFERS_SHEET = "Offers"
_UX_AUDITS_SHEET = "UX Audits"
_BRAND_AUDITS_SHEET = "Brand Audits"

_DATASET_SHEETS = [
    _BRANDS_SHEET,
    _OBSERVATIONS_SHEET,
    _DERIVED_METRICS_SHEET,
    _OFFERS_SHEET,
    _UX_AUDITS_SHEET,
    _BRAND_AUDITS_SHEET,
]

#: Rows in this status are never current facts (data-model.md status
#: transitions: `active` -> `superseded`/`rejected`).
_EXCLUDED_STATUSES = {"rejected", "superseded"}

FIGURE_LEVEL_BRAND = "brand-level"
FIGURE_LEVEL_OPERATOR = "operator-level"

#: Signal labels — these match `SHEET_HEADERS["Summary"]` column names
#: exactly so `summary_generator.py` can key straight off them.
TRAFFIC = "latest_traffic_estimate"
SEARCH_INTEREST = "search_interest_trend"
OPERATOR_REVENUE = "latest_operator_revenue"
ACTIVE_CUSTOMERS = "latest_active_customer_figure"
REVENUE_PER_ACTIVE_CUSTOMER = "revenue_per_active_customer"
MARKETING_PCT_REVENUE = "marketing_pct_revenue"
WELCOME_OFFER = "current_welcome_offer"
UX_SCORE = "ux_score"
BRAND_POSITIONING = "brand_positioning_scores"
REPUTATION_SCORE = "reputation_score"

SIGNAL_LABELS = [
    TRAFFIC,
    SEARCH_INTEREST,
    OPERATOR_REVENUE,
    ACTIVE_CUSTOMERS,
    REVENUE_PER_ACTIVE_CUSTOMER,
    MARKETING_PCT_REVENUE,
    WELCOME_OFFER,
    UX_SCORE,
    BRAND_POSITIONING,
    REPUTATION_SCORE,
]

_POSITIONING_DIMENSIONS = [
    "premium",
    "playful",
    "trustworthy",
    "traditional",
    "crypto_native",
    "sports_led",
    "bonus_led",
    "distinctiveness",
    "coherence",
]

#: Reporting-only heuristic used to flag a signal as "stale" in research
#: gaps. This is not the formal Data Quality `stale_observation` threshold
#: (no such numeric threshold is defined anywhere in metrics.yaml or
#: validation/data_quality.py yet) — it exists purely so the Summary sheet
#: never silently treats a very old figure as if it were current.
STALE_AFTER_DAYS = 180

_CONFIDENCE_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class SignalValue:
    """One tracked signal's latest known value for one brand, or a gap."""

    label: str
    value: str | None = None
    evidence_type: str | None = None
    confidence: str | None = None
    figure_level: str | None = None
    captured_at: datetime | None = None
    age_days: int | None = None

    @property
    def is_gap(self) -> bool:
        return self.value is None or self.value == ""

    def display(self) -> str:
        """Render the value plus its evidence/confidence/level markers, or
        a visible gap marker — never a bare/blank value."""
        if self.is_gap:
            return "GAP: no data on record"
        parts = [str(self.value)]
        markers = []
        if self.evidence_type:
            markers.append(f"evidence={self.evidence_type}")
        if self.confidence:
            markers.append(f"confidence={self.confidence}")
        if markers:
            parts.append(f"({', '.join(markers)})")
        if self.figure_level == FIGURE_LEVEL_OPERATOR:
            parts.append("[OPERATOR-LEVEL]")
        return " ".join(parts)


@dataclass
class BrandCompleteness:
    """The full completeness/gap picture for one brand."""

    brand_id: str
    brand_name: str
    operator_id: str
    signals: dict[str, SignalValue]
    now: datetime

    @property
    def populated_count(self) -> int:
        return sum(1 for s in self.signals.values() if not s.is_gap)

    @property
    def total_signals(self) -> int:
        return len(self.signals)

    @property
    def completeness_ratio(self) -> float:
        if not self.total_signals:
            return 0.0
        return self.populated_count / self.total_signals

    @property
    def pilot_coverage_status(self) -> str:
        ratio = self.completeness_ratio
        if ratio >= 0.75:
            return "comprehensive"
        if ratio > 0:
            return "partial"
        return "no_data"

    @property
    def completeness_by_domain(self) -> str:
        return "; ".join(
            f"{label}: {'yes' if not sig.is_gap else 'no'}" for label, sig in self.signals.items()
        )

    @property
    def research_gaps(self) -> list[str]:
        gaps: list[str] = []
        for label, sig in self.signals.items():
            if sig.is_gap:
                gaps.append(f"{label}: missing - no observation on record")
            elif sig.age_days is None:
                gaps.append(f"{label}: age unknown - capture date could not be determined")
            elif sig.age_days > STALE_AFTER_DAYS:
                gaps.append(f"{label}: stale - last captured {sig.age_days} days ago")
        return gaps

    @property
    def freshest_age_days(self) -> int | None:
        """Age, in days, of the single most-recently-captured signal used
        anywhere in this brand's row — i.e. how current our best data is."""
        ages = [s.age_days for s in self.signals.values() if s.age_days is not None]
        return min(ages) if ages else None

    @property
    def overall_confidence(self) -> str:
        populated = [s for s in self.signals.values() if not s.is_gap]
        if not populated:
            return "no_data"
        worst_rank = min(_CONFIDENCE_RANK.get(s.confidence or "unknown", 0) for s in populated)
        for label, rank in _CONFIDENCE_RANK.items():
            if rank == worst_rank:
                return label
        return "unknown"

    @property
    def operator_level_labels(self) -> list[str]:
        return [
            label
            for label, sig in self.signals.items()
            if sig.figure_level == FIGURE_LEVEL_OPERATOR and not sig.is_gap
        ]

    @property
    def figure_level_note(self) -> str:
        labels = self.operator_level_labels
        if not labels:
            return "all shown figures are brand-level"
        return "operator-level (not brand-specific): " + ", ".join(labels)


# --- dataset loading -------------------------------------------------------------


def _load_dataset(client: SheetsClient) -> dict[str, list[dict[str, str]]]:
    """One batched read of every sheet the summary depends on."""
    ranges = [f"{name}!A2:ZZ" for name in _DATASET_SHEETS]
    values = client.batch_get_values(ranges)
    dataset: dict[str, list[dict[str, str]]] = {}
    for name in _DATASET_SHEETS:
        header = SHEET_HEADERS[name]
        raw_rows = values.get(f"{name}!A2:ZZ", [])
        dataset[name] = [
            {col: (raw[i] if i < len(raw) else "") for i, col in enumerate(header)}
            for raw in raw_rows
        ]
    return dataset


def _active_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if r.get("status", "") not in _EXCLUDED_STATUSES]


# --- date handling -----------------------------------------------------------------


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt: datetime | None = None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _sort_by_date(
    rows: list[dict[str, str]], date_fields: tuple[str, ...]
) -> list[tuple[datetime, dict[str, str]]]:
    dated: list[tuple[datetime, dict[str, str]]] = []
    for row in rows:
        dt = None
        for f in date_fields:
            dt = _parse_datetime(row.get(f))
            if dt is not None:
                break
        if dt is not None:
            dated.append((dt, row))
    dated.sort(key=lambda pair: pair[0])
    return dated


def _pick_latest(
    rows: list[dict[str, str]], date_fields: tuple[str, ...]
) -> tuple[dict[str, str], datetime | None] | None:
    if not rows:
        return None
    dated = _sort_by_date(rows, date_fields)
    if dated:
        dt, row = dated[-1]
        return row, dt
    # No row has a parseable date: fall back to the last-appended row (sheet
    # append order), but report the age as unknown rather than guessing it.
    return rows[-1], None


# --- value/marker extraction -------------------------------------------------------


def _observation_value(row: dict[str, str]) -> str:
    nval = row.get("normalised_numeric_value")
    if nval not in (None, ""):
        unit = row.get("normalised_unit") or ""
        return f"{nval} {unit}".strip()
    raw = row.get("raw_value") or ""
    if not raw:
        return ""
    unit = row.get("raw_unit") or ""
    return f"{raw} {unit}".strip()


def _derived_value(row: dict[str, str]) -> str:
    val = row.get("value") or ""
    if not val:
        return ""
    unit = row.get("unit") or ""
    return f"{val} {unit}".strip()


def _figure_level(row: dict[str, str]) -> str:
    return FIGURE_LEVEL_OPERATOR if row.get("subject_type") == "operator" else FIGURE_LEVEL_BRAND


def _build_signal(
    label: str,
    found: tuple[dict[str, str], datetime | None],
    now: datetime,
    value: str,
    *,
    figure_level: str | None = None,
    evidence_override: str | None = None,
) -> SignalValue:
    row, dt = found
    if not value:
        return SignalValue(label=label)
    evidence = (
        evidence_override if evidence_override is not None else (row.get("evidence_type") or None)
    )
    confidence = row.get("confidence") or None
    age_days = (now - dt).days if dt is not None else None
    return SignalValue(
        label=label,
        value=value,
        evidence_type=evidence or None,
        confidence=confidence or None,
        figure_level=figure_level if figure_level is not None else _figure_level(row),
        captured_at=dt,
        age_days=age_days,
    )


# --- per-signal lookups -------------------------------------------------------------


def _observation_signal(
    label: str,
    observations: list[dict[str, str]],
    subject_type: str,
    subject_id: str,
    metric_id: str,
    now: datetime,
) -> SignalValue:
    if not subject_id:
        return SignalValue(label=label)
    matches = [
        o
        for o in _active_rows(observations)
        if o.get("subject_type") == subject_type
        and o.get("subject_id") == subject_id
        and o.get("metric_id") == metric_id
    ]
    found = _pick_latest(matches, ("captured_at", "as_of_date", "period_end"))
    if not found:
        return SignalValue(label=label)
    return _build_signal(label, found, now, _observation_value(found[0]))


def _operator_only_observation_signal(
    label: str,
    observations: list[dict[str, str]],
    operator_id: str,
    metric_id: str,
    now: datetime,
) -> SignalValue:
    """Look up a metric that is only ever meaningful at operator level
    (e.g. `latest_operator_revenue`) — always flagged operator-level."""
    sig = _observation_signal(label, observations, "operator", operator_id, metric_id, now)
    if sig.is_gap:
        return sig
    return SignalValue(
        label=sig.label,
        value=sig.value,
        evidence_type=sig.evidence_type,
        confidence=sig.confidence,
        figure_level=FIGURE_LEVEL_OPERATOR,
        captured_at=sig.captured_at,
        age_days=sig.age_days,
    )


def _brand_then_operator_observation_signal(
    label: str,
    observations: list[dict[str, str]],
    brand_id: str,
    operator_id: str,
    metric_id: str,
    now: datetime,
) -> SignalValue:
    """Prefer a brand-specific observation; fall back to the operator-level
    figure when no brand-specific one exists, explicitly flagging the level
    (spec Edge Cases: a group-only figure must never be presented as if it
    were brand-specific)."""
    sig = _observation_signal(label, observations, "brand", brand_id, metric_id, now)
    if not sig.is_gap:
        return sig
    return _operator_only_observation_signal(label, observations, operator_id, metric_id, now)


def _brand_then_operator_derived_signal(
    label: str,
    derived_rows: list[dict[str, str]],
    brand_id: str,
    operator_id: str,
    metric_id: str,
    now: datetime,
) -> SignalValue:
    brand_matches = [
        d
        for d in _active_rows(derived_rows)
        if d.get("subject_type") == "brand"
        and d.get("subject_id") == brand_id
        and d.get("metric_id") == metric_id
    ]
    found = _pick_latest(brand_matches, ("calculated_at", "period_end"))
    if found and _derived_value(found[0]):
        return _build_signal(
            label,
            found,
            now,
            _derived_value(found[0]),
            figure_level=FIGURE_LEVEL_BRAND,
            evidence_override="derived",
        )
    if operator_id:
        operator_matches = [
            d
            for d in _active_rows(derived_rows)
            if d.get("subject_type") == "operator"
            and d.get("subject_id") == operator_id
            and d.get("metric_id") == metric_id
        ]
        found = _pick_latest(operator_matches, ("calculated_at", "period_end"))
        if found and _derived_value(found[0]):
            return _build_signal(
                label,
                found,
                now,
                _derived_value(found[0]),
                figure_level=FIGURE_LEVEL_OPERATOR,
                evidence_override="derived",
            )
    return SignalValue(label=label)


def _search_interest_signal(
    observations: list[dict[str, str]], brand_id: str, now: datetime
) -> SignalValue:
    matches = [
        o
        for o in _active_rows(observations)
        if o.get("subject_type") == "brand"
        and o.get("subject_id") == brand_id
        and o.get("metric_id") == "branded_search_interest_index"
    ]
    if not matches:
        return SignalValue(label=SEARCH_INTEREST)
    dated = _sort_by_date(matches, ("captured_at", "as_of_date", "period_end"))
    if not dated:
        row = matches[-1]
        base_value = _observation_value(row)
        if not base_value:
            return SignalValue(label=SEARCH_INTEREST)
        value = f"{base_value} (trend unknown - no dated history)"
        return _build_signal(SEARCH_INTEREST, (row, None), now, value)

    latest_dt, latest_row = dated[-1]
    base_value = _observation_value(latest_row)
    if not base_value:
        return SignalValue(label=SEARCH_INTEREST)

    trend = "insufficient_history"
    if len(dated) >= 2:
        _prev_dt, prev_row = dated[-2]
        try:
            latest_numeric = float(
                latest_row.get("normalised_numeric_value") or latest_row.get("raw_value")
            )
            prev_numeric = float(
                prev_row.get("normalised_numeric_value") or prev_row.get("raw_value")
            )
        except (TypeError, ValueError):
            trend = "unknown"
        else:
            if latest_numeric > prev_numeric:
                trend = "up"
            elif latest_numeric < prev_numeric:
                trend = "down"
            else:
                trend = "flat"

    value = f"{base_value} ({trend})"
    return _build_signal(SEARCH_INTEREST, (latest_row, latest_dt), now, value)


def _welcome_offer_signal(
    offers: list[dict[str, str]], brand_id: str, now: datetime
) -> SignalValue:
    matches = [
        o
        for o in _active_rows(offers)
        if o.get("brand_id") == brand_id and o.get("offer_type") == "welcome_bonus"
    ]
    found = _pick_latest(matches, ("captured_at", "valid_from"))
    if not found:
        return SignalValue(label=WELCOME_OFFER)
    row, dt = found
    value = row.get("headline") or row.get("description") or "(offer on file, no headline recorded)"
    return _build_signal(WELCOME_OFFER, (row, dt), now, value, figure_level=FIGURE_LEVEL_BRAND)


def _ux_score_signal(ux_audits: list[dict[str, str]], brand_id: str, now: datetime) -> SignalValue:
    matches = [r for r in _active_rows(ux_audits) if r.get("brand_id") == brand_id]
    found = _pick_latest(matches, ("audit_date", "captured_at"))
    if not found:
        return SignalValue(label=UX_SCORE)
    row, dt = found
    score = row.get("overall_ux_score") or ""
    if not score:
        return SignalValue(label=UX_SCORE)
    return _build_signal(UX_SCORE, (row, dt), now, score, figure_level=FIGURE_LEVEL_BRAND)


def _brand_positioning_signal(
    brand_audits: list[dict[str, str]], brand_id: str, now: datetime
) -> SignalValue:
    matches = [r for r in _active_rows(brand_audits) if r.get("brand_id") == brand_id]
    found = _pick_latest(matches, ("audit_date", "captured_at"))
    if not found:
        return SignalValue(label=BRAND_POSITIONING)
    row, dt = found
    parts = [
        f"{dim}={row[f'{dim}_score']}" for dim in _POSITIONING_DIMENSIONS if row.get(f"{dim}_score")
    ]
    if not parts:
        return SignalValue(label=BRAND_POSITIONING)
    return _build_signal(
        BRAND_POSITIONING, (row, dt), now, ", ".join(parts), figure_level=FIGURE_LEVEL_BRAND
    )


# --- top-level orchestration ---------------------------------------------------------


def compute_brand_completeness(
    dataset: dict[str, list[dict[str, str]]], brand: dict[str, str], now: datetime
) -> BrandCompleteness:
    brand_id = brand.get("record_id", "")
    operator_id = brand.get("operator_id", "")
    observations = dataset[_OBSERVATIONS_SHEET]
    derived = dataset[_DERIVED_METRICS_SHEET]
    offers = dataset[_OFFERS_SHEET]
    ux_audits = dataset[_UX_AUDITS_SHEET]
    brand_audits = dataset[_BRAND_AUDITS_SHEET]

    signals: dict[str, SignalValue] = {
        TRAFFIC: _observation_signal(
            TRAFFIC, observations, "brand", brand_id, "estimated_monthly_visits", now
        ),
        SEARCH_INTEREST: _search_interest_signal(observations, brand_id, now),
        OPERATOR_REVENUE: _operator_only_observation_signal(
            OPERATOR_REVENUE, observations, operator_id, "revenue", now
        ),
        ACTIVE_CUSTOMERS: _brand_then_operator_observation_signal(
            ACTIVE_CUSTOMERS, observations, brand_id, operator_id, "active_customers", now
        ),
        REVENUE_PER_ACTIVE_CUSTOMER: _brand_then_operator_derived_signal(
            REVENUE_PER_ACTIVE_CUSTOMER,
            derived,
            brand_id,
            operator_id,
            "revenue_per_active_customer",
            now,
        ),
        MARKETING_PCT_REVENUE: _brand_then_operator_derived_signal(
            MARKETING_PCT_REVENUE, derived, brand_id, operator_id, "marketing_pct_revenue", now
        ),
        WELCOME_OFFER: _welcome_offer_signal(offers, brand_id, now),
        UX_SCORE: _ux_score_signal(ux_audits, brand_id, now),
        BRAND_POSITIONING: _brand_positioning_signal(brand_audits, brand_id, now),
        REPUTATION_SCORE: _observation_signal(
            REPUTATION_SCORE, observations, "brand", brand_id, "review_platform_score", now
        ),
    }

    return BrandCompleteness(
        brand_id=brand_id,
        brand_name=brand.get("brand_name", ""),
        operator_id=operator_id,
        signals=signals,
        now=now,
    )


def compute_all_brands(
    client: SheetsClient, now: datetime | None = None
) -> list[BrandCompleteness]:
    """Compute :class:`BrandCompleteness` for every registered brand."""
    now = now or datetime.now(UTC)
    dataset = _load_dataset(client)
    brands = [
        b
        for b in dataset[_BRANDS_SHEET]
        if b.get("record_id") and b.get("status", "") not in _EXCLUDED_STATUSES
    ]
    return [compute_brand_completeness(dataset, brand, now) for brand in brands]
