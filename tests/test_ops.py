from circuitguard.commands.ops import OpEntry, parse_ops_json

OPS_JSON = """[
  {"uuid": "aaa-111", "name": "Steve", "level": 4, "bypassesPlayerLimit": false},
  {"uuid": "bbb-222", "name": "Alex", "level": 2, "bypassesPlayerLimit": true}
]"""


def test_parse_ops_json() -> None:
    assert parse_ops_json(OPS_JSON) == [OpEntry("Steve", 4), OpEntry("Alex", 2)]


def test_parse_empty_file_and_list() -> None:
    assert parse_ops_json("") == []
    assert parse_ops_json("[]") == []


def test_parse_malformed_content() -> None:
    assert parse_ops_json("not json {") == []
    assert parse_ops_json('{"name": "not-a-list"}') == []
    assert parse_ops_json('[{"uuid": "no-name"}, 42]') == []


def test_parse_missing_level_defaults_to_zero() -> None:
    assert parse_ops_json('[{"name": "Steve"}]') == [OpEntry("Steve", 0)]
