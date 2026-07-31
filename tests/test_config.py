import json

import pytest
from pydantic import ValidationError

from circuitguard.config import Settings

BASE_ENV = {
    "DISCORD_TOKEN": "token",
    "CRAFTY_URL": "https://crafty.example.com",
    "CRAFTY_API_TOKEN": "crafty-token",
}


def make_servers(*labels: str, rcon: bool = True) -> str:
    servers: list[dict[str, str]] = []
    for label in labels:
        server = {"label": label, "crafty_id": f"id-{label}"}
        if rcon:
            server |= {"rcon_host": f"host-{label}", "rcon_password": "secret"}
        servers.append(server)
    return json.dumps(servers)


@pytest.fixture
def build(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    def _build(env: dict[str, str]) -> Settings:
        for key, value in {**BASE_ENV, **env}.items():
            monkeypatch.setenv(key, value)
        return Settings(_env_file=None)  # type: ignore[call-arg]

    return _build


def test_parses_server_list(build) -> None:  # type: ignore[no-untyped-def]
    settings = build({"MC_SERVERS": make_servers("Survival", "Creative")})
    assert [s.label for s in settings.servers] == ["Survival", "Creative"]
    assert settings.servers[0].rcon_port == 25575
    assert settings.servers[0].rcon_password.get_secret_value() == "secret"


def test_admin_role_ids_comma_split(build) -> None:  # type: ignore[no-untyped-def]
    settings = build({"MC_SERVERS": make_servers("Survival"), "ADMIN_ROLE_IDS": "123, 456 ,789"})
    assert settings.admin_role_ids == [123, 456, 789]


def test_admin_role_ids_default_empty(build) -> None:  # type: ignore[no-untyped-def]
    settings = build({"MC_SERVERS": make_servers("Survival")})
    assert settings.admin_role_ids == []


def test_duplicate_labels_rejected(build) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError, match="duplicate labels"):
        build({"MC_SERVERS": make_servers("Survival", "survival")})


def test_empty_server_list_requires_crafty_backend(build) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError, match="requires CONSOLE_BACKEND=crafty"):
        build({"MC_SERVERS": "[]"})


def test_empty_server_list_enables_auto_detection(build) -> None:  # type: ignore[no-untyped-def]
    settings = build({"MC_SERVERS": "[]", "CONSOLE_BACKEND": "crafty"})
    assert settings.servers == []


def test_mod_role_ids_comma_split(build) -> None:  # type: ignore[no-untyped-def]
    settings = build(
        {
            "MC_SERVERS": "[]",
            "CONSOLE_BACKEND": "crafty",
            "MOD_ROLE_IDS": "11, 22",
        }
    )
    assert settings.mod_role_ids == [11, 22]


def test_invalid_json_rejected(build) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises((ValidationError, ValueError)):
        build({"MC_SERVERS": "not-json"})


def test_missing_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in BASE_ENV.items():
        if key != "DISCORD_TOKEN":
            monkeypatch.setenv(key, value)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.setenv("MC_SERVERS", make_servers("Survival"))
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_backend_defaults_to_rcon(build) -> None:  # type: ignore[no-untyped-def]
    assert build({"MC_SERVERS": make_servers("Survival")}).console_backend == "rcon"


def test_rcon_backend_requires_rcon_fields(build) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError, match="requires rcon_host and rcon_password"):
        build({"MC_SERVERS": make_servers("Survival", rcon=False)})


def test_crafty_backend_needs_no_rcon_fields(build) -> None:  # type: ignore[no-untyped-def]
    settings = build(
        {"MC_SERVERS": make_servers("Survival", rcon=False), "CONSOLE_BACKEND": "crafty"}
    )
    assert settings.console_backend == "crafty"
    assert settings.servers[0].rcon_host is None


def test_optional_guild_id(build) -> None:  # type: ignore[no-untyped-def]
    assert build({"MC_SERVERS": make_servers("Survival")}).discord_guild_id is None
    settings = build({"MC_SERVERS": make_servers("Survival"), "DISCORD_GUILD_ID": "42"})
    assert settings.discord_guild_id == 42
