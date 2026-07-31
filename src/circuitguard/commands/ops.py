import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from circuitguard.errors import CircuitGuardError
from circuitguard.permissions import require_mod_of_target_server

from .servers import _bot, server_autocomplete, whitelisted_player_autocomplete

if TYPE_CHECKING:
    from circuitguard.bot import CircuitGuardBot


@dataclass(frozen=True)
class OpEntry:
    name: str
    level: int


def parse_ops_json(content: str) -> list[OpEntry]:
    """Parse a vanilla ops.json file; malformed content yields an empty list."""
    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return [
        OpEntry(name=str(item["name"]), level=int(item.get("level") or 0))
        for item in raw
        if isinstance(item, dict) and item.get("name")
    ]


async def fetch_ops(bot: "CircuitGuardBot", server_label: str) -> list[OpEntry]:
    """Current operators, read from the server's ops.json via the Crafty file API."""
    server_cfg = await bot.get_server(server_label)
    content = await bot.crafty.read_file(server_cfg.crafty_id, "ops.json")
    return parse_ops_json(content)


OPS_SUGGEST_TTL = 30.0
_ops_cache: dict[str, tuple[float, list[str]]] = {}


def invalidate_ops_cache(server_label: str) -> None:
    _ops_cache.pop(server_label, None)


async def op_player_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Suggest current operators; falls back to whitelist suggestions if
    ops.json can't be read."""
    label = str(interaction.namespace.server or "")
    if not label:
        return []
    bot = _bot(interaction)
    try:
        server_cfg = await bot.get_server(label)
    except CircuitGuardError:
        return []

    now = time.monotonic()
    cached = _ops_cache.get(server_cfg.label)
    if cached is not None and now - cached[0] < OPS_SUGGEST_TTL:
        names = cached[1]
    else:
        try:
            names = [op.name for op in await fetch_ops(bot, label)]
        except CircuitGuardError:
            return await whitelisted_player_autocomplete(interaction, current)
        _ops_cache[server_cfg.label] = (now, names)

    needle = current.casefold()
    return [
        app_commands.Choice(name=name, value=name)
        for name in sorted(names, key=str.casefold)
        if needle in name.casefold()
    ][:25]


class OpGroup(app_commands.Group):
    """/mcmod op — manage server operators, mods only."""

    def __init__(self, bot: "CircuitGuardBot") -> None:
        super().__init__(name="op", description="Manage server operators")
        self.bot = bot

    @app_commands.command(name="add", description="Grant operator status to a player")
    @app_commands.autocomplete(server=server_autocomplete, player=whitelisted_player_autocomplete)
    @app_commands.describe(server="Server to op on", player="Player to make an operator")
    @require_mod_of_target_server()
    async def add(self, interaction: discord.Interaction, server: str, player: str) -> None:
        await self._change(interaction, server, player, grant=True)

    @app_commands.command(name="remove", description="Revoke a player's operator status")
    @app_commands.autocomplete(server=server_autocomplete, player=op_player_autocomplete)
    @app_commands.describe(server="Server to deop on", player="Operator to demote")
    @require_mod_of_target_server()
    async def remove(self, interaction: discord.Interaction, server: str, player: str) -> None:
        await self._change(interaction, server, player, grant=False)

    @app_commands.command(name="list", description="Show a server's operators")
    @app_commands.autocomplete(server=server_autocomplete)
    @app_commands.describe(server="Server to inspect")
    @require_mod_of_target_server()
    async def list_(self, interaction: discord.Interaction, server: str) -> None:
        await interaction.response.defer(ephemeral=True)
        ops = await fetch_ops(self.bot, server)
        server_cfg = await self.bot.get_server(server)

        if ops:
            body = "\n".join(
                f"• {op.name} (level {op.level})"
                for op in sorted(ops, key=lambda op: op.name.casefold())
            )
            message = f"👑 **{server_cfg.label}** operators ({len(ops)}):\n{body}"
        else:
            message = f"**{server_cfg.label}** has no operators."
        await interaction.followup.send(message, ephemeral=True)

    async def _change(
        self, interaction: discord.Interaction, server_label: str, player: str, *, grant: bool
    ) -> None:
        await interaction.response.defer()
        server_cfg = await self.bot.get_server(server_label)
        action = "op_add" if grant else "op_remove"
        command = f"op {player}" if grant else f"deop {player}"

        try:
            response = await self.bot.console.execute(server_cfg, command)
        except Exception as exc:
            await self.bot.audit.record(
                interaction.user.id,
                action,
                server_label=server_cfg.label,
                target=player,
                success=False,
                detail=str(exc),
            )
            raise

        await self.bot.audit.record(
            interaction.user.id,
            action,
            server_label=server_cfg.label,
            target=player,
            success=True,
            detail=response,
        )
        invalidate_ops_cache(server_cfg.label)
        if "nothing changed" in response.lower():
            message = f"ℹ️ **{server_cfg.label}**: {response}"
        elif grant:
            message = f"👑 **{player}** is now an operator on **{server_cfg.label}**."
        else:
            message = f"🧹 **{player}** is no longer an operator on **{server_cfg.label}**."
        await interaction.followup.send(message)
