import pytest

from circuitguard.config import ServerConfig
from circuitguard.errors import ServerNotFound
from circuitguard.services.crafty import CraftyServer
from circuitguard.services.registry import ServerRegistry, build_auto_configs


def make_config(label: str) -> ServerConfig:
    return ServerConfig(label=label, crafty_id=f"id-{label}")


def test_get_is_case_insensitive() -> None:
    registry = ServerRegistry([make_config("Survival")])
    assert registry.get("survival").label == "Survival"


def test_get_unknown_raises() -> None:
    registry = ServerRegistry([make_config("Survival")])
    with pytest.raises(ServerNotFound):
        registry.get("Creative")


def test_update_replaces_servers() -> None:
    registry = ServerRegistry([make_config("Old")])
    registry.update([make_config("New")])
    assert registry.get("new").label == "New"
    with pytest.raises(ServerNotFound):
        registry.get("Old")


def test_auto_configs_basic() -> None:
    configs = build_auto_configs(
        [CraftyServer(server_id="a1b2c3d4-0000", name="Survival")], mod_role_ids=[42]
    )
    assert len(configs) == 1
    assert configs[0].label == "Survival"
    assert configs[0].crafty_id == "a1b2c3d4-0000"
    assert configs[0].mod_role_ids == [42]
    assert configs[0].rcon_host is None


def test_auto_configs_deduplicates_labels() -> None:
    configs = build_auto_configs(
        [
            CraftyServer(server_id="aaaa1111-0000", name="Survival"),
            CraftyServer(server_id="bbbb2222-0000", name="survival"),
        ],
        mod_role_ids=[],
    )
    assert configs[0].label == "Survival"
    assert configs[1].label == "survival (bbbb2222)"


def test_auto_configs_blank_name_falls_back_to_id() -> None:
    configs = build_auto_configs(
        [CraftyServer(server_id="a1b2c3d4-0000", name="  ")], mod_role_ids=[]
    )
    assert configs[0].label == "a1b2c3d4"


def test_auto_configs_truncates_long_names() -> None:
    configs = build_auto_configs(
        [CraftyServer(server_id="a1b2c3d4-0000", name="x" * 200)], mod_role_ids=[]
    )
    assert len(configs[0].label) <= 100
