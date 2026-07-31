from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

from circuitguard.bot import CircuitGuardBot
from circuitguard.commands import servers as servers_module
from circuitguard.commands.servers import WHITELIST_SUGGEST_TTL, cached_whitelist
from circuitguard.config import ServerConfig, Settings
from circuitguard.errors import ConsoleUnavailable


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    servers_module._whitelist_cache.clear()
    yield
    servers_module._whitelist_cache.clear()


class FakeConsole:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    async def execute(self, server: ServerConfig, command: str) -> str:
        assert command == "whitelist list"
        self.calls += 1
        if self.fail:
            raise ConsoleUnavailable(server)
        return "There are 2 whitelisted player(s): Steve, Alex"


@pytest.fixture
async def bot(tmp_path: Path) -> AsyncIterator[CircuitGuardBot]:
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
    bot.console = FakeConsole()  # type: ignore[assignment]
    yield bot
    await bot.crafty.close()
    await bot.mojang.close()


async def test_cached_whitelist_fetches_and_caches(bot: CircuitGuardBot) -> None:
    console = bot.console
    assert isinstance(console, FakeConsole)

    assert await cached_whitelist(bot, "Survival") == ["Steve", "Alex"]
    assert await cached_whitelist(bot, "survival") == ["Steve", "Alex"]  # label is normalized
    assert console.calls == 1

    fetched_at, players = servers_module._whitelist_cache["Survival"]
    servers_module._whitelist_cache["Survival"] = (fetched_at - WHITELIST_SUGGEST_TTL - 1, players)
    await cached_whitelist(bot, "Survival")
    assert console.calls == 2


async def test_cached_whitelist_propagates_console_errors(bot: CircuitGuardBot) -> None:
    console = bot.console
    assert isinstance(console, FakeConsole)
    console.fail = True

    with pytest.raises(ConsoleUnavailable):
        await cached_whitelist(bot, "Survival")
