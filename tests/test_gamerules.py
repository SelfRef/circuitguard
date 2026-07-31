from circuitguard.commands.servers import GAMERULES, gamerule_value_options, matching_gamerules


def test_matching_is_case_insensitive_substring() -> None:
    assert "keep_inventory" in matching_gamerules("KEEP")
    assert "players_sleeping_percentage" in matching_gamerules("sleeping")


def test_matching_empty_returns_capped_list() -> None:
    results = matching_gamerules("")
    assert len(results) == 25  # Discord's autocomplete limit


def test_value_options_for_bool_rule() -> None:
    assert gamerule_value_options("keep_inventory", "") == ["true", "false"]
    assert gamerule_value_options("keep_inventory", "t") == ["true"]
    assert gamerule_value_options("keep_inventory", "FAL") == ["false"]


def test_value_options_for_int_and_unknown_rules() -> None:
    assert gamerule_value_options("random_tick_speed", "") == []
    assert gamerule_value_options("jade:max_position_deviation", "") == []


def test_gamerule_types_are_valid() -> None:
    assert set(GAMERULES.values()) <= {"bool", "int"}
