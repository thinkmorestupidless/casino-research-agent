"""`casino-intel record-brand-audit` (contracts/cli-commands.md, T079).

Supports two flows, combinable:

- **Manual/hand-entered fallback** (always required): `--scores-file` points
  at a JSON file of `{"<dimension>_score": {"score": int, "rationale": str},
  ...}` — one entry per `config/audit-rubrics.yaml` `brand_audit_dimensions`
  key — plus `--brand-rationale`, always required. Rubric scoring is always
  a human judgement (FR-049).
- **Playwright-assisted capture** (opt-in via `--capture`): automatically
  visits and screenshots the permitted pages, archiving each via Drive and
  populating `screenshot_set_path`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import typer

from casino_intel.cli.context import AppContext
from casino_intel.fetching.audit_capture import capture_permitted_pages
from casino_intel.services.audit_service import AuditService, AuditServiceError
from casino_intel.services.rubric_service import RubricService


def record_brand_audit(
    ctx: typer.Context,
    brand_id: str = typer.Option(..., "--brand-id"),
    auditor: str = typer.Option(..., "--auditor"),
    brand_rationale: str = typer.Option(..., "--brand-rationale"),
    scores_file: Path = typer.Option(
        ..., "--scores-file", help="JSON file of {dimension_score: {score, rationale}}."
    ),
    audit_date: str = typer.Option(None, "--audit-date", help="ISO date; defaults to today."),
    primary_colour: str = typer.Option("", "--primary-colour"),
    background_style: str = typer.Option("", "--background-style"),
    typography_style: str = typer.Option("", "--typography-style"),
    logo_type: str = typer.Option("", "--logo-type"),
    tone_of_voice: str = typer.Option("", "--tone-of-voice"),
    primary_tagline: str = typer.Option("", "--primary-tagline"),
    primary_proposition: str = typer.Option("", "--primary-proposition"),
    target_audience_hypothesis: str = typer.Option("", "--target-audience-hypothesis"),
    homepage_url: str = typer.Option("", "--homepage-url"),
    capture: bool = typer.Option(
        False, "--capture", help="Run the Playwright-assisted screenshot capture flow."
    ),
) -> None:
    """Record one brand audit row; rejects the save if a score is missing its rationale."""
    context: AppContext = ctx.obj
    resolved_audit_date = audit_date or date.today().isoformat()

    scores_payload = json.loads(scores_file.read_text(encoding="utf-8"))
    fields: dict[str, object] = {
        "brand_id": brand_id,
        "auditor": auditor,
        "audit_date": resolved_audit_date,
        "brand_rationale": brand_rationale,
        "primary_colour": primary_colour,
        "background_style": background_style,
        "typography_style": typography_style,
        "logo_type": logo_type,
        "tone_of_voice": tone_of_voice,
        "primary_tagline": primary_tagline,
        "primary_proposition": primary_proposition,
        "target_audience_hypothesis": target_audience_hypothesis,
    }
    for dimension_score, entry in scores_payload.items():
        fields[dimension_score] = entry.get("score")
        fields[f"{dimension_score}_rationale"] = entry.get("rationale", "")

    if capture:
        if not homepage_url:
            typer.echo("--homepage-url is required when --capture is set")
            raise typer.Exit(code=1)
        screenshots = capture_permitted_pages(
            homepage_url,
            context.drive_client,
            brand_id=brand_id,
            audit_date=resolved_audit_date,
        )
        fields["screenshot_set_path"] = ", ".join(s.archive_path for s in screenshots)

    audit_service = AuditService(context.writer, context.data_quality, RubricService())
    try:
        result = audit_service.record_brand_audit(
            fields, actor=context.actor, ingestion_run_id=context.ingestion_run_id
        )
    except AuditServiceError as exc:
        typer.echo(f"Brand audit rejected: {exc}")
        raise typer.Exit(code=1) from None

    typer.echo(f"Recorded brand audit: {result.record_id}")
