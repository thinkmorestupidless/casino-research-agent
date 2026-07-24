#!/usr/bin/env python3
"""Load `scripts/pilot_brands_seed.yaml` into the Operators/Brands sheets
(User Story 1, T038). Resolves each brand's `operator_alias` to the
generated `operator_id` before registering it.

Usage:
    python scripts/seed_pilot_brands.py [--dry-run]
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from casino_intel.cli.context import AppContext
from casino_intel.services.registry_service import RegistryService

SEED_PATH = Path(__file__).parent / "pilot_brands_seed.yaml"
ACTOR = "seed_pilot_brands"


def _drop_nulls(fields: dict) -> dict:
    """Let Pydantic field defaults apply instead of passing an explicit
    None for a field typed as `str = ""` (YAML `null` -> Python None)."""
    return {k: v for k, v in fields.items() if v is not None}


def load_seed(path: Path = SEED_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(context: AppContext, seed: dict) -> dict[str, list[str]]:
    service = RegistryService(context.writer)

    operator_ids: dict[str, str] = {}
    operator_results = []
    for op in seed["operators"]:
        fields = _drop_nulls({k: v for k, v in op.items() if k != "alias"})
        result = service.register_operator(
            fields, actor=ACTOR, ingestion_run_id=context.ingestion_run_id
        )
        operator_ids[op["alias"]] = result.record_id
        operator_results.append(result.record_id)

    brand_results = []
    for brand in seed["brands"]:
        operator_alias = brand["operator_alias"]
        fields = _drop_nulls(
            {k: v for k, v in brand.items() if k not in ("alias", "operator_alias")}
        )
        fields["operator_id"] = operator_ids[operator_alias]
        result = service.register_brand(
            fields, actor=ACTOR, ingestion_run_id=context.ingestion_run_id
        )
        brand_results.append(result.record_id)

    return {"operators": operator_results, "brands": brand_results}


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    context = AppContext(dry_run=dry_run)
    seed = load_seed()
    results = run(context, seed)
    print(f"Registered {len(results['operators'])} operators, {len(results['brands'])} brands.")


if __name__ == "__main__":
    main()
