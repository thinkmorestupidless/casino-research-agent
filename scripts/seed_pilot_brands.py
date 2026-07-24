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
    """Seed all operators, then all brands, each as a single batched append.

    Operators are written first (two API calls), their generated ids mapped
    back to each seed alias, then brands are written with `operator_id`
    resolved (two more calls) — four Sheets writes total for the whole pilot,
    well under the per-minute write quota that row-by-row writes exceed.
    """
    service = RegistryService(context.writer)

    operators = seed["operators"]
    operator_fields = [
        _drop_nulls({k: v for k, v in op.items() if k != "alias"}) for op in operators
    ]
    operator_results = service.register_operators(
        operator_fields, actor=ACTOR, ingestion_run_id=context.ingestion_run_id
    )
    operator_ids = {
        op["alias"]: r.record_id
        for op, r in zip(operators, operator_results, strict=True)
    }

    brand_fields = []
    for brand in seed["brands"]:
        fields = _drop_nulls(
            {k: v for k, v in brand.items() if k not in ("alias", "operator_alias")}
        )
        fields["operator_id"] = operator_ids[brand["operator_alias"]]
        brand_fields.append(fields)
    brand_results = service.register_brands(
        brand_fields, actor=ACTOR, ingestion_run_id=context.ingestion_run_id
    )

    return {
        "operators": [r.record_id for r in operator_results],
        "brands": [r.record_id for r in brand_results],
    }


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    context = AppContext(dry_run=dry_run)
    seed = load_seed()
    results = run(context, seed)
    print(f"Registered {len(results['operators'])} operators, {len(results['brands'])} brands.")


if __name__ == "__main__":
    main()
