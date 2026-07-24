"""Config/vocab loader (research.md decision #11, spec FR-009).

Controlled-vocabulary *value lists* (evidence types, statuses, source types,
etc.) are seeded into the `Config` sheet from `config/vocabularies.yaml` on
first run; thereafter the `Config` sheet is the runtime authority — humans
can inspect/amend it directly in the workbook (source doc §8).

The metric-definition registry and audit rubrics (`config/metrics.yaml`,
`config/audit-rubrics.yaml`) are richer structures than a flat value list
belongs in, so they are loaded directly from their YAML files at runtime
rather than flattened into Config sheet rows — only the plain `metric_id`
list is also seeded into Config for dropdown/inspection purposes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from casino_intel.sheets.client import SheetsClient

SHEET_NAME = "Config"
COLUMNS = ["list_name", "value", "description"]


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class MetricRegistry:
    """In-memory metric-definition registry loaded from `config/metrics.yaml`."""

    def __init__(self, metrics_path: str | Path) -> None:
        data = load_yaml(metrics_path)
        self.schema_version: str = data.get("schema_version", "")
        self.metrics: dict[str, dict[str, Any]] = {
            m["metric_id"]: m for m in data.get("metrics", [])
        }

    def __contains__(self, metric_id: str) -> bool:
        return metric_id in self.metrics

    def get(self, metric_id: str) -> dict[str, Any] | None:
        return self.metrics.get(metric_id)

    def allowed_units(self, metric_id: str) -> list[str]:
        metric = self.metrics.get(metric_id, {})
        return metric.get("allowed_units", [])


class ConfigLoader:
    """Seeds and reads the `Config` sheet's controlled-vocabulary rows."""

    def __init__(self, client: SheetsClient, dry_run: bool = False) -> None:
        self.client = client
        self.dry_run = dry_run

    def seed_vocabularies(self, vocabularies_path: str | Path) -> int:
        """Seed `Config` from `vocabularies.yaml`, skipping any (list_name,
        value) pair already present — safe to re-run (idempotent)."""
        vocab = load_yaml(vocabularies_path)
        existing = self._existing_pairs()

        rows_to_add: list[list[str]] = []
        for list_name, entries in vocab.items():
            if list_name == "schema_version":
                continue
            for value, description in self._flatten(entries):
                if (list_name, value) not in existing:
                    rows_to_add.append([list_name, value, description])
                    existing.add((list_name, value))

        if rows_to_add and not self.dry_run:
            self.client.append_rows(SHEET_NAME, rows_to_add)
        return len(rows_to_add)

    def seed_metric_ids(self, metrics_path: str | Path) -> int:
        """Seed the flat list of known metric_ids into Config (for dropdown
        use); the full metric definitions remain authoritative in
        `config/metrics.yaml` via `MetricRegistry`."""
        registry = MetricRegistry(metrics_path)
        existing = self._existing_pairs()
        rows_to_add = [
            ["metric_definitions", metric_id, definition.get("display_name", "")]
            for metric_id, definition in registry.metrics.items()
            if ("metric_definitions", metric_id) not in existing
        ]
        if rows_to_add and not self.dry_run:
            self.client.append_rows(SHEET_NAME, rows_to_add)
        return len(rows_to_add)

    def get_vocabulary(self, list_name: str) -> list[str]:
        """Read the current allowed values for `list_name` from the live
        Config sheet (the runtime authority)."""
        values = self.client.batch_get_values([f"{SHEET_NAME}!A2:B"]).get(f"{SHEET_NAME}!A2:B", [])
        return [row[1] for row in values if row and row[0] == list_name and len(row) > 1]

    def _existing_pairs(self) -> set[tuple[str, str]]:
        values = self.client.batch_get_values([f"{SHEET_NAME}!A2:B"]).get(f"{SHEET_NAME}!A2:B", [])
        return {(row[0], row[1]) for row in values if len(row) > 1}

    @staticmethod
    def _flatten(entries: Any) -> list[tuple[str, str]]:
        """Turn a vocab entry (list, dict, or scalar) into (value, description) pairs."""
        if isinstance(entries, list):
            return [(str(item), "") for item in entries]
        if isinstance(entries, dict):
            return [(json.dumps(entries), "")]
        return [(str(entries), "")]
