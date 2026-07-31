import pytest
import respx

from circuitguard.errors import CraftyUnavailable
from circuitguard.services.crafty import CraftyClient, PowerAction, parse_players

BASE = "https://crafty.example.com"


@pytest.fixture
def client() -> CraftyClient:
    return CraftyClient(BASE, "token")


def test_parse_players_variants() -> None:
    assert parse_players("['Steve', 'Alex']") == ["Steve", "Alex"]
    assert parse_players("[]") == []
    assert parse_players('["O\'Brien"]') == ["O'Brien"]
    assert parse_players("") == []
    assert parse_players(None) == []
    assert parse_players("garbage[") == []
    assert parse_players(["Already", "List"]) == ["Already", "List"]


@respx.mock
async def test_list_servers(client: CraftyClient) -> None:
    respx.get(f"{BASE}/api/v2/servers").respond(
        200,
        json={"data": [{"server_id": "id-1", "server_name": "Survival"}]},
    )
    servers = await client.list_servers()
    assert servers[0].server_id == "id-1"
    assert servers[0].name == "Survival"


@respx.mock
async def test_get_stats(client: CraftyClient) -> None:
    respx.get(f"{BASE}/api/v2/servers/id-1/stats").respond(
        200,
        json={
            "data": {
                "running": True,
                "version": "1.21.4",
                "online": 2,
                "max": 20,
                "players": "['Steve', 'Alex']",
                "desc": "A server",
            }
        },
    )
    stats = await client.get_stats("id-1")
    assert stats.running is True
    assert stats.online == 2
    assert stats.max_players == 20
    assert stats.players == ["Steve", "Alex"]


@respx.mock
async def test_get_stats_many_partial_failure(client: CraftyClient) -> None:
    respx.get(f"{BASE}/api/v2/servers/ok/stats").respond(
        200, json={"data": {"running": False, "version": "1.21", "online": 0, "max": 10}}
    )
    respx.get(f"{BASE}/api/v2/servers/bad/stats").respond(500)
    stats = await client.get_stats_many(["ok", "bad"])
    assert stats["ok"] is not None and stats["ok"].running is False
    assert stats["bad"] is None


@respx.mock
async def test_server_error_raises(client: CraftyClient) -> None:
    respx.get(f"{BASE}/api/v2/servers").respond(500)
    with pytest.raises(CraftyUnavailable):
        await client.list_servers()


@respx.mock
async def test_read_file(client: CraftyClient) -> None:
    respx.get(f"{BASE}/api/v2/servers/id-1").respond(
        200, json={"status": "ok", "data": {"path": "/srv/servers/id-1"}}
    )
    route = respx.post(f"{BASE}/api/v2/servers/id-1/files").respond(
        200, json={"status": "ok", "data": {"content": '[{"name": "Steve"}]'}}
    )
    content = await client.read_file("id-1", "ops.json")
    assert content == '[{"name": "Steve"}]'
    assert route.calls.last.request.content == b'{"path":"/srv/servers/id-1/ops.json"}'


@respx.mock
async def test_read_file_plain_data(client: CraftyClient) -> None:
    respx.get(f"{BASE}/api/v2/servers/id-1").respond(
        200, json={"status": "ok", "data": {"path": "/srv/servers/id-1"}}
    )
    respx.post(f"{BASE}/api/v2/servers/id-1/files").respond(
        200, json={"status": "ok", "data": "raw file text"}
    )
    assert await client.read_file("id-1", "ops.json") == "raw file text"


@respx.mock
async def test_read_file_error_raises(client: CraftyClient) -> None:
    respx.get(f"{BASE}/api/v2/servers/id-1").respond(
        200, json={"status": "ok", "data": {"path": "/srv/servers/id-1"}}
    )
    respx.post(f"{BASE}/api/v2/servers/id-1/files").respond(
        200, json={"status": "error", "error": "NOT_FOUND"}
    )
    with pytest.raises(CraftyUnavailable):
        await client.read_file("id-1", "ops.json")


@respx.mock
async def test_power_action_url(client: CraftyClient) -> None:
    route = respx.post(f"{BASE}/api/v2/servers/id-1/action/restart_server").respond(
        200, json={"status": "ok"}
    )
    await client.power_action("id-1", PowerAction.RESTART)
    assert route.called
