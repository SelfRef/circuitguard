import re
from dataclasses import dataclass

import httpx

from circuitguard.errors import InvalidUsername, MojangRateLimited, UsernameNotFound

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


@dataclass(frozen=True)
class MojangProfile:
    uuid: str
    name: str


class MojangClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(base_url="https://api.mojang.com", timeout=10)

    async def close(self) -> None:
        await self._client.aclose()

    async def lookup(self, username: str) -> MojangProfile:
        """Resolve a username to its canonical name and UUID via the Mojang API."""
        if not USERNAME_RE.match(username):
            raise InvalidUsername(username)

        response = await self._client.get(f"/users/profiles/minecraft/{username}")
        if response.status_code == 404:
            raise UsernameNotFound(username)
        if response.status_code == 429:
            raise MojangRateLimited("Mojang API rate limit hit")
        response.raise_for_status()

        data = response.json()
        return MojangProfile(uuid=data["id"], name=data["name"])
