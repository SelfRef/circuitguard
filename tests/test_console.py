import httpx
import pytest
import respx

from circuitguard.config import ServerConfig
from circuitguard.errors import ConsoleUnavailable
from circuitguard.services.console import (
    CraftyConsoleService,
    lines_after,
    parse_whitelist_list,
    strip_log_prefix,
)
from circuitguard.services.crafty import CraftyClient

BASE = "https://crafty.example.com"


def test_parses_players() -> None:
    assert parse_whitelist_list("There are 3 whitelisted player(s): Steve, Alex, Herobrine") == [
        "Steve",
        "Alex",
        "Herobrine",
    ]


def test_single_player() -> None:
    assert parse_whitelist_list("There are 1 whitelisted player(s): Steve") == ["Steve"]


def test_no_players() -> None:
    assert parse_whitelist_list("There are no whitelisted players") == []


def test_empty_response() -> None:
    assert parse_whitelist_list("") == []


def test_lines_after_appended() -> None:
    assert lines_after(["a", "b"], ["a", "b", "c", "d"]) == ["c", "d"]


def test_lines_after_no_change() -> None:
    assert lines_after(["a", "b"], ["a", "b"]) == []


def test_lines_after_scrolled_buffer() -> None:
    assert lines_after(["a", "b"], ["b", "c"]) == ["c"]


def test_lines_after_anchor_gone() -> None:
    assert lines_after(["a", "b"], ["x", "y"]) == ["x", "y"]


def test_lines_after_empty_baseline() -> None:
    assert lines_after([], ["a"]) == ["a"]


def test_lines_after_duplicate_anchor_uses_last() -> None:
    assert lines_after(["tick", "tick"], ["tick", "tick", "new"]) == ["new"]


def test_strip_log_prefix() -> None:
    line = "[12:34:56] [Server thread/INFO]: There are no whitelisted players"
    assert strip_log_prefix(line) == "There are no whitelisted players"
    assert strip_log_prefix("no prefix here") == "no prefix here"


SERVER = ServerConfig(label="Survival", crafty_id="id-1")


def make_console() -> CraftyConsoleService:
    client = CraftyClient(BASE, "token")
    return CraftyConsoleService(client, poll_interval=0.01, max_polls=3)


def logs_json(*lines: str) -> dict[str, object]:
    return {"status": "ok", "data": list(lines)}


OLD = "[10:00:00] [Server thread/INFO]: old line"
NEW = "[10:00:01] [Server thread/INFO]: There are 1 whitelisted player(s): Steve"


@respx.mock
async def test_crafty_console_captures_response() -> None:
    stdin = respx.post(f"{BASE}/api/v2/servers/id-1/stdin").respond(200, json={"status": "ok"})
    respx.get(f"{BASE}/api/v2/servers/id-1/logs", params={"raw": "true"}).side_effect = [
        httpx.Response(200, json=logs_json(OLD)),  # baseline
        httpx.Response(200, json=logs_json(OLD)),  # first poll: nothing yet
        httpx.Response(200, json=logs_json(OLD, NEW)),  # second poll: output arrived
        httpx.Response(200, json=logs_json(OLD, NEW)),  # settle poll
    ]

    response = await make_console().execute(SERVER, "whitelist list")

    assert stdin.called
    assert stdin.calls.last.request.content == b"whitelist list"
    assert response == "There are 1 whitelisted player(s): Steve"


@respx.mock
async def test_crafty_console_no_output_returns_empty() -> None:
    respx.post(f"{BASE}/api/v2/servers/id-1/stdin").respond(200, json={"status": "ok"})
    respx.get(f"{BASE}/api/v2/servers/id-1/logs", params={"raw": "true"}).respond(
        200, json=logs_json(OLD)
    )

    assert await make_console().execute(SERVER, "save-all") == ""


@respx.mock
async def test_crafty_console_stdin_rejected() -> None:
    respx.get(f"{BASE}/api/v2/servers/id-1/logs", params={"raw": "true"}).respond(
        200, json=logs_json(OLD)
    )
    respx.post(f"{BASE}/api/v2/servers/id-1/stdin").respond(
        200, json={"status": "error", "error": "SERVER_NOT_RUNNING"}
    )

    with pytest.raises(ConsoleUnavailable):
        await make_console().execute(SERVER, "whitelist list")


@respx.mock
async def test_crafty_console_crafty_down() -> None:
    respx.get(f"{BASE}/api/v2/servers/id-1/logs", params={"raw": "true"}).respond(503)

    with pytest.raises(ConsoleUnavailable):
        await make_console().execute(SERVER, "whitelist list")
