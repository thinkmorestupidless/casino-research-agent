# Feature Specification: Online Casino Competitive Intelligence Database

**Feature Branch**: `001-casino-competitive-intelligence`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "this document contains the full spec for the system i want to build /Users/thinkmore/Downloads/online-casino-competitive-intelligence-requirements.md" — a full requirements document (v0.1, 24 July 2026) for a source-backed competitive intelligence dataset covering GB-facing online casino brands, to be built as a Google Sheets workbook with a supporting ingestion pipeline, with an explicit future migration path to PostgreSQL.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy foundation of brands, operators and sourced facts (Priority: P1)

A researcher needs to register the brands and operators under study, and record facts about them such that every fact can always be traced back to where it came from, when it was captured, and how reliable it is. Without this foundation, no other analysis in the system is trustworthy.

**Why this priority**: This is the load-bearing structure of the whole system. Every other capability (ingestion, audits, derived metrics, summaries) depends on brands, operators, sources and observations being modeled as distinct, linked records with stable identity. If this is wrong, every later capability inherits the flaw.

**Independent Test**: Register one operator, one brand belonging to that operator, one source (e.g. a regulator webpage), and one observation citing that source (e.g. "estimated monthly visits, June 2026"). Confirm the observation displays its evidence type, confidence level, and a working link back to the exact source — and that adding a second, later observation for the same brand/metric does not overwrite the first. Delivers value on its own: a small, fully-traceable fact base an analyst can already query and trust.

**Acceptance Scenarios**:

1. **Given** an operator and a brand it owns have been registered, **When** a researcher records a new fact about the brand (e.g. a traffic estimate), **Then** the fact is stored as a new, dated observation linked to a specific source, without altering or deleting any previously recorded observation for that brand.
2. **Given** two different sources report conflicting values for the same brand and metric in the same period, **When** both are recorded, **Then** both observations are retained side-by-side with their own confidence and evidence type, and neither silently overwrites or averages the other.
3. **Given** a monetary observation is reported in a foreign currency, **When** it is recorded, **Then** the original value and currency are preserved alongside any normalised GBP value, the exchange rate used, and the conversion date.
4. **Given** a stable identifier scheme, **When** any record is created, **Then** it receives a permanent, human-readable ID that does not depend on its position in a sheet or on the brand's current name.

---

### User Story 2 - Automated ingestion of public documents into reviewable facts (Priority: P2)

A researcher wants the system to automatically fetch, read and extract facts from publicly available regulator statistics, operator financial reports and structured data files, so that building the fact base does not require manually retyping every number from every document.

**Why this priority**: Manual entry alone does not scale to the volume of regulatory filings, annual reports and structured exports needed for even a 15–20 brand pilot. Automated ingestion is the highest-leverage capability after the data foundation exists, and it is the first place where the model's guarantees (traceability, non-overwrite, evidence typing) get stress-tested against messy real-world documents.

**Independent Test**: Point the system at a known regulator statistics page (HTML with a downloadable spreadsheet), a known operator annual report (PDF), and a known structured export (CSV/XLSX). Run ingestion once and confirm each produces one or more candidate observations awaiting review, each with a source reference, an extraction locator (e.g. page/table), and a preliminary evidence type and confidence. Run ingestion again against the same unchanged documents and confirm no duplicate observations are created.

**Acceptance Scenarios**:

1. **Given** a regulator publishes a downloadable statistics file, **When** the system ingests it, **Then** the relevant figures appear as new observations tagged with evidence type, source, and the reporting period they cover.
2. **Given** an operator's annual report PDF contains a table of key performance figures, **When** the system ingests it, **Then** each extracted figure records the page/table it came from and a short supporting excerpt, and is marked as unreviewed pending human approval.
3. **Given** a source document has not changed since the last ingestion run, **When** ingestion is run again, **Then** no duplicate observations are created for that source and period.
4. **Given** a source is later updated at the same URL, **When** the system re-fetches it, **Then** the prior downloaded document is preserved, a new document version is recorded with its own content hash, and any resulting change to observations is held for human review before superseding the prior value.
5. **Given** an extracted record fails a basic validation rule (e.g. missing source, invalid currency, percentage outside 0–100), **When** ingestion runs, **Then** the record is flagged as a data quality issue rather than silently accepted.

---

### User Story 3 - Manual UX and brand audits with photographic evidence (Priority: P3)

A researcher or designer wants to systematically score each brand's registration journey, promotional clarity, visual identity and positioning using a consistent rubric, with every score backed by a written rationale and screenshot evidence, so that subjective judgements are structured, comparable and defensible rather than ad hoc impressions.

**Why this priority**: Brand and UX signals are central to the stated purpose (informing proposition design and website UX) but cannot be automated safely or credibly — they require human judgement. This capability is independent of the ingestion pipeline and can be exercised as soon as brands are registered (User Story 1), making it valuable on its own even before automated ingestion (User Story 2) is complete.

**Independent Test**: Conduct one full UX audit and one full brand audit for a single registered brand, following the standard capture environment (fixed geography, viewport, logged-out state, etc.), stopping before any account creation, deposit or wager. Confirm every numeric score has an accompanying rationale, and that homepage, lobby, promotions and footer/licence screenshots are attached and retrievable.

**Acceptance Scenarios**:

1. **Given** a brand is registered, **When** an auditor completes a UX audit, **Then** the audit records device, viewport, geography, logged-in state and date, plus one score-with-rationale pair for each rubric dimension (e.g. promotion clarity, trust signals, navigation).
2. **Given** an audit is being conducted, **When** the auditor reaches the point of submitting identity documents, accepting binding terms, depositing funds, placing a wager or withdrawing funds, **Then** the automated or guided journey stops before that action.
3. **Given** a numeric score is entered without a supporting rationale, **When** the audit is saved, **Then** the system treats it as invalid and requires a rationale before acceptance.
4. **Given** two auditors independently score the same three brands during calibration, **When** their scores are compared, **Then** the rubric version used is recorded so disagreements can be traced to a specific rubric definition.

---

### User Story 4 - Derived metrics with transparent formulas and lineage (Priority: P4)

An analyst wants selected commercial ratios (such as revenue per active customer, marketing spend as a percentage of revenue, or traffic growth) calculated automatically from stored observations, with the formula, inputs and assumptions always visible, so that comparisons across brands are consistent and any number can be traced back to exactly what produced it.

**Why this priority**: Derived metrics are only meaningful once a base of approved observations exists (User Stories 1–2), and they are explicitly lower-risk to defer than the raw fact base or audits, since a partially-manual calculation is an acceptable interim state. This is a clear enhancement on top of the data foundation rather than a prerequisite for it.

**Independent Test**: With two approved observations available for a single brand or operator (e.g. a revenue figure and an active-customer figure for compatible periods), trigger the relevant derived-metric calculation and confirm the result stores the formula used, the exact input observation IDs, any assumptions, and a resulting confidence/comparability status — and that the calculation is skipped (not guessed) when the periods or definitions are not sufficiently compatible.

**Acceptance Scenarios**:

1. **Given** compatible revenue and active-customer observations exist for the same subject and period, **When** the derived-metric job runs, **Then** a new derived metric record is created showing the formula, the specific input observation IDs, and the calculated value.
2. **Given** the only available inputs use incompatible reporting periods or incompatible definitions, **When** the derived-metric job runs, **Then** no value is fabricated, and the gap is left visible rather than silently estimated.
3. **Given** an underlying input observation is later superseded, **When** the derived metric is recalculated, **Then** the new calculation is stored as a new derived-metric record rather than overwriting the previous one, preserving history.

---

### User Story 5 - Comparative summary across the brand set (Priority: P5)

An analyst wants a single view that compares brands side-by-side across traffic, financial, offer, audit and reputation signals, clearly marking whether each figure is a hard fact, an estimate, or a brand-level versus operator-level number, and highlighting where data is missing, so that strategic conclusions are drawn from an honest picture rather than an implied false precision.

**Why this priority**: This is the payoff view that makes the whole dataset usable for decision-making, but it is a read-only projection over data produced by the previous four capabilities — it has no value until they exist, so it is correctly last in build order even though it is highly visible to end users.

**Independent Test**: With a handful of brands populated with mixed data completeness (some with full financials and audits, some with only traffic estimates), generate the summary view and confirm it shows, per brand, the latest values for each tracked signal, an explicit confidence/estimate indicator, an explicit operator-level-vs-brand-level marker where relevant, the age of the latest observation, and a visible list of remaining research gaps for that brand.

**Acceptance Scenarios**:

1. **Given** brands with varying data completeness, **When** the summary is generated, **Then** every displayed figure is marked with its confidence and whether it is a reported fact, an estimate, or a derived value.
2. **Given** a financial figure is only available at operator (group) level, **When** it is shown for a brand in the summary, **Then** it is explicitly labelled as operator-level rather than presented as if it were brand-specific.
3. **Given** a brand has no recent observation for a tracked signal, **When** the summary is generated, **Then** the gap is visibly flagged as missing/stale rather than left blank or backfilled with an assumption.

---

### Edge Cases

- What happens when a source is discovered to be paywalled or requires authentication after it has already been added to the research queue? The system must record it as inaccessible under current permissions rather than attempting to bypass access controls.
- How does the system handle a metric whose value is reported at group/operator level with no reliable way to allocate it to an individual brand? The value must be stored at the correct (operator) subject level and never silently attributed to a brand; an attempted allocation must record its method, assumptions and resulting confidence.
- How does the system handle two third-party providers (e.g. two traffic-estimate vendors) reporting different numbers for the same brand and period? Both are retained as separate observations tagged with their provider and are never merged or averaged into a single "true" value.
- What happens when a previously recorded source becomes unavailable at its original URL (link rot, takedown, legal request)? The source record is marked unavailable/status-changed rather than deleted, preserving the audit trail, while still permitting removal of content where legally required.
- What happens when a controlled vocabulary value (e.g. an evidence type, currency code, or metric ID) does not exist yet for a newly encountered case? The record is flagged as a data quality issue (unknown/invalid controlled-vocabulary value) rather than silently accepted with a free-text guess.
- How does the system handle a subjective audit score submitted without a written rationale? It is rejected as incomplete; a score without rationale is never considered valid.
- What happens when an automated capture reaches a step that would require creating an account, submitting ID, depositing funds, wagering, or withdrawing? The capture stops before that step every time, regardless of how much additional data could be obtained by continuing.
- How does the system handle Google Trends-style relative index values collected in different comparison sets? They are never compared directly across unrelated comparison sets without an explicit anchoring or rescaling method recorded alongside the values.
- What happens if re-running ingestion against a source produces the exact same facts as before? No duplicate observations are created; the run is idempotent for unchanged sources.
- How does the system handle personal data encountered incidentally while reviewing customer complaints or reviews? Only aggregated, paraphrased themes and counts are retained; individual usernames, personal data and full review text are not stored.

## Requirements *(mandatory)*

### Functional Requirements

**Data foundation, identity and provenance**

- **FR-001**: System MUST maintain distinct, linked record types for brands, operators, licences, sources, documents and observations, such that a fact (observation) is never conflated with the entity it describes (brand/operator) or the source it came from.
- **FR-002**: System MUST assign every record a stable, unique, immutable, human-readable identifier at creation time; row position or brand/operator name MUST NOT be used as a key.
- **FR-003**: System MUST record, for every record where applicable: creation timestamp and creator, last-update timestamp, record status (active/superseded/rejected/needs review), free-text notes, a link to its source, an optional link to a supporting document, evidence type, confidence, review status, capture timestamp, and the validity/reporting period the fact applies to.
- **FR-004**: System MUST treat every new fact capture as an additive observation with its own capture date and reporting period; it MUST NOT overwrite or delete a prior observation for the same subject and metric.
- **FR-005**: System MUST retain, for any numeric fact reported in a non-GBP currency, the original value and currency, the normalised GBP value, the exchange rate used, the conversion date and the calculation method.
- **FR-006**: System MUST classify every observation with exactly one evidence type from a fixed set (reported directly by the primary party, reported by a secondary source, calculated/derived, third-party estimate, directly observed, structured human judgement, inferred range, or unknown).
- **FR-007**: System MUST classify every observation with a confidence level (high, medium, low, or unknown), applying documented rules for what qualifies as each level (e.g. exact primary source with no ambiguity is high; weak, stale, or conflicting sources are low).
- **FR-008**: System MUST record, for every numeric observation, a definition reference, a comparability grouping, and a comparability status (comparable, partially comparable, not comparable, or unknown), plus a free-text comparability note where relevant.
- **FR-009**: System MUST maintain user-inspectable controlled vocabularies (not hidden in code) for countries, currencies, evidence types, confidence values, review statuses, source types, product verticals, acquisition channels, offer types, device types, audit score ranges, operator ownership types, brand/licence status values, comparability statuses, metric definitions and units, and MUST reject or flag values outside these vocabularies.
- **FR-010**: System MUST NOT allow terms such as "active customer," "monthly active account," "unique visitor," "depositor," and "registered account" to be treated as interchangeable; each recorded metric MUST carry its own definition reference.

**Source and document management**

- **FR-011**: System MUST register every source used, capturing at minimum its type, publisher, title, URL, publication date (where known), retrieval timestamp, reporting period (where applicable), whether it is a primary source, whether it is paywalled or requires authentication, any access restrictions, a content hash of the retrieved material, an archived copy location, a preferred citation, and a status.
- **FR-012**: System MUST retain downloaded or captured documents (HTML snapshots, PDFs, spreadsheets, screenshots) as archived files with references and content hashes from the fact records, rather than storing large raw content inline with the facts themselves.
- **FR-013**: System MUST NOT attempt to access paywalled or authentication-required sources without permission, MUST NOT bypass anti-bot or access controls, and MUST respect publisher terms and rate limits.
- **FR-014**: System MUST prioritise source discovery in the order: statutory/regulatory sources, operator primary sources, brand primary sources, reputable measurement platforms, reputable secondary reporting, affiliate/review sources, then inference — without silently reconciling conflicting sources found at different priority levels.

**Automated ingestion**

- **FR-015**: System MUST be able to ingest at least three structured/semi-structured source formats automatically: HTML tables, PDF documents, and spreadsheet exports (CSV/XLSX).
- **FR-016**: System MUST, for each ingested fact, record the exact source locator it was extracted from (e.g. page, table, row, heading, or on-page location) and a short supporting excerpt.
- **FR-017**: System MUST assign a preliminary evidence type and confidence to every machine-extracted fact and MUST mark it as unreviewed pending human validation before it is treated as approved.
- **FR-018**: System MUST detect when a source is unchanged since its last successful ingestion and MUST skip re-extraction and avoid creating duplicate observations in that case.
- **FR-019**: System MUST detect when a source has changed at the same location, preserve the prior archived document, create a new document record with its own content hash, and hold any resulting change to observations for human review before it supersedes the prior value.
- **FR-020**: System MUST run all extracted facts through validation before acceptance and MUST route records that fail validation (missing source, missing reporting period, invalid ID, duplicate entity/observation, unsupported currency, out-of-range percentage, prohibited negative value, normalised value without a raw value, derived metric without recorded inputs, subjective score without rationale, stale observation, conflicting high-confidence observations, group figure mislabelled as brand figure, unreachable source URL, changed content hash, unknown metric, or invalid controlled-vocabulary value) to a visible data-quality queue rather than accepting them silently.
- **FR-021**: System MUST support a human review workflow allowing unreviewed records to be approved, rejected, or corrected, and MUST distinguish machine-checked, human-reviewed, and approved states.

**Financial and commercial data**

- **FR-022**: System MUST NOT allocate group/operator-level financial or customer figures to an individual brand without explicit labelling of the allocation method, assumptions, resulting range, confidence, and the input observations used.
- **FR-023**: System MUST record operator financial observations (e.g. revenue, gross gaming revenue/yield, net gaming revenue, operating/net profit, marketing expense, affiliate expense, bonus and promotion expense, gaming tax, employee counts) with their reporting period, currency, segment, territory, and whether the figure is reported or derived.
- **FR-024**: System MUST support recording indicative acquisition-cost ranges (e.g. cost-per-acquisition) built from multiple possible inputs (reported figures, affiliate offer terms, paid-search cost data, allocation assumptions) and MUST NOT present a group-level marketing-expense-derived figure as a precise brand-level acquisition cost without labelling it as a group-level proxy.

**Traffic, search interest and app presence**

- **FR-025**: System MUST record brand-level traffic estimates per provider, domain and period, including channel-mix shares, and MUST NOT merge or average estimates from different providers as though they were measured identically.
- **FR-026**: System MUST record branded search-interest observations with their comparison set, anchor term (where used), geography, platform and granularity, and MUST NOT compare index values collected under different, unrelated comparison sets without a documented anchoring or rescaling method.
- **FR-027**: System MUST record mobile app presence per platform and store-country, including rating, review/rating counts, version/update recency, ranking and download estimates where available, while treating download estimates as distinct from active-user counts.

**Offers, product and reputation**

- **FR-028**: System MUST capture promotional offers from full terms (not headline text alone), including bonus mechanics, wagering requirements, qualifying/excluded games, time limits, withdrawal caps and a terms-clarity assessment, each linked to its source and capture date.
- **FR-029**: System MUST capture product/game-catalogue observations per brand (vertical coverage, provider count, live casino/jackpot/sportsbook/bingo/poker availability, discovery features) with source and confidence.
- **FR-030**: System MUST capture reputation/review-platform observations as aggregated scores and paraphrased recurring themes (e.g. withdrawal delay, KYC friction, bonus disputes) and MUST NOT store individual usernames or full review text.

**Human audits**

- **FR-031**: System MUST support structured UX audits and brand/visual-identity audits per brand, capturing a fixed capture environment (geography, viewport/device, logged-in state, cookie state, date/time) and a defined set of 1–5 rubric scores, each requiring a written rationale to be considered valid.
- **FR-032**: System MUST require supporting screenshot evidence for each audit (at minimum: homepage, promotions, lobby, registration up to the permitted stop point, footer/licence, and responsible-gambling information).
- **FR-033**: System MUST ensure that any guided or automated research journey stops before submitting identity documents, accepting legally binding terms, depositing funds, placing a wager, or withdrawing funds.
- **FR-034**: System MUST record a rubric version against every audit so that scores can be traced to the specific rubric definition used at the time, supporting inter-rater calibration.

**Derived metrics**

- **FR-035**: System MUST calculate derived metrics (e.g. revenue per active customer, GGY per average monthly active account, marketing expense as a percentage of revenue, EBITDA margin, traffic growth year-on-year, share of search) only from approved input observations, and MUST record the formula, formula version, exact input observation IDs, and any assumptions used.
- **FR-036**: System MUST skip a derived-metric calculation rather than fabricate a value when the underlying input periods or definitions are not sufficiently compatible, and MUST record the resulting comparability status alongside any value it does produce.
- **FR-037**: System MUST preserve prior derived-metric results as history when recalculation occurs (e.g. after an input observation is superseded), rather than overwriting them in place.

**Change tracking and data quality**

- **FR-038**: System MUST maintain an append-only change log capturing, at minimum, the actor, action, affected record, changed field(s), old and new values (or a linked diff), reason, source and ingestion-run identifier for every material change.
- **FR-039**: System MUST maintain a visible data-quality issue log that records detected problems with severity, affected record/field, description, suggested fix, assignment and resolution status.
- **FR-040**: System MUST generate research tasks (e.g. discover source, download/parse document, extract metric, verify licence, perform audit, resolve conflict, human validation) with priority, status, attempt tracking and blocking-issue notes, so that outstanding work is trackable even without an automated scheduler.

**Access, interface and reporting**

- **FR-041**: System MUST provide a single, human-inspectable workbook (Google Sheets) as the primary interface for browsing, entering and reviewing data, containing distinct areas for reference data (README/config/controlled vocabularies), master entities (brands/operators/licences), provenance (sources/documents), the canonical fact table (observations), domain-specific views (financials, traffic, search interest, acquisition, offers, products, UX audits, brand audits, reputation, app presence), derived metrics, work tracking (research queue), governance (change log, data quality) and a comparative summary.
- **FR-042**: System MUST protect against spreadsheet formula injection when importing external text (e.g. values beginning with `=`, `+`, `-`, or `@` must be neutralised or escaped appropriately) and MUST NOT allow imported data to execute unexpected formulas.
- **FR-043**: System MUST support exporting a complete copy of the dataset to a portable, non-proprietary format (e.g. CSV) on demand.
- **FR-044**: System MUST record a schema version and last successful ingestion/review timestamps in a visible, discoverable location, and MUST support additive schema changes without silently renaming or removing existing fields.
- **FR-045**: System MUST cover an initial pilot of 15–20 brands, selected to represent a range of operator scale, proposition (challenger, sportsbook-led, premium, bonus-led, crypto-native), sentiment and traffic scale, with the sampling rationale documented alongside the brand records.

**Safety, privacy and scope boundaries**

- **FR-046**: System MUST NOT create player accounts, submit identity verification, make deposits, place wagers, or withdraw funds as part of any automated or guided research activity.
- **FR-047**: System MUST NOT collect personal data about individual gamblers, and MUST aggregate/paraphrase any review or complaint content rather than storing raw personal text.
- **FR-048**: System MUST NOT bypass anti-bot controls, authentication, or website terms of use during data collection.
- **FR-049**: System MUST NOT present a subjective brand/UX score as validated unless it has passed the documented human-review rubric process; automated scoring is not a substitute for human review.
- **FR-050**: System MUST store access credentials for any external system (e.g. Sheets/Drive API access) outside the workbook itself and MUST NOT record secrets in any user-facing record.

### Key Entities

- **Brand**: A consumer-facing casino brand (e.g. its public name, domain(s), status, type, target markets, app/crypto support, launch date). Belongs to one operator.
- **Operator**: The corporate entity or group that owns/operates one or more brands (ownership type, listing/ticker, headquarters, reporting currency, financial year end).
- **Licence**: A regulator/jurisdiction relationship held by an operator (and optionally a specific brand), including licence number, type, status and validity dates.
- **Source**: A retrievable, citable origin of information (regulator publication, filing, operator report, website page, traffic/SEO tool export, app store listing, review platform, news article, etc.), with access, quality and provenance metadata.
- **Document**: A specific downloaded or captured artifact tied to a source (PDF, HTML snapshot, spreadsheet, screenshot), with hash, storage location and extraction status.
- **Observation**: The canonical, time-indexed fact record — a value for a metric, about a subject (brand/operator/market/licence/offer/app), for a period, sourced from a document/source, tagged with evidence type, confidence and comparability.
- **Financial / Traffic / Search Interest / Acquisition / Offer / Product Observation / UX Audit / Brand Audit / Reputation / App Presence record**: Domain-specific, human-friendly views of observations for a particular analytical area, each retaining its own source, confidence and (where subjective) rationale.
- **Derived Metric**: A calculated result over one or more approved observations, retaining its formula, formula version, input observation references, assumptions and resulting confidence/comparability.
- **Research Task**: A unit of outstanding work (discover a source, ingest a document, perform an audit, resolve a conflict, etc.) with priority, status and attempt history.
- **Change Log Entry**: An append-only record of a material change to any other record, for audit purposes.
- **Data Quality Issue**: A detected problem with a record or field, with severity, description, suggested fix and resolution status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An analyst can select any recorded fact in the system and, within a single lookup, identify what is known, what is estimated, how reliable it is, exactly where it came from, whether it is genuinely comparable to other brands' figures, and whether anything about it remains unknown.
- **SC-002**: At least 15 pilot brands and their operators are fully registered with complete master data, representing a documented range of scale, proposition and sentiment.
- **SC-003**: Every fact presented anywhere in the system can be traced to a specific, retrievable source within one navigation step, with zero facts presented without provenance.
- **SC-004**: At least three distinct document formats (web pages, PDFs, and structured spreadsheet exports) are processed into reviewable facts without manual re-typing.
- **SC-005**: Re-running data collection against an unchanged source produces zero duplicate facts, on every run.
- **SC-006**: At least ten of the pilot brands have a current promotional-offer capture, and at least ten have a traffic or search-interest observation.
- **SC-007**: At least five of the pilot brands have a completed UX audit and brand audit, each with 100% of scores accompanied by a written rationale.
- **SC-008**: The system never presents an operator/group-level figure as if it were specific to one brand — 100% of such figures are visibly labelled by their true reporting level.
- **SC-009**: Every calculated (derived) figure in the system can be expanded to show the exact inputs and method used to produce it.
- **SC-010**: 100% of invalid or suspect records (e.g. missing source, out-of-range values, unsupported currency, missing rationale) are visible in a single review queue rather than silently entering the trusted dataset.
- **SC-011**: A complete, current export of the dataset can be produced on demand in a portable format, with no data loss relative to the primary interface.
- **SC-012**: No credentials or secrets are ever visible within the primary user-facing interface or stored alongside the data records.
- **SC-013**: An analyst reviewing the comparative summary can identify, for every pilot brand, its current data-completeness level and its top remaining research gaps without consulting any other document.

## Assumptions

- Google Sheets is the mandated primary storage and user interface for this initial implementation (an explicit, stated requirement rather than an incidental implementation choice), chosen for low operational overhead, human inspectability and ease of schema change; migration to a relational database (e.g. PostgreSQL) is an explicitly planned future phase and is out of scope for this specification.
- The initial market focus is Great Britain-facing online casino brands; other jurisdictions' regulators/licences are added only where a pilot brand operates materially outside Great Britain.
- The MVP does not include a production web application, a real-time monitoring system, or an automated scheduler; outstanding work is tracked via a research queue and triggered manually or via scripted/CLI runs.
- Most brand-level commercial data (exact profit, CPA, lifetime value) is not publicly disclosed; the system is designed to make ranges, assumptions and uncertainty explicit rather than to reconstruct undisclosed figures.
- Subjective brand and UX scoring requires human judgement using an agreed rubric; the system does not attempt to fully automate or replace that judgement, only to structure, evidence and store it consistently.
- All data collection relies on publicly accessible information obtained lawfully and without bypassing access controls, authentication, or website terms; no player accounts are created and no personal data about individual gamblers is collected.
- Brand and UX analysis produced by this system informs strategy but does not constitute legal advice regarding gambling advertising or licensing compliance.
- The pilot scope is 15–20 brands, selected by stratified sampling for variety of proposition, scale, operator ownership and sentiment, with the exact list and sampling rationale documented directly in the brand records.
