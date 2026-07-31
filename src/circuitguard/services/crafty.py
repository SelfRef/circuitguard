import ast
import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum

import httpx

from circuitguard.errors import CraftyUnavailable

log = logging.getLogger(__name__)


class PowerAction(StrEnum):
    START = "start_server"
    STOP = "stop_server"
    RESTART = "restart_server"
    BACKUP = "backup_server"


@dataclass(frozen=True)
class ServerStats:
    running: bool
    version: str
    online: int
    max_players: int
    players: list[str]
    description: str


@dataclass(frozen=True)
class CraftyServer:
    server_id: str
    name: str


def parse_players(raw: object) -> list[str]:
    """Crafty reports players as a Python-repr string like "['Steve', 'Alex']"."""
    if isinstance(raw, list):
        return [str(player) for player in raw]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [str(player) for player in parsed]
        except (ValueError, SyntaxError):
            log.warning("Could not parse Crafty players field: %r", raw)
    return []


class CraftyClient:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        verify_ssl: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=10,
            verify=verify_ssl,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, *, content: str | None = None
    ) -> dict[str, object]:
        try:
            response = await self._client.request(method, path, content=content)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CraftyUnavailable(f"Crafty request failed: {exc}") from exc
        payload: dict[str, object] = response.json()
        if payload.get("status") not in (None, "ok"):
            raise CraftyUnavailable(f"Crafty rejected {method} {path}: {payload.get('error')}")
        return payload

    async def list_servers(self) -> list[CraftyServer]:
        payload = await self._request("GET", "/api/v2/servers")
        data = payload.get("data", [])
        assert isinstance(data, list)
        return [CraftyServer(server_id=s["server_id"], name=s["server_name"]) for s in data]

    async def get_stats(self, server_id: str) -> ServerStats:
        payload = await self._request("GET", f"/api/v2/servers/{server_id}/stats")
        data = payload.get("data")
        assert isinstance(data, dict)
        return ServerStats(
            running=bool(data.get("running")),
            version=str(data.get("version") or "?"),
            online=int(data.get("online") or 0),
            max_players=int(data.get("max") or 0),
            players=parse_players(data.get("players")),
            description=str(data.get("desc") or ""),
        )

    async def get_stats_many(self, server_ids: list[str]) -> dict[str, ServerStats | None]:
        """Fetch stats for many servers concurrently; None for servers that failed."""
        results = await asyncio.gather(
            *(self.get_stats(server_id) for server_id in server_ids),
            return_exceptions=True,
        )
        stats: dict[str, ServerStats | None] = {}
        for server_id, result in zip(server_ids, results, strict=True):
            if isinstance(result, BaseException):
                log.warning("Stats fetch failed for %s: %s", server_id, result)
                stats[server_id] = None
            else:
                stats[server_id] = result
        return stats

    async def power_action(self, server_id: str, action: PowerAction) -> None:
        await self._request("POST", f"/api/v2/servers/{server_id}/action/{action.value}")

    async def send_stdin(self, server_id: str, command: str) -> None:
        """Send a console command to the server process; produces no command output."""
        await self._request("POST", f"/api/v2/servers/{server_id}/stdin", content=command)

    async def get_logs(self, server_id: str) -> list[str]:
        """Return the most recent console log lines Crafty has buffered."""
        payload = await self._request("GET", f"/api/v2/servers/{server_id}/logs?raw=true")
        data = payload.get("data", [])
        assert isinstance(data, list)
        return [str(line) for line in data]
