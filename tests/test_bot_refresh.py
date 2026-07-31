from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from circuitguard.bot import SERVER_CACHE_TTL, CircuitGuardBot
from circuitguard.config import Settings
from circuitguard.errors import CraftyUnavailable
from circuitguard.services.crafty import CraftyServer


@pytest.fixture
async def bot(tmp_path: Path) -> AsyncIterator[CircuitGuardBot]:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        discord_token="token",
        crafty_url="https://crafty.example.com",
        crafty_api_token="crafty-token",
        console_backend="crafty",
        db_path=tmp_path / "test.db",
    )
    bot = CircuitGuardBot(settings)
    yield bot
    await bot.crafty.close()
    await bot.mojang.close()


class FakeCrafty:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    async def list_servers(self) -> list[CraftyServer]:
        self.calls += 1
        if self.fail:
            raise CraftyUnavailable("down")
        return [CraftyServer(server_id="id-1", name="Survival")]


@pytest.fixture
def fake_crafty(bot: CircuitGuardBot, monkeypatch: pytest.MonkeyPatch) -> FakeCrafty:
    fake = FakeCrafty()
    monkeypatch.setattr(bot.crafty, "list_servers", fake.list_servers)
    return fake


async def test_refreshes_once_until_stale(bot: CircuitGuardBot, fake_crafty: FakeCrafty) -> None:
    assert bot.auto_detect_servers

    server = await bot.get_server("survival")
    assert server.crafty_id == "id-1"
    await bot.ensure_fresh_servers()
    await bot.get_server("Survival")
    assert fake_crafty.calls == 1

    assert bot._servers_refreshed_at is not None
    bot._servers_refreshed_at -= SERVER_CACHE_TTL + 1
    await bot.ensure_fresh_servers()
    assert fake_crafty.calls == 2


async def test_failed_refresh_keeps_stale_list_and_retries(
    bot: CircuitGuardBot, fake_crafty: FakeCrafty
) -> None:
    await bot.ensure_fresh_servers()
    assert bot._servers_refreshed_at is not None
    bot._servers_refreshed_at -= SERVER_CACHE_TTL + 1

    fake_crafty.fail = True
    server = await bot.get_server("Survival")  # stale list still serves lookups
    assert server.label == "Survival"
    assert fake_crafty.calls == 2

    fake_crafty.fail = False
    await bot.ensure_fresh_servers()  # timestamp was not advanced, so it retries
    assert fake_crafty.calls == 3


async def test_failed_refresh_with_empty_cache_raises(
    bot: CircuitGuardBot, fake_crafty: FakeCrafty
) -> None:
    fake_crafty.fail = True
    with pytest.raises(CraftyUnavailable):
        await bot.get_server("Survival")

    fake_crafty.fail = False
    server = await bot.get_server("Survival")  # recovers on the next action
    assert server.crafty_id == "id-1"


async def test_manual_config_never_refreshes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        discord_token="token",
        crafty_url="https://crafty.example.com",
        crafty_api_token="crafty-token",
        console_backend="crafty",
        db_path=tmp_path / "test.db",
        MC_SERVERS=[{"label": "Survival", "crafty_id": "id-1"}],
    )
    bot = CircuitGuardBot(settings)
    try:
        fake = FakeCrafty()
        monkeypatch.setattr(bot.crafty, "list_servers", fake.list_servers)

        assert not bot.auto_detect_servers
        server = await bot.get_server("Survival")
        assert server.crafty_id == "id-1"
        assert fake.calls == 0
    finally:
        await bot.crafty.close()
        await bot.mojang.close()
