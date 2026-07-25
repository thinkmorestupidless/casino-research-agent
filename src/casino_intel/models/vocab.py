"""Controlled-vocabulary enums (spec FR-009, source doc §8).

These are the code-level mirror of `config/vocabularies.yaml`. At runtime the
`Config` sheet is the authority (research.md decision #11); these enums are
the fallback/default set used before a workbook exists and for static typing.
"""

from __future__ import annotations

from enum import StrEnum


class EvidenceType(StrEnum):
    REPORTED_PRIMARY = "reported_primary"
    REPORTED_SECONDARY = "reported_secondary"
    DERIVED = "derived"
    THIRD_PARTY_ESTIMATE = "third_party_estimate"
    DIRECT_OBSERVATION = "direct_observation"
    SUBJECTIVE_AUDIT = "subjective_audit"
    INFERRED_RANGE = "inferred_range"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    MACHINE_CHECKED = "machine_checked"
    HUMAN_REVIEWED = "human_reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


#: Legal predecessor -> allowed successor states (data-model.md "review_status" transitions).
REVIEW_STATUS_TRANSITIONS: dict[ReviewStatus, set[ReviewStatus]] = {
    ReviewStatus.UNREVIEWED: {ReviewStatus.MACHINE_CHECKED, ReviewStatus.REJECTED},
    ReviewStatus.MACHINE_CHECKED: {ReviewStatus.HUMAN_REVIEWED, ReviewStatus.REJECTED},
    ReviewStatus.HUMAN_REVIEWED: {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
    ReviewStatus.APPROVED: set(),
    ReviewStatus.REJECTED: set(),
}


class RecordStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


#: data-model.md "status" transitions.
RECORD_STATUS_TRANSITIONS: dict[RecordStatus, set[RecordStatus]] = {
    RecordStatus.ACTIVE: {RecordStatus.SUPERSEDED, RecordStatus.REJECTED},
    RecordStatus.NEEDS_REVIEW: {RecordStatus.ACTIVE, RecordStatus.REJECTED},
    RecordStatus.SUPERSEDED: set(),
    RecordStatus.REJECTED: set(),
}


class ComparabilityStatus(StrEnum):
    COMPARABLE = "comparable"
    PARTIALLY_COMPARABLE = "partially_comparable"
    NOT_COMPARABLE = "not_comparable"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    REGULATOR_STATISTICS = "regulator_statistics"
    REGULATOR_LICENCE_REGISTER = "regulator_licence_register"
    STATUTORY_COMPANY_FILING = "statutory_company_filing"
    ANNUAL_REPORT = "annual_report"
    INTERIM_REPORT = "interim_report"
    INVESTOR_PRESENTATION = "investor_presentation"
    EARNINGS_CALL_TRANSCRIPT = "earnings_call_transcript"
    CORPORATE_PRESS_RELEASE = "corporate_press_release"
    OPERATOR_WEBSITE = "operator_website"
    BRAND_WEBSITE = "brand_website"
    PROMOTION_TERMS = "promotion_terms"
    AFFILIATE_PROGRAMME = "affiliate_programme"
    AFFILIATE_LISTING = "affiliate_listing"
    ADVERTISING_RULING = "advertising_ruling"
    APP_STORE = "app_store"
    REVIEW_PLATFORM = "review_platform"
    TRAFFIC_INTELLIGENCE = "traffic_intelligence"
    SEO_INTELLIGENCE = "seo_intelligence"
    SEARCH_TRENDS = "search_trends"
    NEWS_ARTICLE = "news_article"
    SOCIAL_MEDIA_PROFILE = "social_media_profile"
    MANUAL_SCREEN_CAPTURE = "manual_screen_capture"
    OTHER = "other"


class SourceStatus(StrEnum):
    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class DocumentTextExtractionStatus(StrEnum):
    NOT_STARTED = "not_started"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class BrandStatus(StrEnum):
    ACTIVE = "active"
    DORMANT = "dormant"
    CLOSED = "closed"
    ACQUIRED = "acquired"
    REBRANDED = "rebranded"


class BrandType(StrEnum):
    CASINO_ONLY = "casino_only"
    SPORTSBOOK_LED = "sportsbook_led"
    BINGO_LED = "bingo_led"
    CRYPTO = "crypto"
    SWEEPSTAKES = "sweepstakes"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class OwnershipType(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    PRIVATE_EQUITY = "private_equity"
    STATE = "state"
    UNKNOWN = "unknown"


class LicenceType(StrEnum):
    REMOTE_CASINO = "remote_casino"
    BETTING = "betting"
    BINGO = "bingo"
    SOFTWARE = "software"
    OTHER = "other"


class LicenceStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    SURRENDERED = "surrendered"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class SubjectType(StrEnum):
    BRAND = "brand"
    OPERATOR = "operator"
    MARKET = "market"
    LICENCE = "licence"
    OFFER = "offer"
    APP = "app"


class TaskType(StrEnum):
    DISCOVER_SOURCE = "discover_source"
    DOWNLOAD_DOCUMENT = "download_document"
    PARSE_DOCUMENT = "parse_document"
    EXTRACT_METRIC = "extract_metric"
    VERIFY_LICENCE = "verify_licence"
    CAPTURE_TRAFFIC = "capture_traffic"
    CAPTURE_SEARCH_TRENDS = "capture_search_trends"
    CAPTURE_OFFER = "capture_offer"
    PERFORM_UX_AUDIT = "perform_ux_audit"
    PERFORM_BRAND_AUDIT = "perform_brand_audit"
    REVIEW_CONFLICT = "review_conflict"
    HUMAN_VALIDATION = "human_validation"


class TaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class DataQualityIssueType(StrEnum):
    MISSING_SOURCE = "missing_source"
    MISSING_REPORTING_PERIOD = "missing_reporting_period"
    INVALID_ID = "invalid_id"
    DUPLICATE_ENTITY = "duplicate_entity"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    PERCENTAGE_OUTSIDE_0_100 = "percentage_outside_0_100"
    NEGATIVE_VALUE_WHERE_PROHIBITED = "negative_value_where_prohibited"
    NORMALISED_VALUE_WITHOUT_RAW_VALUE = "normalised_value_without_raw_value"
    DERIVED_METRIC_WITHOUT_INPUTS = "derived_metric_without_inputs"
    SUBJECTIVE_SCORE_WITHOUT_RATIONALE = "subjective_score_without_rationale"
    STALE_OBSERVATION = "stale_observation"
    CONFLICTING_HIGH_CONFIDENCE_OBSERVATIONS = "conflicting_high_confidence_observations"
    GROUP_FIGURE_INCORRECTLY_LABELLED_AS_BRAND_FIGURE = (
        "group_figure_incorrectly_labelled_as_brand_figure"
    )
    SOURCE_URL_UNAVAILABLE = "source_url_unavailable"
    CONTENT_HASH_CHANGED = "content_hash_changed"
    UNKNOWN_METRIC_DEFINITION = "unknown_metric_definition"
    INVALID_CONTROLLED_VOCABULARY_VALUE = "invalid_controlled_vocabulary_value"


class DataQualitySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataQualityStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


class ChangeLogAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    SUPERSEDE = "supersede"
    REJECT = "reject"
    APPROVE = "approve"
    DELETE_SUPPRESSION = "delete_suppression"
