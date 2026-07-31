import httpx
import pytest
import respx

from circuitguard.errors import InvalidUsername, MojangRateLimited, UsernameNotFound
from circuitguard.services.mojang import MojangClient


@pytest.fixture
def client() -> MojangClient:
    return MojangClient(client=httpx.AsyncClient(base_url="https://api.mojang.com"))


@respx.mock
async def test_lookup_found(client: MojangClient) -> None:
    respx.get("https://api.mojang.com/users/profiles/minecraft/steve").respond(
        200, json={"id": "abc123", "name": "Steve"}
    )
    profile = await client.lookup("steve")
    assert profile.uuid == "abc123"
    assert profile.name == "Steve"


@respx.mock
async def test_lookup_not_found(client: MojangClient) -> None:
    respx.get("https://api.mojang.com/users/profiles/minecraft/ghost").respond(404)
    with pytest.raises(UsernameNotFound):
        await client.lookup("ghost")


@respx.mock
async def test_lookup_rate_limited(client: MojangClient) -> None:
    respx.get("https://api.mojang.com/users/profiles/minecraft/steve").respond(429)
    with pytest.raises(MojangRateLimited):
        await client.lookup("steve")


@pytest.mark.parametrize("username", ["ab", "a" * 17, "bad name", "bad-name", "näme", ""])
async def test_invalid_usernames_rejected_without_api_call(
    client: MojangClient, username: str
) -> None:
    with pytest.raises(InvalidUsername):
        await client.lookup(username)
