# Online Casino Competitive Intelligence Database
## Initial Implementation Requirements Specification

**Document status:** Initial implementation specification  
**Version:** 0.1  
**Date:** 24 July 2026  
**Primary storage:** Google Sheets  
**Intended audience:** Coding agent / implementation engineer  
**Initial market focus:** Great Britain-facing online casino brands  
**Primary objective:** Build a structured, source-backed dataset that can inform casino brand strategy, proposition design, acquisition strategy and website UX.

---

## 1. Purpose

The system will collect, normalise and analyse publicly available information about online casino brands and their operators.

The initial implementation must support research into:

- market size and category growth;
- brand reach and consumer awareness;
- acquisition channels and indicative acquisition economics;
- active users and customer value;
- operator revenue and profitability;
- promotions, bonuses and loyalty mechanics;
- product breadth and game presentation;
- visual identity and brand positioning;
- registration, deposit and withdrawal journeys;
- trust, reputation and regulatory signals;
- mobile application presence and performance;
- differences between reported facts, derived metrics, third-party estimates and subjective audits.

The purpose is not to create a perfect financial model of every casino. Most brand-level commercial data is not publicly disclosed. The system must therefore make uncertainty, source quality and comparability explicit.

The first implementation should favour:

1. low operational overhead;
2. easy schema modification;
3. human inspectability;
4. complete source provenance;
5. future migration to PostgreSQL;
6. direct access by research agents and coding agents.

---

## 2. Scope

### 2.1 In scope

The MVP will:

- store operator and brand master data;
- store time-indexed observations rather than overwriting prior values;
- register every source used;
- ingest structured files such as CSV and XLSX;
- extract tables and facts from HTML, PDF and annual-report documents;
- support manual UX and brand audits;
- calculate selected derived metrics;
- retain raw extracted values alongside normalised values;
- assign evidence type, confidence and comparability flags;
- provide a Google Sheets workbook as the primary user interface;
- maintain an append-only change log;
- support an initial pilot of 15–20 brands;
- produce summary views suitable for later dashboarding and analysis.

### 2.2 Out of scope for the MVP

The MVP will not:

- claim exact brand-level profit, CPA or LTV where these are not disclosed;
- scrape authenticated or paywalled services without permission;
- bypass anti-bot controls or website terms;
- create player accounts or make deposits automatically;
- collect personal data about individual gamblers;
- automate subjective brand scoring without human review;
- replace legal review of gambling advertising or licensing requirements;
- operate a production web application or PostgreSQL service;
- perform real-time monitoring;
- infer precise conversion rates from traffic alone.

---

## 3. Design principles

### 3.1 Append observations; do not overwrite history

Commercial metrics, traffic estimates, bonuses and website designs change. Each capture must be a new observation with a capture date and reporting period.

### 3.2 Separate entities, observations and sources

A brand is an entity. “Estimated monthly visits in June 2026” is an observation. The Similarweb page or exported report is a source. These must not be conflated.

### 3.3 Preserve raw and normalised values

Where a report states “€450m revenue,” retain:

- the original value and currency;
- any normalised GBP value;
- the exchange rate used;
- the conversion date;
- the calculation method.

### 3.4 Never hide uncertainty

Every observation must state whether it is:

- reported;
- derived;
- third-party estimated;
- directly observed;
- subjective;
- unknown.

### 3.5 Avoid false comparability

Terms such as “active customer,” “monthly active account,” “unique visitor,” “depositor,” “new depositing customer” and “registered account” are not interchangeable.

### 3.6 Design for migration

Every sheet should map naturally to a future relational table. Records use stable IDs rather than row numbers or brand names as keys.

---

## 4. Research questions the dataset must answer

The initial data model should allow analysis of the following questions.

### 4.1 Market and category

- How large is the online casino market in the target territory?
- Which verticals are growing: slots, live casino, table games, bingo or sportsbook?
- What broad benchmark exists for GGY per active account?
- How seasonal is activity?
- Which regulatory or tax changes may affect economics?

### 4.2 Brand reach

- Which brands receive the greatest estimated web traffic?
- Which brands have growing or declining branded search interest?
- How much traffic appears direct, organic, paid, affiliate, referral or social?
- Which brands have meaningful app-store presence?
- Which brands appear overly dependent on affiliates or paid acquisition?

### 4.3 Customer economics

- What active-customer figures do public operators disclose?
- What revenue, GGR, NGR or GGY do they report?
- What marketing expenditure do they report?
- What can defensibly be calculated per active customer?
- Is an estimated CPA range possible, and what assumptions support it?
- What margin and marketing-efficiency benchmarks exist at operator level?

### 4.4 Brand, proposition and UX

- Which visual and tonal territories are crowded?
- Which brands position themselves as premium, playful, trustworthy, crypto-native, sports-led or bonus-led?
- How prominent are promotions relative to games and brand storytelling?
- How many steps are required to register?
- What verification is requested and when?
- How quickly can a user find a desired game?
- What trust, licensing and responsible-gambling information is visible?
- How clearly are wagering requirements and withdrawal conditions explained?
- Which design and UX patterns correlate with stronger direct traffic, branded search or customer sentiment?

---

## 5. Workbook structure

Create one Google Sheets workbook named:

`Casino Competitive Intelligence – MVP`

The workbook must contain the following tabs.

1. `README`
2. `Config`
3. `Brands`
4. `Operators`
5. `Licences`
6. `Sources`
7. `Documents`
8. `Observations`
9. `Financials`
10. `Traffic`
11. `Search Interest`
12. `Acquisition`
13. `Offers`
14. `Products`
15. `UX Audits`
16. `Brand Audits`
17. `Reputation`
18. `App Presence`
19. `Derived Metrics`
20. `Research Queue`
21. `Change Log`
22. `Data Quality`
23. `Summary`

Tabs 8–18 are domain-specific views. `Observations` is the canonical generic fact table. Implementations may initially write both the specialised sheet and a canonical observation row, or generate the specialised sheets from the canonical table. The preferred long-term model is one canonical fact store plus human-friendly views.

---

## 6. Common record fields

All data tables must include, where applicable:

| Field | Type | Requirement |
|---|---|---|
| `record_id` | string | Stable, unique, immutable ID |
| `created_at` | ISO-8601 datetime | Creation timestamp |
| `created_by` | string | Human, agent or ingestion job identifier |
| `updated_at` | ISO-8601 datetime | Last material update |
| `status` | enum | `active`, `superseded`, `rejected`, `needs_review` |
| `notes` | text | Free-text context |
| `source_id` | string | Foreign key to `Sources` |
| `document_id` | string | Optional foreign key to `Documents` |
| `evidence_type` | enum | See Section 7 |
| `confidence` | enum | `high`, `medium`, `low`, `unknown` |
| `review_status` | enum | `unreviewed`, `machine_checked`, `human_reviewed`, `approved`, `rejected` |
| `captured_at` | ISO-8601 datetime | When the information was captured |
| `valid_from` | date | Date the fact became valid, where known |
| `valid_to` | date | End of validity, where known |
| `period_start` | date | Start of reporting period |
| `period_end` | date | End of reporting period |

IDs should use readable prefixes and UUIDs or ULIDs, for example:

- `brand_01J...`
- `operator_01J...`
- `source_01J...`
- `obs_01J...`
- `audit_01J...`

Do not use spreadsheet row numbers as identifiers.

---

## 7. Evidence model

### 7.1 Evidence types

| Value | Meaning |
|---|---|
| `reported_primary` | Published directly by the operator, regulator or statutory authority |
| `reported_secondary` | Reported by a reputable secondary source quoting or reproducing primary data |
| `derived` | Calculated from stored input observations |
| `third_party_estimate` | Estimated by a traffic, SEO, app or market-intelligence provider |
| `direct_observation` | Captured directly from a website, app, advert or user journey |
| `subjective_audit` | Structured human judgement using the agreed rubric |
| `inferred_range` | Range estimated from several facts and documented assumptions |
| `unknown` | Evidence type not established |

### 7.2 Confidence

**High**

- direct primary source;
- exact reporting period and definition known;
- value transcribed or parsed with validation;
- no material ambiguity.

**Medium**

- reputable third-party estimate;
- derived metric with minor definition limitations;
- direct observation that may vary by user, location or session;
- primary data allocated from operator to brand using a documented assumption.

**Low**

- weak source;
- substantial inference;
- missing denominator;
- uncertain brand/operator allocation;
- stale observation;
- conflicting sources.

### 7.3 Comparability

Each numerical observation must include:

- `definition_id`;
- `comparability_group`;
- `comparability_status`: `comparable`, `partially_comparable`, `not_comparable`, `unknown`;
- `comparability_note`.

---

## 8. Controlled vocabularies and configuration

The `Config` sheet must contain named lists used for Google Sheets data validation.

Required controlled vocabularies include:

- countries and territories using ISO 3166-1 alpha-2;
- currencies using ISO 4217;
- evidence types;
- confidence values;
- review statuses;
- source types;
- product verticals;
- acquisition channels;
- offer types;
- device types;
- audit score range;
- operator ownership type;
- brand status;
- licence status;
- comparability status;
- metric definitions;
- units.

Do not encode controlled lists in implementation code only. The workbook must expose them for inspection and amendment.

---

# 9. Sheet specifications

## 9.1 `README`

Purpose:

- explain the workbook;
- link to this specification;
- state data limitations;
- document update workflow;
- display version and last successful ingestion;
- describe colour conventions;
- state that estimates are not audited facts.

Required fields:

- workbook version;
- schema version;
- last ingestion time;
- last human review time;
- target market;
- owner;
- links to code repository and runbook.

---

## 9.2 `Brands`

One row per consumer-facing brand.

Required columns:

| Column | Description |
|---|---|
| `brand_id` | Stable ID |
| `brand_name` | Current public name |
| `legal_or_trading_name` | Where different |
| `operator_id` | Parent or operating company |
| `primary_domain` | Canonical domain |
| `alternate_domains` | Comma-separated or JSON array |
| `launch_date` | Exact or approximate |
| `brand_status` | Active, dormant, closed, acquired, rebranded |
| `brand_type` | Casino-only, sportsbook-led, bingo-led, crypto, sweepstakes, hybrid |
| `primary_market` | ISO country |
| `active_markets` | List |
| `restricted_markets` | List |
| `primary_language` | ISO language |
| `currency_options` | List |
| `mobile_web` | Boolean |
| `native_ios_app` | Boolean |
| `native_android_app` | Boolean |
| `crypto_supported` | Boolean |
| `public_description` | Short factual description |
| `research_priority` | 1–5 |
| `first_observed_at` | Date |
| `last_verified_at` | Date |
| `status` | Record status |
| `notes` | Notes |

Optional:

- previous names;
- slogan;
- social handles;
- affiliate programme name;
- customer-support channels.

---

## 9.3 `Operators`

One row per corporate operator or relevant parent group.

Required columns:

| Column | Description |
|---|---|
| `operator_id` | Stable ID |
| `operator_name` | Current name |
| `former_names` | Previous names |
| `ultimate_parent` | Ultimate parent entity |
| `ownership_type` | Public, private, private equity, state, unknown |
| `listed_exchange` | Exchange |
| `ticker` | Stock ticker |
| `headquarters_country` | ISO country |
| `company_number` | Relevant company registration number |
| `website` | Corporate website |
| `investor_relations_url` | Investor information |
| `reporting_currency` | ISO currency |
| `financial_year_end` | Month/day |
| `brands_owned` | Derived field or list |
| `employees_reported` | Latest observation |
| `last_verified_at` | Date |
| `notes` | Notes |

---

## 9.4 `Licences`

One row per operator/brand/licence relationship.

Required columns:

| Column | Description |
|---|---|
| `licence_id` | Stable internal ID |
| `operator_id` | Operator |
| `brand_id` | Optional brand |
| `regulator` | Regulator name |
| `jurisdiction` | ISO country/territory |
| `official_licence_number` | Regulator identifier |
| `licence_type` | Remote casino, betting, bingo, software, etc. |
| `licence_status` | Active, suspended, surrendered, revoked, unknown |
| `effective_date` | Start |
| `expiry_date` | End, if applicable |
| `licensee_legal_name` | Exact legal name |
| `source_id` | Licence register source |
| `last_verified_at` | Date |

---

## 9.5 `Sources`

One row per retrievable source.

Required columns:

| Column | Description |
|---|---|
| `source_id` | Stable ID |
| `source_type` | Controlled vocabulary |
| `publisher` | Organisation publishing the source |
| `title` | Human-readable title |
| `url` | Canonical URL |
| `publication_date` | Where known |
| `accessed_at` | Retrieval timestamp |
| `reporting_period_start` | Where applicable |
| `reporting_period_end` | Where applicable |
| `territory` | Relevant geography |
| `language` | Source language |
| `is_primary_source` | Boolean |
| `paywalled` | Boolean |
| `authentication_required` | Boolean |
| `robots_or_terms_note` | Restrictions or permissions |
| `content_hash` | SHA-256 of downloaded content where possible |
| `archive_path` | Drive path or object-store URI |
| `citation_text` | Preferred citation |
| `quality_score` | 1–5 |
| `status` | Active, unavailable, superseded, rejected |
| `notes` | Notes |

Source types:

- regulator statistics;
- regulator licence register;
- statutory company filing;
- annual report;
- interim report;
- investor presentation;
- earnings call transcript;
- corporate press release;
- operator website;
- brand website;
- promotion terms;
- affiliate programme;
- affiliate listing;
- advertising ruling;
- app store;
- review platform;
- traffic intelligence;
- SEO intelligence;
- search trends;
- news article;
- social-media profile;
- manual screen capture;
- other.

---

## 9.6 `Documents`

One row per downloaded or ingested artifact.

Required columns:

| Column | Description |
|---|---|
| `document_id` | Stable ID |
| `source_id` | Parent source |
| `filename` | Original filename |
| `mime_type` | MIME type |
| `downloaded_at` | Timestamp |
| `content_hash` | SHA-256 |
| `storage_path` | Google Drive path |
| `file_size_bytes` | Size |
| `page_count` | PDF page count |
| `text_extraction_status` | Not started, complete, partial, failed |
| `ocr_used` | Boolean |
| `parser_name` | Parser/library |
| `parser_version` | Version |
| `raw_text_path` | Extracted text artifact |
| `structured_data_path` | JSON/CSV artifact |
| `ingestion_run_id` | Run identifier |
| `notes` | Notes |

Do not store large documents or extracted full text inside sheet cells. Store them in Google Drive and retain references and hashes.

Recommended Drive hierarchy:

```text
Casino Competitive Intelligence/
  sources/
    regulators/
    operators/
    brands/
    traffic/
    app-stores/
    reviews/
  extracted/
    text/
    tables/
    json/
  screenshots/
    brand/
      YYYY-MM-DD/
  exports/
  logs/
```

---

## 9.7 `Observations`

Canonical, long-form fact table.

Required columns:

| Column | Description |
|---|---|
| `observation_id` | Stable ID |
| `subject_type` | Brand, operator, market, licence, offer, app |
| `subject_id` | ID of subject |
| `metric_id` | Controlled metric identifier |
| `raw_value` | Value as published |
| `raw_unit` | Published unit |
| `normalised_numeric_value` | Numeric value where applicable |
| `normalised_text_value` | Normalised categorical/text value |
| `normalised_unit` | Standard unit |
| `currency` | Original currency |
| `normalised_currency` | Usually GBP for initial market |
| `fx_rate` | Used rate |
| `fx_rate_date` | Date |
| `period_start` | Reporting period |
| `period_end` | Reporting period |
| `as_of_date` | Point-in-time date |
| `geography` | ISO geography |
| `segment` | Casino, slots, sportsbook, group, etc. |
| `source_id` | Source |
| `document_id` | Document |
| `source_locator` | Page, table, row, heading or CSS selector |
| `verbatim_excerpt` | Short supporting excerpt; avoid excessive copyrighted text |
| `evidence_type` | Evidence type |
| `confidence` | Confidence |
| `definition_id` | Definition |
| `comparability_group` | Group |
| `comparability_status` | Status |
| `calculation_formula` | For derived values |
| `input_observation_ids` | Inputs for derived values |
| `methodology_note` | Method |
| `review_status` | Review |
| `captured_at` | Capture time |
| `created_by` | Actor |
| `status` | Active/superseded/rejected |

### Initial metric catalogue

#### Market metrics

- `market_ggr`
- `market_ggy`
- `market_ngr`
- `market_active_accounts`
- `market_bets_or_spins`
- `market_sessions`
- `market_average_session_minutes`
- `market_sessions_over_one_hour`
- `market_share`
- `vertical_ggr`
- `vertical_ggy`
- `vertical_growth_yoy`

#### Operator financial metrics

- `revenue`
- `gaming_revenue`
- `ggr`
- `ggy`
- `ngr`
- `adjusted_ebitda`
- `operating_profit`
- `net_profit`
- `marketing_expense`
- `sales_and_marketing_expense`
- `affiliate_expense`
- `bonuses_and_promotions_expense`
- `gaming_tax`
- `payment_cost`
- `capital_expenditure`
- `cash`
- `net_debt`
- `employees`

#### Customer metrics

- `active_customers`
- `monthly_active_customers`
- `average_monthly_active_accounts`
- `depositing_customers`
- `new_depositing_customers`
- `registered_accounts`
- `first_time_depositors`
- `average_stake`
- `average_deposit`
- `deposit_frequency`
- `customer_retention_rate`
- `churn_rate`
- `vip_customer_count`

#### Traffic and awareness metrics

- `estimated_monthly_visits`
- `estimated_unique_visitors`
- `visit_duration_seconds`
- `pages_per_visit`
- `bounce_rate`
- `traffic_share_direct`
- `traffic_share_organic`
- `traffic_share_paid`
- `traffic_share_referral`
- `traffic_share_social`
- `traffic_share_display`
- `branded_search_interest_index`
- `branded_search_volume`
- `share_of_search`
- `referring_domains`
- `backlinks`
- `domain_authority_or_equivalent`

#### App metrics

- `app_rating`
- `app_rating_count`
- `app_review_count`
- `app_download_estimate`
- `app_rank`
- `app_last_updated_at`
- `app_version`
- `app_size_bytes`

#### Reputation metrics

- `review_platform_score`
- `review_count`
- `complaint_count`
- `complaint_resolution_rate`
- `regulatory_action_count`
- `advertising_ruling_count`
- `sentiment_score`

#### UX metrics

- `registration_steps`
- `registration_fields`
- `time_to_register_seconds`
- `kyc_stage`
- `deposit_steps`
- `minimum_deposit`
- `withdrawal_methods_count`
- `games_above_fold`
- `homepage_promotion_count`
- `homepage_load_lcp_ms`
- `homepage_cls`
- `homepage_inp_ms`
- `search_result_relevance_score`
- `navigation_depth_to_game`
- `responsible_gambling_prominence_score`
- `licence_visibility_score`
- `terms_clarity_score`
- `accessibility_score`

---

## 9.8 `Financials`

Human-friendly view of financial observations.

Columns:

- `financial_id`
- `operator_id`
- `brand_id` where specifically disclosed
- `period_start`
- `period_end`
- `financial_metric`
- `raw_value`
- `raw_currency`
- `normalised_value_gbp`
- `segment`
- `territory`
- `reported_or_derived`
- `source_id`
- `page_or_table`
- `confidence`
- `comparability_note`
- `review_status`

The system must not silently allocate group financials to individual brands.

Where allocation is attempted, store:

- allocation method;
- assumptions;
- resulting range;
- confidence;
- input observations.

---

## 9.9 `Traffic`

One row per brand/domain/provider/period.

Columns:

- `traffic_id`
- `brand_id`
- `domain`
- `provider`
- `period_start`
- `period_end`
- `geography`
- `device_scope`
- `estimated_visits`
- `estimated_unique_visitors`
- `visit_duration_seconds`
- `pages_per_visit`
- `bounce_rate`
- channel shares;
- top referral domains;
- top destination domains;
- source ID;
- confidence;
- provider methodology version;
- capture date.

Provider estimates from different services must not be merged as though measured identically.

---

## 9.10 `Search Interest`

One row per search series and period.

Columns:

- `search_interest_id`
- `brand_id`
- `query_text`
- `query_type`: exact term, topic, URL
- `platform`: Google Search, YouTube Search
- `geography`
- `category`
- `period_start`
- `period_end`
- `granularity`
- `interest_index`
- `comparison_set_id`
- `anchor_term`
- `export_file_document_id`
- `source_id`
- `captured_at`
- `notes`

Google Trends values are relative, normalised indices rather than absolute search volume. Store the comparison set because values can change when different brands are compared.

---

## 9.11 `Acquisition`

One row per brand/channel/period.

Columns:

- `acquisition_id`
- `brand_id`
- `period_start`
- `period_end`
- `geography`
- `channel`
- `traffic_share`
- `spend_reported`
- `spend_estimated`
- `new_customers_reported`
- `new_customers_estimated`
- `cpa_reported`
- `cpa_estimate_low`
- `cpa_estimate_mid`
- `cpa_estimate_high`
- `affiliate_model`
- `affiliate_cpa_offer`
- `affiliate_revenue_share_percent`
- `paid_keyword_cpc_low`
- `paid_keyword_cpc_high`
- `methodology_note`
- `source_id`
- `confidence`

Do not derive CPA from total group marketing expense without labelling it as a group-level proxy.

---

## 9.12 `Offers`

One row per offer capture.

Columns:

- `offer_id`
- `brand_id`
- `captured_at`
- `geography`
- `customer_type`
- `offer_type`
- `headline`
- `description`
- `promo_code`
- `minimum_deposit`
- `maximum_bonus`
- `bonus_percentage`
- `free_spins_count`
- `free_spin_value`
- `wagering_multiplier`
- `wagering_basis`
- `qualifying_games`
- `excluded_games`
- `minimum_odds` where applicable
- `maximum_bet_during_wagering`
- `time_limit_days`
- `withdrawal_cap`
- `cashback_percentage`
- `cashback_cap`
- `opt_in_required`
- `terms_url`
- `source_id`
- `screenshot_document_id`
- `terms_clarity_score`
- `confidence`

Offer terms must be captured from the full terms, not only the promotional headline.

---

## 9.13 `Products`

One row per brand/product observation.

Columns:

- `product_observation_id`
- `brand_id`
- `captured_at`
- `vertical`
- `game_count_estimated`
- `game_provider_count`
- `named_providers`
- `exclusive_games_count`
- `live_casino_available`
- `jackpots_available`
- `sportsbook_available`
- `bingo_available`
- `poker_available`
- `crash_games_available`
- `demo_play_available`
- `game_search_available`
- `filters_available`
- `favourites_available`
- `recently_played_available`
- `recommendations_available`
- `source_id`
- `confidence`
- `notes`

---

## 9.14 `UX Audits`

One row per brand, device, geography and audit date.

Columns:

- `ux_audit_id`
- `brand_id`
- `audit_date`
- `auditor`
- `geography`
- `device_type`
- `viewport`
- `logged_in_state`
- `new_or_returning_visitor`
- `cookie_state`
- `homepage_url`
- `registration_steps`
- `registration_fields`
- `registration_required_fields`
- `kyc_requested_at`
- `deposit_steps`
- `game_discovery_score`
- `search_quality_score`
- `navigation_clarity_score`
- `promotion_clarity_score`
- `trust_signal_score`
- `responsible_gambling_score`
- `accessibility_score`
- `mobile_usability_score`
- `visual_clutter_score`
- `performance_score`
- `overall_ux_score`
- `screen_recording_document_id`
- `screenshot_set_path`
- `source_id`
- `notes`

### UX audit scoring

Use a 1–5 ordinal scale with a written rubric.

Example: `promotion_clarity_score`

1. Offer is misleading or material terms are difficult to locate.
2. Headline is clear but important constraints are obscured.
3. Main value and major restrictions are visible with one interaction.
4. Major terms are clearly summarised and full terms are easy to inspect.
5. Offer, eligibility, wagering and withdrawal consequences are immediately understandable.

Store both score and rationale. A score without rationale is invalid.

### Journey safety

Automated research must stop before:

- submitting identity documents;
- accepting legally binding terms on behalf of a researcher;
- depositing money;
- placing a wager;
- withdrawing funds.

---

## 9.15 `Brand Audits`

One row per brand and audit date.

Columns:

- `brand_audit_id`
- `brand_id`
- `audit_date`
- `auditor`
- `primary_colour`
- `secondary_colours`
- `background_style`
- `typography_style`
- `logo_type`
- `mascot_present`
- `photography_present`
- `illustration_present`
- `animation_intensity`
- `visual_density`
- `tone_of_voice`
- `primary_tagline`
- `primary_proposition`
- `target_audience_hypothesis`
- `premium_score`
- `playful_score`
- `trustworthy_score`
- `traditional_score`
- `crypto_native_score`
- `sports_led_score`
- `bonus_led_score`
- `distinctiveness_score`
- `coherence_score`
- `brand_rationale`
- `screenshot_set_path`
- `review_status`

All subjective scores use 1–5 rubrics maintained in `Config`.

---

## 9.16 `Reputation`

One row per platform/brand/capture.

Columns:

- `reputation_id`
- `brand_id`
- `platform`
- `profile_url`
- `captured_at`
- `score`
- `score_scale_max`
- `review_count`
- `recent_review_window_days`
- `recent_review_count`
- `positive_theme_summary`
- `negative_theme_summary`
- `withdrawal_complaint_share`
- `verification_complaint_share`
- `bonus_complaint_share`
- `support_complaint_share`
- `suspected_review_manipulation`
- `methodology_note`
- `source_id`
- `confidence`

Review content should be aggregated and paraphrased. Do not store unnecessary personal data, usernames or complete review text.

---

## 9.17 `App Presence`

One row per application and platform.

Columns:

- `app_presence_id`
- `brand_id`
- `platform`
- `store_country`
- `app_name`
- `developer_name`
- `app_id`
- `store_url`
- `category`
- `rating`
- `rating_count`
- `review_count`
- `current_version`
- `last_updated_at`
- `minimum_os`
- `app_size_bytes`
- `in_app_purchases`
- `age_rating`
- `download_estimate`
- `rank`
- `captured_at`
- `source_id`
- `confidence`

---

## 9.18 `Derived Metrics`

One row per calculated result.

Columns:

- `derived_metric_id`
- `subject_type`
- `subject_id`
- `metric_id`
- `period_start`
- `period_end`
- `value`
- `unit`
- `formula_version`
- `formula`
- `input_observation_ids`
- `assumptions`
- `confidence`
- `comparability_status`
- `calculated_at`
- `calculated_by`
- `review_status`

### Initial calculations

#### Revenue per active customer

```text
revenue_per_active_customer =
  revenue_for_period / active_customers_for_compatible_period
```

Only calculate where definitions and periods are sufficiently compatible.

#### GGY per average monthly active account

```text
ggy_per_average_monthly_active_account =
  quarterly_ggy / average_monthly_active_accounts
```

Label carefully: the denominator may be an average monthly count while the numerator covers a quarter. This is not equivalent to per-customer lifetime value.

#### Marketing expense as percentage of revenue

```text
marketing_pct_revenue =
  marketing_expense / revenue
```

#### EBITDA margin

```text
adjusted_ebitda_margin =
  adjusted_ebitda / revenue
```

#### Traffic growth

```text
traffic_growth_yoy =
  (visits_current_period - visits_prior_year_period)
  / visits_prior_year_period
```

#### Share of search

```text
share_of_search =
  brand_interest_index
  / sum(interest_indices_in_same_comparison_set)
```

#### Indicative CPA range

No single mandatory formula. The calculation must store assumptions and may use:

- reported CPA;
- reported marketing expense and new customers;
- affiliate CPA offers;
- paid-search costs;
- operator guidance;
- reasonable allocation ranges.

---

## 9.19 `Research Queue`

Tracks work to perform.

Columns:

- `task_id`
- `subject_type`
- `subject_id`
- `task_type`
- `priority`
- `requested_metric_ids`
- `suggested_sources`
- `assigned_to`
- `status`
- `attempt_count`
- `last_attempt_at`
- `next_attempt_after`
- `blocking_issue`
- `result_summary`
- `created_at`
- `completed_at`

Task types:

- discover source;
- download document;
- parse document;
- extract metric;
- verify licence;
- capture traffic;
- capture search trends;
- capture offer;
- perform UX audit;
- perform brand audit;
- review conflict;
- human validation.

---

## 9.20 `Change Log`

Append-only audit log.

Columns:

- `change_id`
- `timestamp`
- `actor`
- `action`
- `sheet_name`
- `record_id`
- `field_name`
- `old_value`
- `new_value`
- `reason`
- `source_id`
- `ingestion_run_id`

Where Google Sheets API limitations make field-level logging expensive, the MVP may log record-level changes plus a JSON diff stored in Drive.

---

## 9.21 `Data Quality`

Generated issues table.

Columns:

- `issue_id`
- `detected_at`
- `severity`
- `issue_type`
- `sheet_name`
- `record_id`
- `field_name`
- `description`
- `suggested_fix`
- `assigned_to`
- `status`
- `resolved_at`

Initial checks:

- missing source;
- missing reporting period;
- invalid ID;
- duplicate entity;
- duplicate observation;
- unsupported currency;
- percentage outside 0–100;
- negative value where prohibited;
- normalised value without raw value;
- derived metric without inputs;
- subjective score without rationale;
- stale observation;
- conflicting high-confidence observations;
- group figure incorrectly labelled as brand figure;
- source URL unavailable;
- content hash changed;
- unknown metric definition;
- invalid controlled-vocabulary value.

---

## 9.22 `Summary`

Read-only or formula-generated view.

Initial outputs:

- pilot brand coverage;
- completeness by domain;
- latest traffic estimate;
- search-interest trend;
- latest available operator revenue;
- latest active-customer figure;
- revenue per active customer where valid;
- marketing percentage of revenue;
- current welcome offer;
- UX score;
- brand-positioning scores;
- reputation score;
- data confidence indicator;
- age of latest observation;
- research gaps.

The Summary sheet must never hide whether a value is operator-level or brand-level.

---

# 10. Sources to discover, download and ingest

## 10.1 Source priority

Use this hierarchy:

1. statutory and regulatory sources;
2. operator primary sources;
3. brand primary sources;
4. reputable measurement platforms;
5. reputable secondary reporting;
6. affiliate and review sources;
7. inference.

Conflicting sources are retained as separate observations. They are not silently reconciled.

---

## 10.2 Gambling regulators

### UK Gambling Commission

Track:

- annual industry statistics and downloadable Excel data;
- quarterly or periodic market overview data;
- business data covering GGY, bets/spins, active accounts and sessions;
- public register/licence information;
- enforcement and regulatory action;
- consultations and rule changes relevant to product or marketing design.

The Commission’s annual industry statistics provide downloadable source data, while its periodic market data includes sector-level GGY, bets/spins, active accounts and session measures. These are market benchmarks rather than individual-brand performance.

Initial official references:

- [UKGC annual industry statistics, April 2024–March 2025](https://www.gamblingcommission.gov.uk/statistics-and-research/publication/industry-statistics-annual-report-financial-year-april-2024-to-march-2025)
- [UKGC market overview, operator data to March 2026](https://www.gamblingcommission.gov.uk/statistics-and-research/publication/market-overview-operator-data-to-march-2026-published-may-2026)
- [UKGC gambling business data to March 2026](https://www.gamblingcommission.gov.uk/statistics-and-research/publication/gambling-business-data-on-gambling-to-march-2026-published-may-2026)

Ingestion methods:

- HTML table extraction;
- XLSX download and parsing;
- PDF download where present;
- periodic snapshot and content hash;
- manually verified licence-register capture if an API is unavailable.

Other regulators should be added where brands operate materially outside Great Britain, for example Malta, Gibraltar, Ireland, Sweden, Denmark, Ontario or selected US states.

---

## 10.3 Statutory company filings

Track:

- Companies House filings for UK entities;
- relevant overseas corporate registries;
- annual accounts;
- confirmation statements;
- ownership changes;
- charges and insolvency events;
- subsidiary relationships.

Extract:

- turnover;
- operating profit;
- net profit;
- employee counts;
- reporting period;
- audit qualifications;
- parent/subsidiary relationships;
- legal entity names and company numbers.

Limitations:

- small-company accounts may omit turnover;
- legal entities may serve several brands;
- consolidated group accounts may not expose UK brand performance;
- filing periods may be stale.

---

## 10.4 Public operator investor relations

For listed and debt-reporting operators, track:

- annual reports;
- interim and quarterly reports;
- results presentations;
- earnings releases;
- earnings-call transcripts;
- capital-markets-day materials;
- bond or lender presentations;
- acquisition announcements;
- geographic and product-segment notes.

Search for terms including:

```text
active customers
monthly active users
average monthly players
new depositing customers
marketing
sales and marketing
customer acquisition
CPA
cost per acquisition
retention
churn
revenue per player
ARPU
GGR
NGR
GGY
online casino
gaming revenue
bonuses
promotional costs
affiliate
VIP
direct traffic
```

Potential pilot operators should include a range of listed groups and private operators where evidence is available.

---

## 10.5 Brand websites

Capture:

- homepage;
- casino lobby;
- game-category pages;
- promotion pages;
- full promotional terms;
- registration journey;
- deposit and withdrawal information;
- verification/KYC information;
- responsible-gambling pages;
- complaints procedure;
- privacy and cookie notices;
- licence/footer information;
- VIP and loyalty programmes;
- affiliate programme;
- payment methods;
- customer-support channels.

For each capture, store:

- URL;
- capture timestamp;
- target geography;
- viewport/device;
- logged-in state;
- cookie state;
- screenshot;
- HTML snapshot where permitted;
- content hash;
- extracted structured data;
- source record.

Dynamic or personalised pages must be marked as such.

---

## 10.6 Traffic and SEO intelligence

Possible providers include Similarweb, Semrush, Ahrefs and equivalent services available under valid subscriptions.

Capture:

- estimated visits;
- visit trends;
- geography;
- device split;
- acquisition-channel shares;
- referring sites;
- paid and organic keywords;
- backlinks and referring domains;
- audience overlap where available.

Requirements:

- store provider name;
- store the provider’s data period;
- store export or screenshot;
- record subscription tier;
- record methodology notes;
- do not combine estimates from different providers without a comparison method;
- do not describe traffic estimates as active users.

---

## 10.7 Google Trends

Use for relative branded-search interest and share-of-search analysis.

Google states that Trends data is sampled, anonymised, categorised, aggregated and normalised to a 0–100 scale. It is not an absolute search-volume measure.

Official references:

- [Google Trends data FAQ](https://support.google.com/trends/answer/4365533?hl=en)
- [Export, embed and cite Trends data](https://support.google.com/trends/answer/4365538?hl=en-GB)
- [Compare search terms and topics](https://support.google.com/trends/answer/17309543)

Capture:

- exact search term or selected topic;
- geography;
- category;
- search surface;
- comparison-set brands;
- anchor term where used;
- date range;
- granularity;
- exported CSV;
- capture timestamp.

Do not compare index values collected in unrelated comparison sets without an anchoring or rescaling method.

---

## 10.8 App stores and mobile intelligence

Primary sources:

- Apple App Store;
- Google Play;
- operator download pages.

Third-party sources, where licensed:

- Sensor Tower;
- data.ai or successor services;
- AppMagic;
- Similarweb app intelligence.

Capture:

- app identity and developer;
- store country;
- rating and count;
- reviews count;
- version and update recency;
- ranking;
- estimated downloads;
- app description and screenshots;
- age rating;
- privacy declarations.

App-store availability may vary by geography and gambling regulation.

---

## 10.9 Advertising and sponsorship

Track:

- Advertising Standards Authority rulings;
- regulator enforcement;
- TV and digital advertisements;
- sponsorship announcements;
- football and sports partnerships;
- influencer partnerships;
- social advertising;
- creative libraries where legally accessible.

Capture:

- campaign period;
- creative proposition;
- offer;
- media/channel;
- target audience hypothesis;
- regulatory issue;
- ruling outcome;
- source.

This data is used to understand positioning and acquisition strategy, not to estimate spend precisely unless expenditure is disclosed.

---

## 10.10 Affiliate programmes and comparison sites

Potential sources:

- operator affiliate programme terms;
- affiliate networks;
- comparison and review sites;
- archived affiliate landing pages.

Capture:

- CPA amounts or ranges;
- revenue-share rates;
- hybrid structures;
- negative carryover;
- minimum player requirements;
- qualifying jurisdictions;
- sub-affiliate permissions;
- payment frequency;
- programme restrictions;
- prominence on comparison sites;
- ranking and offer copy.

Affiliate terms may be negotiated, private or outdated. Record the exact capture date and confidence.

---

## 10.11 Review and complaint sources

Potential sources:

- Trustpilot;
- Casino Guru;
- AskGamblers;
- app-store reviews;
- social channels;
- regulator complaints information where aggregated.

Capture aggregate measures and recurring themes:

- withdrawal delay;
- account closure;
- KYC friction;
- bonus disputes;
- support quality;
- technical failures;
- perceived fairness;
- responsible-gambling interventions.

Do not treat review ratings as representative customer satisfaction without qualification. Review platforms have selection bias and potential manipulation.

---

## 10.12 News and trade publications

Use for:

- acquisitions;
- launches and closures;
- executive statements;
- sponsorships;
- market-entry changes;
- layoffs or restructures;
- enforcement;
- leaked or reported commercial metrics.

Prefer original company announcements and filings where available. Secondary reporting must identify the quoted primary source.

---

# 11. Ingestion architecture

## 11.1 Components

The MVP should contain:

1. **Source registry**
   - reads the `Sources` sheet;
   - discovers due sources;
   - creates research tasks.

2. **Fetcher**
   - downloads HTML, PDF, XLSX, CSV and JSON;
   - respects terms, access controls and rate limits;
   - writes files to Google Drive;
   - calculates hashes.

3. **Parser**
   - extracts text and tables;
   - records parser name/version;
   - emits structured candidate facts.

4. **Extractor**
   - maps candidate facts to metric definitions;
   - captures source locators and excerpts;
   - assigns preliminary evidence and confidence.

5. **Normalizer**
   - parses dates, currencies, percentages and units;
   - creates normalised values;
   - never destroys raw values.

6. **Validator**
   - runs schema and business rules;
   - sends invalid records to `Data Quality`.

7. **Writer**
   - appends records through the Google Sheets API;
   - uses idempotency keys;
   - logs changes.

8. **Reviewer workflow**
   - exposes unreviewed records;
   - supports approval, rejection and correction.

9. **Derived-metric job**
   - calculates only approved formulas from approved inputs;
   - records lineage.

10. **Summary generator**
    - refreshes human-readable comparisons.

---

## 11.2 Recommended implementation stack

The coding agent may choose alternatives, but a straightforward implementation is:

- Python 3.12+;
- Pydantic for schemas and validation;
- Google Sheets API;
- Google Drive API;
- `httpx` for HTTP;
- `beautifulsoup4` or `selectolax` for HTML;
- `pandas` and `openpyxl` for spreadsheets;
- `pypdf` or `PyMuPDF` for PDF text;
- table extraction library selected per document;
- Playwright for permitted dynamic-page capture;
- `tenacity` for retries;
- structured JSON logging;
- pytest;
- optional SQLite cache for local execution state.

OCR should be a last resort. Prefer native PDF text and table extraction.

---

## 11.3 Ingestion run

Each run receives an `ingestion_run_id`.

Workflow:

```text
Select due sources
    ↓
Check access policy and source status
    ↓
Fetch source
    ↓
Hash and archive
    ↓
Skip extraction if unchanged and no forced reparse
    ↓
Parse into document model
    ↓
Extract candidate observations
    ↓
Normalise
    ↓
Validate
    ↓
Deduplicate
    ↓
Append as unreviewed
    ↓
Create data-quality issues
    ↓
Human review
    ↓
Approve observations
    ↓
Recalculate derived metrics
    ↓
Refresh summary
```

---

## 11.4 Idempotency and deduplication

Create an observation fingerprint from:

```text
subject_id
metric_id
period_start
period_end
as_of_date
geography
segment
source_id
raw_value
```

A repeated run against an unchanged source must not create duplicate rows.

Where a source changes at the same URL:

- preserve prior document;
- store new content hash;
- create a new document record;
- compare extracted observations;
- supersede only after review.

---

## 11.5 Extraction output contract

Each parser/extractor emits JSON similar to:

```json
{
  "subject": {
    "type": "operator",
    "id": "operator_..."
  },
  "metric_id": "active_customers",
  "raw_value": "4.2 million",
  "raw_unit": "customers",
  "normalised_numeric_value": 4200000,
  "normalised_unit": "customers",
  "period_start": "2026-01-01",
  "period_end": "2026-03-31",
  "geography": "GB",
  "segment": "online",
  "source_id": "source_...",
  "document_id": "document_...",
  "source_locator": "page 18, KPI table",
  "verbatim_excerpt": "Active customers ...",
  "evidence_type": "reported_primary",
  "confidence": "high",
  "definition_id": "active_customer_operator_defined",
  "comparability_status": "partially_comparable",
  "methodology_note": "Definition taken from report footnote.",
  "review_status": "unreviewed"
}
```

---

# 12. Metric definitions

Create a metric-definition registry in `Config` or a dedicated hidden/reference sheet.

Each metric requires:

- metric ID;
- display name;
- description;
- subject types;
- data type;
- allowed units;
- aggregation behaviour;
- preferred reporting frequency;
- denominator definition;
- comparability group;
- validation rules;
- calculation formula where derived;
- known caveats.

Example:

```yaml
metric_id: estimated_monthly_visits
display_name: Estimated monthly website visits
subject_types:
  - brand
data_type: number
allowed_units:
  - visits
evidence_types:
  - third_party_estimate
aggregation: do_not_sum_across_providers
comparability_group: web_visits_provider_period_device
caveats:
  - Not unique visitors
  - Not active customers
  - May exclude app traffic
  - Provider estimates may be inaccurate for small sites
```

---

# 13. Human audit protocol

## 13.1 Standard environment

For comparable audits, define:

- geography: Great Britain;
- language: English;
- desktop viewport;
- mobile viewport;
- browser;
- incognito or clean profile;
- cookies accepted/rejected consistently;
- logged-out state;
- test date and time;
- network profile.

## 13.2 Required evidence

Every UX or brand audit should include:

- homepage screenshot;
- promotions screenshot;
- lobby screenshot;
- registration screenshots up to the permitted stop point;
- footer/licence screenshot;
- responsible-gambling screenshot;
- notes explaining scores.

## 13.3 Inter-rater calibration

Before scoring all pilot brands:

1. two auditors independently score three brands;
2. compare disagreements;
3. refine rubrics;
4. repeat until scores are reasonably consistent;
5. record rubric version.

---

# 14. Pilot dataset

Select 15–20 brands using stratified sampling.

The pilot should include:

- large listed operator brands;
- casino-only challenger brands;
- sportsbook-led casino brands;
- mobile-first brands;
- premium or VIP-positioned brands;
- strongly promotional/bonus-led brands;
- distinctive entertainment-led brands;
- at least one crypto-native comparator, clearly separated from GB-licensed comparisons;
- brands with strong and weak customer sentiment;
- brands with high and low estimated traffic.

Selection criteria:

- relevance to intended target market;
- availability of public evidence;
- variety of proposition and design;
- operator diversity;
- sufficient scale for traffic estimates;
- lawful accessibility from the research geography.

The exact list should be stored in `Brands` with a documented sampling rationale.

---

# 15. Update frequencies

| Data type | Suggested frequency |
|---|---|
| Regulatory market statistics | On publication |
| Annual reports | Annually |
| Interim/quarterly results | Quarterly |
| Licence status | Monthly |
| Traffic estimates | Monthly |
| Google Trends | Monthly |
| Welcome offers | Weekly |
| Homepage and lobby capture | Monthly |
| Affiliate terms | Monthly |
| App ratings/version | Monthly |
| Review-platform aggregates | Monthly |
| UX audit | Quarterly or after major redesign |
| Brand audit | Quarterly or after major redesign |
| Regulatory/ASA actions | Weekly |
| News and ownership changes | Weekly |

The MVP does not need a scheduler, but `Research Queue` must store due dates so scheduling can be added later.

---

# 16. Security, privacy and compliance

The implementation must:

- use service-account or OAuth credentials stored outside the workbook;
- follow least-privilege access;
- avoid storing secrets in Sheets;
- record access and ingestion failures without exposing credentials;
- respect source terms, robots rules and rate limits;
- avoid circumventing paywalls or authentication;
- avoid collecting player personal data;
- aggregate or paraphrase reviews;
- stop automated journeys before financial or legally binding actions;
- permit source deletion or suppression where legally required;
- make clear that brand and UX analysis does not constitute legal advice.

---

# 17. Google Sheets implementation requirements

## 17.1 API behaviour

- Use batch reads and batch writes.
- Avoid cell-by-cell API calls.
- Append records using stable IDs.
- Implement retries with exponential backoff.
- Respect quotas.
- Verify writes after completion.
- Never reorder source sheets destructively.
- Do not allow formulas in imported text to execute unexpectedly; escape values beginning with `=`, `+`, `-` or `@` where appropriate.
- Protect generated columns and summary formulas.
- Freeze headers.
- Apply filters.
- Use named ranges for configuration lists.
- Use data validation.
- Use conditional formatting for confidence and quality issues.
- Store dates as dates, not locale-dependent text.

## 17.2 Sheet limits

Google Sheets has finite cell and performance limits. The MVP should:

- keep large extracted text outside Sheets;
- avoid inserting raw HTML;
- avoid image blobs;
- archive source files in Drive;
- consider splitting observations by year if volume becomes problematic;
- include an export-to-CSV command;
- monitor row counts and workbook latency.

## 17.3 Schema versioning

Store:

- `schema_version` in `README`;
- migration scripts in the repository;
- a migration log;
- backward-compatible column additions where possible.

Do not rename or remove columns without a migration.

---

# 18. Repository structure

Recommended structure:

```text
casino-intelligence/
  README.md
  pyproject.toml
  .env.example
  config/
    metrics.yaml
    vocabularies.yaml
    sources.yaml
    audit-rubrics.yaml
  src/
    casino_intel/
      models/
      sheets/
      drive/
      fetching/
      parsing/
      extraction/
      normalisation/
      validation/
      derivation/
      reporting/
      cli/
  tests/
    unit/
    integration/
    fixtures/
  scripts/
    initialise_workbook.py
    ingest_source.py
    import_ukgc.py
    validate_workbook.py
    refresh_summary.py
    export_csv.py
  docs/
    requirements.md
    runbook.md
    source-policy.md
    metric-definitions.md
```

---

# 19. Command-line interface

The MVP should expose commands similar to:

```bash
casino-intel initialise-workbook
casino-intel add-source --url URL --type TYPE
casino-intel fetch-source --source-id SOURCE_ID
casino-intel ingest-source --source-id SOURCE_ID
casino-intel import-file --path FILE
casino-intel validate
casino-intel derive
casino-intel refresh-summary
casino-intel export --output exports/
casino-intel research-queue list
casino-intel research-queue run --limit 10
```

All commands must support dry-run mode where they can mutate data.

---

# 20. Testing requirements

## 20.1 Unit tests

Cover:

- ID generation;
- metric validation;
- date parsing;
- currency parsing;
- percentage parsing;
- FX normalisation;
- observation fingerprints;
- confidence rules;
- comparability rules;
- formula calculations;
- sheet row serialisation;
- formula-injection protection.

## 20.2 Integration tests

Cover:

- creating a test workbook;
- writing and reading records;
- ingesting a known HTML page;
- ingesting a known PDF;
- ingesting a known XLSX file;
- unchanged-source idempotency;
- changed-source versioning;
- data-quality issue creation;
- export and re-import.

## 20.3 Golden fixtures

Maintain stable fixtures for:

- UKGC XLSX;
- operator annual-report PDF;
- promotion terms HTML;
- traffic CSV export;
- Google Trends CSV;
- app-store capture;
- UX audit JSON.

External pages may change, so parser tests should not depend solely on live network access.

---

# 21. MVP acceptance criteria

The initial implementation is accepted when:

1. The workbook is created with all required tabs and headers.
2. Controlled vocabularies and validations are active.
3. At least 15 pilot brands and their operators are registered.
4. Every material fact can be traced to a source.
5. At least three source formats are ingested automatically: HTML, PDF and XLSX/CSV.
6. UKGC market data is imported into canonical observations.
7. At least three operator financial reports are parsed into reviewed observations.
8. At least ten brands have current offer captures.
9. At least ten brands have traffic or search-interest observations.
10. At least five brands have completed UX and brand audits.
11. The system distinguishes brand-level, operator-level and market-level data.
12. Derived metrics retain formulas and input lineage.
13. Re-running an unchanged ingestion does not duplicate records.
14. Invalid records appear in `Data Quality`.
15. A complete CSV export is available.
16. The Summary sheet presents comparable fields and visibly marks estimates and missing data.
17. Secrets are not stored in the workbook or repository.
18. The repository includes setup documentation and a runbook.

---

# 22. Implementation phases

## Phase 1: Workbook and schema

- create workbook;
- create tabs;
- add headers and formatting;
- load controlled vocabularies;
- implement IDs;
- implement Sheets/Drive clients;
- add validation and change logging.

## Phase 2: Primary-source ingestion

- source registry;
- generic fetcher;
- archive and hashing;
- UKGC HTML/XLSX importer;
- PDF parser;
- operator report extraction;
- human review workflow.

## Phase 3: Brand observation

- brand website capture;
- offers parser;
- screenshot storage;
- UX and brand audit forms;
- app-store capture.

## Phase 4: Market intelligence

- traffic CSV import;
- Google Trends CSV import;
- SEO data import;
- review aggregates;
- acquisition estimates.

## Phase 5: Analysis

- derived metrics;
- summary views;
- completeness scoring;
- research-gap generation;
- export package;
- migration assessment for PostgreSQL.

---

# 23. Future PostgreSQL migration

The Sheets model should map to tables including:

```text
operators
brands
brand_operator_relationships
licences
sources
documents
metric_definitions
observations
offers
audits
research_tasks
ingestion_runs
data_quality_issues
change_events
```

Migration triggers:

- workbook approaches performance limits;
- observations exceed approximately 50,000–100,000 rows;
- multiple agents write concurrently;
- scheduled ingestion becomes routine;
- application or dashboard requires query performance;
- stronger transactional guarantees are needed.

Sheets should then become an editorial and reporting interface over PostgreSQL rather than the system of record.

---

# 24. Important analytical limitations

The system must display these caveats prominently:

- Website visits are not active players.
- Registered accounts are not depositing customers.
- “Active customer” definitions vary by operator.
- Group revenue cannot generally be assigned precisely to one brand.
- Group marketing expenditure is not brand CPA.
- Affiliate offers are not necessarily the operator’s realised average acquisition cost.
- Google Trends is a relative index, not absolute volume.
- Review ratings are affected by selection and platform bias.
- App downloads do not equal active users.
- Revenue is not GGR, NGR, GGY or profit unless the source defines it that way.
- Quarterly active counts should not be naively summed.
- A range with explicit assumptions is preferable to a fabricated point estimate.
- Correlation between design traits and performance does not prove causation.

---

# 25. Definition of success

The MVP succeeds if it enables an analyst to select a group of online casino brands and answer:

- what is known;
- what is estimated;
- how reliable each value is;
- where it came from;
- whether it is genuinely comparable;
- what remains unknown;
- which commercial, brand and UX patterns appear worth investigating.

The database should support evidence-informed brand design without pretending that incomplete public data provides certainty it does not possess.
