"""`casino-intel record-ux-audit` (contracts/cli-commands.md, T079).

Supports two flows, combinable:

- **Manual/hand-entered fallback** (always required): `--scores-file` points
  at a JSON file of `{"<dimension>_score": {"score": int, "rationale": str},
  ...}` — one entry per `config/audit-rubrics.yaml` `ux_audit_dimensions`
  key. Rubric scoring is always a human judgement (FR-049); it is never
  derived from the capture step below.
- **Playwright-assisted capture** (opt-in via `--capture`): automatically
  visits and screenshots the permitted pages (homepage, lobby, promotions,
  registration up to the stop point, footer/licence, responsible gambling),
  archiving each via Drive and populating `screenshot_set_path`. The journey
  never proceeds past the permitted stop point (FR-033/FR-046).
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


def record_ux_audit(
    ctx: typer.Context,
    brand_id: str = typer.Option(..., "--brand-id"),
    auditor: str = typer.Option(..., "--auditor"),
    scores_file: Path = typer.Option(
        ..., "--scores-file", help="JSON file of {dimension_score: {score, rationale}}."
    ),
    audit_date: str = typer.Option(None, "--audit-date", help="ISO date; defaults to today."),
    geography: str = typer.Option("GB", "--geography"),
    device_type: str = typer.Option("desktop", "--device-type"),
    viewport: str = typer.Option("", "--viewport"),
    homepage_url: str = typer.Option("", "--homepage-url"),
    logged_in: bool = typer.Option(False, "--logged-in/--logged-out"),
    cookie_state: str = typer.Option("accepted", "--cookie-state"),
    new_or_returning: str = typer.Option("new", "--new-or-returning"),
    registration_steps: int = typer.Option(0, "--registration-steps"),
    kyc_requested_at: str = typer.Option(
        "", "--kyc-requested-at", help="Stage the KYC prompt appeared at — never a completion."
    ),
    deposit_steps: int = typer.Option(
        0, "--deposit-steps", help="Deposit-flow steps reached before the journey stopped."
    ),
    capture: bool = typer.Option(
        False, "--capture", help="Run the Playwright-assisted screenshot capture flow."
    ),
) -> None:
    """Record one UX audit row; rejects the save if a populated score is missing its rationale."""
    context: AppContext = ctx.obj
    resolved_audit_date = audit_date or date.today().isoformat()

    scores_payload = json.loads(scores_file.read_text(encoding="utf-8"))
    fields: dict[str, object] = {
        "brand_id": brand_id,
        "auditor": auditor,
        "audit_date": resolved_audit_date,
        "geography": geography,
        "device_type": device_type,
        "viewport": viewport,
        "homepage_url": homepage_url,
        "logged_in_state": logged_in,
        "cookie_state": cookie_state,
        "new_or_returning_visitor": new_or_returning,
        "registration_steps": registration_steps,
        "kyc_requested_at": kyc_requested_at,
        "deposit_steps": deposit_steps,
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
        result = audit_service.record_ux_audit(
            fields, actor=context.actor, ingestion_run_id=context.ingestion_run_id
        )
    except AuditServiceError as exc:
        typer.echo(f"UX audit rejected: {exc}")
        raise typer.Exit(code=1) from None

    typer.echo(f"Recorded UX audit: {result.record_id}")
