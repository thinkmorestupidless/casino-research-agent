# Phase 1 Data Model: Online Casino Competitive Intelligence Database

This model is the Pydantic/Sheets-schema source of truth for the feature. Every entity maps to one workbook tab (per source doc §5) and is designed to map 1:1 onto the future PostgreSQL tables listed in source doc §23 (noted per entity below). Field lists are normative; types/enums follow source doc §6–§9 and spec FR-001–FR-050.

## Common fields (inherited by every entity below, where applicable)

| Field | Type | Notes |
|---|---|---|
| `record_id` | string (prefixed ULID) | Stable, unique, immutable. Never a row number or name. |
| `created_at` | datetime (ISO-8601) | |
| `created_by` | string | Human, agent, or ingestion-run identifier |
| `updated_at` | datetime (ISO-8601) | |
| `status` | enum: `active`, `superseded`, `rejected`, `needs_review` | |
| `notes` | text | Free text |
| `source_id` | string (FK → Source) | Required unless entity is itself `Source`/`Document` |
| `document_id` | string (FK → Document, optional) | |
| `evidence_type` | enum (§ Evidence Types below) | Required on all fact-bearing records |
| `confidence` | enum: `high`, `medium`, `low`, `unknown` | |
| `review_status` | enum: `unreviewed`, `machine_checked`, `human_reviewed`, `approved`, `rejected` | |
| `captured_at` | datetime (ISO-8601) | |
| `valid_from` / `valid_to` | date (optional) | |
| `period_start` / `period_end` | date (optional) | Reporting period, where the record is period-bound |

**State transitions**:
- `status`: `active` → `superseded` (only when a newer approved observation replaces it — the prior row is never deleted) | `active`/`needs_review` → `rejected` (validation or human review failure).
- `review_status`: `unreviewed` → `machine_checked` → `human_reviewed` → `approved` | `rejected` (rejection possible from any pre-`approved` state).

## Evidence types

`reported_primary`, `reported_secondary`, `derived`, `third_party_estimate`, `direct_observation`, `subjective_audit`, `inferred_range`, `unknown` (source doc §7.1).

---

## Entity: Brand
*(→ future table `brands`)*

Consumer-facing casino brand. One row per brand (FR-001, spec Key Entities).

| Field | Type | Validation |
|---|---|---|
| `brand_id` | string (PK) | prefix `brand_` |
| `brand_name` | string | required |
| `legal_or_trading_name` | string | optional |
| `operator_id` | string (FK → Operator) | required |
| `primary_domain` | string | required, valid domain |
| `alternate_domains` | list[string] | |
| `launch_date` | date | approximate allowed, flag as such in `notes` |
| `brand_status` | enum: `active`, `dormant`, `closed`, `acquired`, `rebranded` | controlled vocabulary |
| `brand_type` | enum: `casino_only`, `sportsbook_led`, `bingo_led`, `crypto`, `sweepstakes`, `hybrid` | |
| `primary_market` | string (ISO 3166-1 alpha-2) | |
| `active_markets` / `restricted_markets` | list[string] (ISO alpha-2) | |
| `primary_language` | string (ISO language) | |
| `currency_options` | list[string] (ISO 4217) | |
| `mobile_web` / `native_ios_app` / `native_android_app` / `crypto_supported` | boolean | |
| `public_description` | text | factual only, no marketing copy |
| `research_priority` | int | 1–5 |
| `first_observed_at` / `last_verified_at` | date | |
| `sampling_rationale` | text | required for pilot brands (FR-045) |
| *(optional)* `previous_names`, `slogan`, `social_handles`, `affiliate_programme_name`, `customer_support_channels` | | |

**Relationships**: many `Brand` → one `Operator`; one `Brand` → many `Licence`, `Observation` (subject_type=brand), `Financial`, `Traffic`, `SearchInterest`, `Acquisition`, `Offer`, `ProductObservation`, `UXAudit`, `BrandAudit`, `Reputation`, `AppPresence`.

---

## Entity: Operator
*(→ future table `operators`)*

Corporate entity/group owning one or more brands.

| Field | Type | Validation |
|---|---|---|
| `operator_id` | string (PK) | prefix `operator_` |
| `operator_name` | string | required |
| `former_names` | list[string] | |
| `ultimate_parent` | string | |
| `ownership_type` | enum: `public`, `private`, `private_equity`, `state`, `unknown` | |
| `listed_exchange` / `ticker` | string | required together or both empty |
| `headquarters_country` | string (ISO alpha-2) | |
| `company_number` | string | |
| `website` / `investor_relations_url` | string (URL) | |
| `reporting_currency` | string (ISO 4217) | |
| `financial_year_end` | string (MM-DD) | |
| `brands_owned` | list[string] (derived from Brand.operator_id) | computed, not hand-entered |
| `employees_reported` | int | latest observation reference |
| `last_verified_at` | date | |

**Relationships**: one `Operator` → many `Brand`, `Licence`, `Financial` observations.

---

## Entity: Licence
*(→ future table `licences`)*

| Field | Type | Validation |
|---|---|---|
| `licence_id` | string (PK) | prefix `licence_` |
| `operator_id` | string (FK → Operator) | required |
| `brand_id` | string (FK → Brand, optional) | |
| `regulator` | string | required |
| `jurisdiction` | string (ISO alpha-2/territory) | |
| `official_licence_number` | string | |
| `licence_type` | enum (controlled vocabulary; e.g. `remote_casino`, `betting`, `bingo`, `software`) | |
| `licence_status` | enum: `active`, `suspended`, `surrendered`, `revoked`, `unknown` | |
| `effective_date` / `expiry_date` | date | |
| `licensee_legal_name` | string | exact legal name |
| `last_verified_at` | date | |

---

## Entity: Source
*(→ future table `sources`)*

Registered, retrievable origin of information (FR-011).

| Field | Type | Validation |
|---|---|---|
| `source_id` | string (PK) | prefix `source_` |
| `source_type` | enum (controlled vocabulary, source doc §9.5 list) | |
| `publisher` | string | |
| `title` | string | |
| `url` | string (URL) | |
| `publication_date` | date, optional | |
| `accessed_at` | datetime | |
| `reporting_period_start` / `reporting_period_end` | date, optional | |
| `territory` / `language` | string | |
| `is_primary_source` / `paywalled` / `authentication_required` | boolean | |
| `robots_or_terms_note` | text | |
| `content_hash` | string (SHA-256 hex) | |
| `archive_path` | string (Drive URI) | |
| `citation_text` | text | |
| `quality_score` | int | 1–5 |
| `status` | enum: `active`, `unavailable`, `superseded`, `rejected` | |

**Validation rule**: `paywalled=true` or `authentication_required=true` sources MUST NOT be fetched automatically (FR-013) — enforced in the fetcher, not just recorded.

---

## Entity: Document
*(→ future table `documents`)*

Downloaded/captured artifact tied to a `Source` (FR-012).

| Field | Type | Validation |
|---|---|---|
| `document_id` | string (PK) | prefix `document_` |
| `source_id` | string (FK → Source) | required |
| `filename` / `mime_type` | string | |
| `downloaded_at` | datetime | |
| `content_hash` | string (SHA-256 hex) | |
| `storage_path` | string (Drive URI) | never inline content |
| `file_size_bytes` / `page_count` | int | |
| `text_extraction_status` | enum: `not_started`, `complete`, `partial`, `failed` | |
| `ocr_used` | boolean | |
| `parser_name` / `parser_version` | string | |
| `raw_text_path` / `structured_data_path` | string (Drive URI) | |
| `ingestion_run_id` | string | |

**State transition**: re-fetch at same `Source.url` with a differing `content_hash` → new `Document` row created; prior `Document` row retained unmodified (FR-019).

---

## Entity: Observation *(canonical fact table)*
*(→ future table `observations`)*

The generic, time-indexed fact record (FR-004, spec Key Entities). All domain-specific sheets (Financials, Traffic, Search Interest, Acquisition, Offers, Products, App Presence) are either generated from this table or write to it in parallel, per source doc §5.

| Field | Type | Validation |
|---|---|---|
| `observation_id` | string (PK) | prefix `obs_` |
| `subject_type` | enum: `brand`, `operator`, `market`, `licence`, `offer`, `app` | |
| `subject_id` | string (FK, polymorphic on `subject_type`) | |
| `metric_id` | string (FK → metric-definition registry) | must exist in `Config`/metrics registry (FR-009) |
| `raw_value` | string | as published, unmodified |
| `raw_unit` | string | |
| `normalised_numeric_value` | decimal, optional | |
| `normalised_text_value` | string, optional | |
| `normalised_unit` | string | |
| `currency` / `normalised_currency` | string (ISO 4217) | normalised is typically GBP |
| `fx_rate` / `fx_rate_date` | decimal / date | required if `currency` ≠ `normalised_currency` |
| `period_start` / `period_end` | date | |
| `as_of_date` | date | point-in-time observations |
| `geography` | string (ISO alpha-2) | |
| `segment` | string | e.g. `casino`, `slots`, `sportsbook`, `group` |
| `source_locator` | string | page/table/row/heading/CSS selector |
| `verbatim_excerpt` | text | short, non-copyright-infringing |
| `definition_id` | string (FK → metric-definition registry) | |
| `comparability_group` | string | |
| `comparability_status` | enum: `comparable`, `partially_comparable`, `not_comparable`, `unknown` | |
| `calculation_formula` | text, required if `evidence_type=derived` | |
| `input_observation_ids` | list[string] (FK → Observation), required if `evidence_type=derived` | |
| `methodology_note` | text | |
| `fingerprint` | string (SHA-256 hex, computed) | see Validation rules below; used for idempotency |

**Validation rules** (feed `DataQualityIssue` on failure, FR-020):
- `fingerprint = sha256(subject_id, metric_id, period_start, period_end, as_of_date, geography, segment, source_id, raw_value)` (source doc §11.4). A new observation whose fingerprint already exists for an `active` row is not re-inserted.
- `source_id` is required on every row (missing → `missing_source` issue).
- `evidence_type=derived` requires non-empty `calculation_formula` and `input_observation_ids` (→ `derived_metric_without_inputs`).
- `normalised_numeric_value` present requires `raw_value` present (→ `normalised_value_without_raw_value`).
- `subject_type=brand` with a metric known to be group-only-disclosed (per metric-definition registry) is flagged (→ `group_figure_incorrectly_labelled_as_brand_figure`) unless an explicit allocation record exists (see Financial Allocation below).
- Percentage-typed metrics outside 0–100 → `percentage_outside_0_100`.
- `metric_id`/`definition_id` not present in the metric-definition registry → `unknown_metric_definition`.

---

## Entity: FinancialAllocation *(embedded/attached to Observation, not a separate sheet)*

Used only when a group/operator figure is deliberately allocated to a brand (FR-022).

| Field | Type |
|---|---|
| `allocation_method` | text |
| `allocation_assumptions` | text |
| `resulting_range_low` / `resulting_range_high` | decimal |
| `allocation_confidence` | enum: `high`, `medium`, `low`, `unknown` |
| `input_observation_ids` | list[string] |

---

## Domain-specific observation views

Each of the following is a human-friendly projection carrying its own identity, but every numeric/categorical fact within it is expected to also exist (or be derivable) as a canonical `Observation` row, per source doc §5's "one canonical fact store plus human-friendly views" target model. Common fields (`*_id`, `brand_id`, `captured_at`/`period_start`/`period_end`, `source_id`, `confidence`, `evidence_type`, `review_status`) are omitted below where identical to the patterns above; only view-specific fields are listed.

- **Financial** *(→ `observations` filtered/joined, not a separate future table)*: `financial_id`, `operator_id`, `brand_id?`, `financial_metric`, `raw_value`, `raw_currency`, `normalised_value_gbp`, `segment`, `territory`, `reported_or_derived`, `page_or_table`, `comparability_note`. **Rule**: never allocate group→brand silently (FR-022); see FinancialAllocation.
- **Traffic**: `traffic_id`, `brand_id`, `domain`, `provider`, `geography`, `device_scope`, `estimated_visits`, `estimated_unique_visitors`, `visit_duration_seconds`, `pages_per_visit`, `bounce_rate`, channel-share fields, top referral/destination domains, `provider_methodology_version`. **Rule**: never merge across `provider` values (FR-025).
- **SearchInterest**: `search_interest_id`, `brand_id`, `query_text`, `query_type` (`exact_term`/`topic`/`url`), `platform`, `geography`, `category`, `granularity`, `interest_index`, `comparison_set_id`, `anchor_term`, `export_file_document_id`. **Rule**: never compare `interest_index` across differing `comparison_set_id` without a documented rescaling method (FR-026).
- **Acquisition**: `acquisition_id`, `brand_id`, `geography`, `channel`, `traffic_share`, `spend_reported`/`spend_estimated`, `new_customers_reported`/`new_customers_estimated`, `cpa_reported`, `cpa_estimate_low`/`mid`/`high`, `affiliate_model`, `affiliate_cpa_offer`, `affiliate_revenue_share_percent`, `paid_keyword_cpc_low`/`high`, `methodology_note`. **Rule**: CPA derived from group marketing spend must be labelled a group-level proxy (FR-024).
- **Offer**: `offer_id`, `brand_id`, `geography`, `customer_type`, `offer_type`, `headline`, `description`, `promo_code`, `minimum_deposit`, `maximum_bonus`, `bonus_percentage`, `free_spins_count`/`free_spin_value`, `wagering_multiplier`/`wagering_basis`, `qualifying_games`/`excluded_games`, `minimum_odds?`, `maximum_bet_during_wagering`, `time_limit_days`, `withdrawal_cap`, `cashback_percentage`/`cashback_cap`, `opt_in_required`, `terms_url`, `screenshot_document_id`, `terms_clarity_score`. **Rule**: must be captured from full terms, not headline only (FR-028).
- **ProductObservation**: `product_observation_id`, `brand_id`, `vertical`, `game_count_estimated`, `game_provider_count`, `named_providers`, `exclusive_games_count`, boolean feature flags (`live_casino_available`, `jackpots_available`, `sportsbook_available`, `bingo_available`, `poker_available`, `crash_games_available`, `demo_play_available`, `game_search_available`, `filters_available`, `favourites_available`, `recently_played_available`, `recommendations_available`).
- **AppPresence**: `app_presence_id`, `brand_id`, `platform`, `store_country`, `app_name`, `developer_name`, `app_id`, `store_url`, `category`, `rating`/`rating_count`/`review_count`, `current_version`, `last_updated_at`, `minimum_os`, `app_size_bytes`, `in_app_purchases`, `age_rating`, `download_estimate`, `rank`.
- **Reputation**: `reputation_id`, `brand_id`, `platform`, `profile_url`, `score`/`score_scale_max`, `review_count`, `recent_review_window_days`/`recent_review_count`, `positive_theme_summary`/`negative_theme_summary` (aggregated/paraphrased only — FR-030, FR-047), `withdrawal_complaint_share`, `verification_complaint_share`, `bonus_complaint_share`, `support_complaint_share`, `suspected_review_manipulation`, `methodology_note`. **Rule**: no individual usernames or full review text stored.

---

## Entity: UXAudit
*(→ future table `audits`, `audit_type=ux`)*

One row per brand/device/geography/date (FR-031–FR-034).

| Field | Type |
|---|---|
| `ux_audit_id` | string (PK, prefix `audit_`) |
| `brand_id` | string (FK) |
| `audit_date` | date |
| `auditor` | string |
| `geography` / `device_type` / `viewport` | string |
| `logged_in_state` / `new_or_returning_visitor` / `cookie_state` | enum/boolean |
| `homepage_url` | string |
| `registration_steps` / `registration_fields` / `registration_required_fields` | int/list |
| `kyc_requested_at` | string (journey stage) |
| `deposit_steps` | int |
| `{game_discovery, search_quality, navigation_clarity, promotion_clarity, trust_signal, responsible_gambling, accessibility, mobile_usability, visual_clutter, performance, overall_ux}_score` | int 1–5 |
| `{...}_score_rationale` | text, **required whenever the paired `*_score` is set** (FR-031: "a score without rationale is invalid") |
| `screen_recording_document_id` / `screenshot_set_path` | string (Drive refs) |
| `rubric_version` | string (FK → audit-rubrics registry) |

**Validation rule**: reject save if any populated `*_score` field lacks a non-empty paired `*_score_rationale` (spec Edge Cases, FR-031).
**Safety rule**: no field may reference a completed KYC submission, deposit, wager, or withdrawal step (FR-033) — `kyc_requested_at`/`deposit_steps` record only that the *prompt* appeared, not that it was completed.

---

## Entity: BrandAudit
*(→ future table `audits`, `audit_type=brand`)*

One row per brand/date (FR-031, FR-034).

| Field | Type |
|---|---|
| `brand_audit_id` | string (PK, prefix `audit_`) |
| `brand_id` / `audit_date` / `auditor` | |
| `primary_colour` / `secondary_colours` / `background_style` / `typography_style` / `logo_type` | string |
| `mascot_present` / `photography_present` / `illustration_present` | boolean |
| `animation_intensity` / `visual_density` | enum (rubric-defined scale) |
| `tone_of_voice` / `primary_tagline` / `primary_proposition` / `target_audience_hypothesis` | text |
| `{premium, playful, trustworthy, traditional, crypto_native, sports_led, bonus_led, distinctiveness, coherence}_score` | int 1–5 |
| `brand_rationale` | text, required (mirrors UXAudit's rationale rule) |
| `screenshot_set_path` | string (Drive ref) |
| `rubric_version` | string (FK → audit-rubrics registry) |

---

## Entity: DerivedMetric
*(→ future table not explicitly named but folds into `observations` with `evidence_type=derived`, or a dedicated `derived_metrics` extension — kept as its own future table per source doc §23 pending confirmation at migration time)*

| Field | Type |
|---|---|
| `derived_metric_id` | string (PK, prefix `derived_`) |
| `subject_type` / `subject_id` | |
| `metric_id` | |
| `period_start` / `period_end` | |
| `value` / `unit` | |
| `formula_version` / `formula` | text |
| `input_observation_ids` | list[string] (FK → Observation), required, non-empty |
| `assumptions` | text |
| `comparability_status` | enum (as Observation) |
| `calculated_at` / `calculated_by` | |

**Validation/behaviour rule**: a calculation is skipped entirely (no row written) rather than produced with a fabricated value when input periods/definitions are not comparable (FR-036); recalculation after an input is superseded creates a new row, never an in-place overwrite (FR-037).

---

## Entity: ResearchTask
*(→ future table `research_tasks`)*

| Field | Type |
|---|---|
| `task_id` | string (PK, prefix `task_`) |
| `subject_type` / `subject_id` | |
| `task_type` | enum (source doc §9.19 list: `discover_source`, `download_document`, `parse_document`, `extract_metric`, `verify_licence`, `capture_traffic`, `capture_search_trends`, `capture_offer`, `perform_ux_audit`, `perform_brand_audit`, `review_conflict`, `human_validation`) |
| `priority` | int |
| `requested_metric_ids` | list[string] |
| `suggested_sources` | list[string] |
| `assigned_to` | string |
| `status` | enum: `open`, `in_progress`, `blocked`, `done`, `cancelled` |
| `attempt_count` / `last_attempt_at` / `next_attempt_after` | |
| `blocking_issue` | text |
| `result_summary` | text |
| `completed_at` | datetime |

---

## Entity: IngestionRun *(implicit; referenced by `ingestion_run_id` throughout, tracked as run metadata, not a user-facing sheet in MVP but required for FK integrity — → future table `ingestion_runs`)*

| Field | Type |
|---|---|
| `ingestion_run_id` | string (PK, prefix `run_`) |
| `started_at` / `completed_at` | datetime |
| `triggered_by` | string |
| `sources_processed` | list[string] |
| `outcome_summary` | text |

---

## Entity: ChangeLogEntry
*(→ future table `change_events`)*

Append-only (FR-038).

| Field | Type |
|---|---|
| `change_id` | string (PK, prefix `change_`) |
| `timestamp` | datetime |
| `actor` | string |
| `action` | enum: `create`, `update`, `supersede`, `reject`, `approve`, `delete_suppression` |
| `sheet_name` / `record_id` / `field_name` | string |
| `old_value` / `new_value` | string (or JSON-diff reference in Drive, per source doc §9.20 fallback) |
| `reason` | text |
| `source_id` / `ingestion_run_id` | string |

**Rule**: rows are never updated or deleted once written (append-only).

---

## Entity: DataQualityIssue
*(→ future table `data_quality_issues`)*

Generated, not hand-authored (FR-020, FR-039).

| Field | Type |
|---|---|
| `issue_id` | string (PK, prefix `issue_`) |
| `detected_at` | datetime |
| `severity` | enum: `low`, `medium`, `high`, `critical` |
| `issue_type` | enum (source doc §9.21 list — 18 values, e.g. `missing_source`, `duplicate_observation`, `subjective_score_without_rationale`, `group_figure_incorrectly_labelled_as_brand_figure`, …) |
| `sheet_name` / `record_id` / `field_name` | string |
| `description` / `suggested_fix` | text |
| `assigned_to` | string |
| `status` | enum: `open`, `in_progress`, `resolved`, `wont_fix` |
| `resolved_at` | datetime |

---

## Cross-cutting relationships summary

```text
Operator 1---* Brand
Operator 1---* Licence *---1 Brand (optional)
Brand   1---* {Financial(via brand_id), Traffic, SearchInterest, Acquisition, Offer,
               ProductObservation, UXAudit, BrandAudit, Reputation, AppPresence}
Source  1---* Document
Source  1---* Observation
Document 0..1---* Observation
Observation *---1 metric-definition (registry, in Config)
Observation *---* Observation (via input_observation_ids, for evidence_type=derived)
DerivedMetric *---* Observation (via input_observation_ids)
ResearchTask *---1 Source (suggested_sources) / *---1 Brand|Operator (subject)
ChangeLogEntry *---1 (any record, via record_id) — polymorphic, append-only
DataQualityIssue *---1 (any record, via record_id) — polymorphic
IngestionRun 1---* Document, Observation, ChangeLogEntry (via ingestion_run_id)
```

This mirrors the future PostgreSQL table list in source doc §23 directly, with `Financial`/`Traffic`/`SearchInterest`/`Acquisition`/`ProductObservation`/`AppPresence`/`Reputation` treated as Sheets-only human-friendly views over `observations` (no separate future table needed for those), and `UXAudit`/`BrandAudit` folding into a single future `audits` table distinguished by an `audit_type` column.
