import pytest

from casino_intel.services.audit_service import AuditService, AuditServiceError
from casino_intel.services.rubric_service import RubricService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation.data_quality import DataQualityWriter

RUBRICS_PATH = "config/audit-rubrics.yaml"


@pytest.fixture
def data_quality_writer(sheets_client, fake_service):
    fake_service.add_sheet("Data Quality", SHEET_HEADERS["Data Quality"])
    return DataQualityWriter(sheets_client)


@pytest.fixture(autouse=True)
def _audit_sheets(fake_service):
    fake_service.add_sheet("UX Audits", SHEET_HEADERS["UX Audits"])
    fake_service.add_sheet("Brand Audits", SHEET_HEADERS["Brand Audits"])


@pytest.fixture
def audit_service(sheets_writer, data_quality_writer):
    return AuditService(sheets_writer, data_quality_writer, RubricService(RUBRICS_PATH))


def _ux_fields(**overrides):
    defaults = dict(
        brand_id="brand_1",
        auditor="tester",
        audit_date="2026-07-24",
        geography="GB",
        game_discovery_score=4,
        game_discovery_score_rationale="Found via search in two clicks.",
    )
    defaults.update(overrides)
    return defaults


def _brand_fields(**overrides):
    defaults = dict(
        brand_id="brand_1",
        auditor="tester",
        audit_date="2026-07-24",
        brand_rationale="Premium, understated identity with strong trust signals.",
        premium_score=4,
        premium_score_rationale="Muted palette, minimal promotional noise.",
    )
    defaults.update(overrides)
    return defaults


def test_record_ux_audit_appends_row_and_stamps_rubric_version(audit_service, fake_service):
    result = audit_service.record_ux_audit(_ux_fields(), actor="tester")
    assert result.written
    assert len(fake_service.sheets["UX Audits"]) == 2
    header = SHEET_HEADERS["UX Audits"]
    row = dict(zip(header, fake_service.sheets["UX Audits"][1], strict=False))
    assert row["rubric_version"] == "2026.07.1"
    assert row["evidence_type"] == "subjective_audit"


def test_record_ux_audit_missing_rationale_is_rejected(audit_service, fake_service):
    with pytest.raises(AuditServiceError):
        audit_service.record_ux_audit(_ux_fields(game_discovery_score_rationale=""), actor="tester")
    assert len(fake_service.sheets["UX Audits"]) == 1  # header only — nothing written
    assert len(fake_service.sheets["Data Quality"]) == 2  # the failure is still logged
    assert fake_service.sheets["Data Quality"][1][3] == "subjective_score_without_rationale"


def test_record_ux_audit_never_records_a_completed_restricted_action(audit_service, fake_service):
    with pytest.raises(AuditServiceError):
        audit_service.record_ux_audit(
            _ux_fields(kyc_requested_at="identity_documents_submitted"), actor="tester"
        )
    assert len(fake_service.sheets["UX Audits"]) == 1


def test_record_brand_audit_appends_row(audit_service, fake_service):
    result = audit_service.record_brand_audit(_brand_fields(), actor="tester")
    assert result.written
    assert len(fake_service.sheets["Brand Audits"]) == 2


def test_record_brand_audit_missing_rationale_is_rejected(audit_service, fake_service):
    with pytest.raises(AuditServiceError):
        audit_service.record_brand_audit(_brand_fields(premium_score_rationale=""), actor="tester")
    assert len(fake_service.sheets["Brand Audits"]) == 1


def test_record_brand_audit_requires_overall_brand_rationale(audit_service, fake_service):
    with pytest.raises(AuditServiceError):
        audit_service.record_brand_audit(_brand_fields(brand_rationale=""), actor="tester")
    assert len(fake_service.sheets["Brand Audits"]) == 1
