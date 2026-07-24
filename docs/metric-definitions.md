# Metric definitions

This is a human-readable mirror of `config/metrics.yaml`, the authoritative metric-definition registry. Regenerate this file whenever `config/metrics.yaml` changes materially (it is not auto-generated in the MVP).

Every `Observation.metric_id` and `Observation.definition_id` must resolve to an entry in `config/metrics.yaml`; an unresolved metric is a `unknown_metric_definition` Data Quality issue (see `src/casino_intel/validation/data_quality.py`), never a silently-accepted free-text metric.

See `config/metrics.yaml` for the full, current list of market, operator-financial, customer, traffic/awareness, app, reputation, UX and derived metrics, each with its `subject_types`, `allowed_units`, `comparability_group`, and known `caveats`.

## Key caveats that apply across the registry (source doc §24)

- Website visits are not active players.
- Registered accounts are not depositing customers.
- "Active customer" definitions vary by operator.
- Group revenue cannot generally be assigned precisely to one brand.
- Group marketing expenditure is not brand CPA.
- Affiliate offers are not necessarily the operator's realised average acquisition cost.
- Google Trends is a relative index, not absolute volume.
- Review ratings are affected by selection and platform bias.
- App downloads do not equal active users.
- Revenue is not GGR, NGR, GGY or profit unless the source defines it that way.
- Quarterly active counts should not be naively summed.
- A range with explicit assumptions is preferable to a fabricated point estimate.
- Correlation between design traits and performance does not prove causation.
