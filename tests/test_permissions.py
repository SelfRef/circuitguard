import json

import pytest

from circuitguard.config import Settings
from circuitguard.errors import ServerNotFound
from circuitguard.permissions import is_admin, is_mod_for
from circuitguard.services.registry import ServerRegistry

ADMIN_ROLE = 100
SURVIVAL_MOD = 200
CREATIVE_MOD = 300


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    servers = [
        {
            "label": "Survival",
            "crafty_id": "id-1",
            "rcon_host": "h1",
            "rcon_password": "x",
            "mod_role_ids": [SURVIVAL_MOD],
        },
        {
            "label": "Creative",
            "crafty_id": "id-2",
            "rcon_host": "h2",
            "rcon_password": "x",
            "mod_role_ids": [CREATIVE_MOD],
        },
    ]
    env = {
        "DISCORD_TOKEN": "t",
        "CRAFTY_URL": "https://c.example.com",
        "CRAFTY_API_TOKEN": "t",
        "ADMIN_ROLE_IDS": str(ADMIN_ROLE),
        "MC_SERVERS": json.dumps(servers),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_admin_everywhere(settings: Settings) -> None:
    roles = {ADMIN_ROLE, 999}
    assert is_admin(roles, settings)
    for server in settings.servers:
        assert is_mod_for(roles, server, settings)


def test_mod_only_on_own_server(settings: Settings) -> None:
    roles = {SURVIVAL_MOD}
    survival, creative = settings.servers
    assert not is_admin(roles, settings)
    assert is_mod_for(roles, survival, settings)
    assert not is_mod_for(roles, creative, settings)


def test_plain_user_denied_everywhere(settings: Settings) -> None:
    roles = {999, 888}
    assert not is_admin(roles, settings)
    for server in settings.servers:
        assert not is_mod_for(roles, server, settings)


def test_no_roles(settings: Settings) -> None:
    assert not is_admin(set(), settings)
    assert not is_mod_for(set(), settings.servers[0], settings)


def test_registry_lookup_case_insensitive(settings: Settings) -> None:
    registry = ServerRegistry(settings.servers)
    assert registry.get("survival").label == "Survival"
    assert registry.get("SURVIVAL").label == "Survival"
    with pytest.raises(ServerNotFound):
        registry.get("Hardcore")
