from casino_intel.models.ids import PREFIXES, entity_type_of, is_valid_id, new_id


def test_new_id_has_correct_prefix():
    brand_id = new_id("brand")
    assert brand_id.startswith("brand_")


def test_new_id_is_unique():
    ids = {new_id("observation") for _ in range(1000)}
    assert len(ids) == 1000


def test_is_valid_id_accepts_generated_ids():
    for entity_type in PREFIXES:
        assert is_valid_id(new_id(entity_type), entity_type)


def test_is_valid_id_rejects_row_number_style_keys():
    assert not is_valid_id("42")
    assert not is_valid_id("Brand 7")
    assert not is_valid_id("")


def test_entity_type_of_round_trips():
    source_id = new_id("source")
    assert entity_type_of(source_id) == "source"
