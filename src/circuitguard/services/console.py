import asyncio
import logging
import re
from typing import Protocol

from circuitguard.config import ServerConfig
from circuitguard.errors import ConsoleUnavailable, CraftyUnavailable
from circuitguard.services.crafty import CraftyClient

log = logging.getLogger(__name__)

# Vanilla/Paper console line, e.g. "[12:34:56] [Server thread/INFO]: message"
LOG_LINE_PREFIX = re.compile(r"^\[\d{2}:\d{2}:\d{2}(?:\.\d+)?\] \[[^\]]*\]:\s?")


class ConsoleService(Protocol):
    async def execute(self, server: ServerConfig, command: str) -> str:
        """Run a console command on the server and return its response."""
        ...


def parse_whitelist_list(response: str) -> list[str]:
    """Parse vanilla `whitelist list` output.

    Formats: "There are N whitelisted player(s): a, b" or
    "There are no whitelisted players".
    """
    marker = "whitelisted player(s):"
    if marker in response:
        names_part = response.split(marker, 1)[1]
        return [name.strip() for name in names_part.split(",") if name.strip()]
    return []


def lines_after(baseline: list[str], current: list[str]) -> list[str]:
    """Lines in `current` that appeared after the last line of `baseline`.

    Both are tails of the same rolling log buffer; timestamps make lines
    near-unique, so anchoring on the last occurrence of the baseline's final
    line is reliable enough. If the anchor scrolled out entirely, everything
    is considered new.
    """
    if not baseline:
        return current
    anchor = baseline[-1]
    for index in range(len(current) - 1, -1, -1):
        if current[index] == anchor:
            return current[index + 1 :]
    return current


def strip_log_prefix(line: str) -> str:
    return LOG_LINE_PREFIX.sub("", line)


class CraftyConsoleService:
    """Console access through the Crafty API alone — no RCON port needed.

    Crafty's stdin endpoint returns no command output, so the response is
    scraped from the console log: snapshot the log, send the command, then
    poll for new lines. Best effort — concurrent server output (chat, joins)
    can be mixed into the captured response.
    """

    def __init__(
        self,
        crafty: CraftyClient,
        *,
        poll_interval: float = 0.4,
        max_polls: int = 10,
    ) -> None:
        self._crafty = crafty
        self._poll_interval = poll_interval
        self._max_polls = max_polls

    async def execute(self, server: ServerConfig, command: str) -> str:
        try:
            baseline = await self._crafty.get_logs(server.crafty_id)
            await self._crafty.send_stdin(server.crafty_id, command)

            fresh: list[str] = []
            for _ in range(self._max_polls):
                await asyncio.sleep(self._poll_interval)
                current = await self._crafty.get_logs(server.crafty_id)
                fresh = lines_after(baseline, current)
                if fresh:
                    # One settle poll so multi-line output isn't cut short.
                    await asyncio.sleep(self._poll_interval)
                    current = await self._crafty.get_logs(server.crafty_id)
                    fresh = lines_after(baseline, current)
                    break
        except CraftyUnavailable as exc:
            log.warning("Crafty console failed for %s: %s", server.label, exc)
            raise ConsoleUnavailable(server) from exc

        return "\n".join(strip_log_prefix(line) for line in fresh).strip()
