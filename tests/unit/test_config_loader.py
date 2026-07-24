from pathlib import Path

from casino_intel.sheets.config_loader import ConfigLoader, MetricRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
VOCAB_PATH = REPO_ROOT / "config" / "vocabularies.yaml"
METRICS_PATH = REPO_ROOT / "config" / "metrics.yaml"


def test_seed_vocabularies_writes_rows(sheets_client, fake_service):
    fake_service.add_sheet("Config", ["list_name", "value", "description"])
    loader = ConfigLoader(sheets_client)

    added = loader.seed_vocabularies(VOCAB_PATH)

    assert added > 0
    assert len(fake_service.sheets["Config"]) == added + 1  # + header
    evidence_types = loader.get_vocabulary("evidence_types")
    assert "reported_primary" in evidence_types
    assert "unknown" in evidence_types


def test_seed_vocabularies_is_idempotent(sheets_client, fake_service):
    fake_service.add_sheet("Config", ["list_name", "value", "description"])
    loader = ConfigLoader(sheets_client)

    first = loader.seed_vocabularies(VOCAB_PATH)
    second = loader.seed_vocabularies(VOCAB_PATH)

    assert first > 0
    assert second == 0  # nothing new to add second time
    assert len(fake_service.sheets["Config"]) == first + 1


def test_seed_metric_ids(sheets_client, fake_service):
    fake_service.add_sheet("Config", ["list_name", "value", "description"])
    loader = ConfigLoader(sheets_client)

    added = loader.seed_metric_ids(METRICS_PATH)

    assert added > 0
    metric_ids = loader.get_vocabulary("metric_definitions")
    assert "estimated_monthly_visits" in metric_ids
    assert "revenue_per_active_customer" in metric_ids


def test_metric_registry_loads_all_metrics_and_resolves_units():
    registry = MetricRegistry(METRICS_PATH)
    assert "estimated_monthly_visits" in registry
    assert "not_a_real_metric" not in registry
    assert "visits" in registry.allowed_units("estimated_monthly_visits")
