from casino_intel.validation.fingerprint import fingerprint


def _obs(**overrides):
    base = dict(
        subject_id="brand_01",
        metric_id="estimated_monthly_visits",
        period_start="2026-06-01",
        period_end="2026-06-30",
        as_of_date=None,
        geography="GB",
        segment="casino",
        source_id="source_01",
        raw_value="1,200,000",
    )
    base.update(overrides)
    return base


def test_identical_observations_produce_identical_fingerprints():
    assert fingerprint(_obs()) == fingerprint(_obs())


def test_different_raw_value_changes_fingerprint():
    assert fingerprint(_obs()) != fingerprint(_obs(raw_value="1,300,000"))


def test_different_source_changes_fingerprint():
    assert fingerprint(_obs()) != fingerprint(_obs(source_id="source_02"))


def test_missing_optional_fields_are_treated_as_empty_not_crashing():
    minimal = {"subject_id": "brand_01", "metric_id": "m", "source_id": "s", "raw_value": "1"}
    assert fingerprint(minimal) == fingerprint(minimal)


def test_extra_unrelated_keys_do_not_affect_fingerprint():
    obs = _obs()
    obs_with_extra = {**obs, "verbatim_excerpt": "irrelevant to identity"}
    assert fingerprint(obs) == fingerprint(obs_with_extra)
