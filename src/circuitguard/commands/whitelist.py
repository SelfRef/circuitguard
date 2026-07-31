from typing import TYPE_CHECKING

import discord
from discord import app_commands

from circuitguard.config import ServerConfig
from circuitguard.errors import NotLinkedError
from circuitguard.permissions import require_mod_of_target_server
from circuitguard.services.console import parse_whitelist_list

from .servers import server_autocomplete, whitelisted_player_autocomplete

if TYPE_CHECKING:
    from circuitguard.bot import CircuitGuardBot


async def run_whitelist_add(
    bot: "CircuitGuardBot",
    interaction: discord.Interaction,
    server_cfg: ServerConfig,
    username: str,
) -> str:
    """Execute `whitelist add` on the server with audit logging; returns the response."""
    try:
        response = await bot.console.execute(server_cfg, f"whitelist add {username}")
    except Exception as exc:
        await bot.audit.record(
            interaction.user.id,
            "whitelist_add",
            server_label=server_cfg.label,
            target=username,
            success=False,
            detail=str(exc),
        )
        raise
    await bot.audit.record(
        interaction.user.id,
        "whitelist_add",
        server_label=server_cfg.label,
        target=username,
        success=True,
        detail=response,
    )
    return response


def format_add_response(response: str, username: str, server_label: str) -> str:
    if "already whitelisted" in response.lower():
        return f"ℹ️ **{username}** is already whitelisted on **{server_label}**."
    return f"✅ Added **{username}** to the **{server_label}** whitelist."


class WhitelistGroup(app_commands.Group):
    """/mc whitelist — self-service; linking happens inline on first use."""

    def __init__(self, bot: "CircuitGuardBot") -> None:
        super().__init__(name="whitelist", description="Whitelist yourself on a server")
        self.bot = bot

    @app_commands.command(name="me", description="Add yourself to a server's whitelist")
    @app_commands.autocomplete(server=server_autocomplete)
    @app_commands.describe(
        server="Server to whitelist on",
        username="Your Minecraft username — only needed the first time (or to change it)",
    )
    async def me(
        self, interaction: discord.Interaction, server: str, username: str | None = None
    ) -> None:
        await interaction.response.defer()
        server_cfg = await self.bot.get_server(server)

        linked = await self.bot.user_repo.get(interaction.user.id)
        linked_note = ""
        if username is None:
            if linked is None:
                raise NotLinkedError("User has no linked Minecraft account")
            name = linked.mc_username
        else:
            profile = await self.bot.mojang.lookup(username)
            name = profile.name
            if linked is None or linked.mc_username != profile.name:
                await self.bot.user_repo.upsert_link(
                    interaction.user.id, profile.name, profile.uuid
                )
                await self.bot.audit.record(
                    interaction.user.id, "link", target=profile.name, success=True
                )
                linked_note = (
                    f"\n🔗 Remembered **{profile.name}** as your Minecraft account — "
                    "next time just use `/mc whitelist me` without a username."
                )

        response = await run_whitelist_add(self.bot, interaction, server_cfg, name)
        message = format_add_response(response, name, server_cfg.label)
        await interaction.followup.send(message + linked_note)

    @app_commands.command(name="list", description="Show a server's whitelist")
    @app_commands.autocomplete(server=server_autocomplete)
    @app_commands.describe(server="Server to inspect")
    async def list_(self, interaction: discord.Interaction, server: str) -> None:
        await interaction.response.defer(ephemeral=True)
        server_cfg = await self.bot.get_server(server)

        response = await self.bot.console.execute(server_cfg, "whitelist list")
        players = parse_whitelist_list(response)
        if players:
            body = "\n".join(f"• {player}" for player in sorted(players, key=str.casefold))
            message = f"**{server_cfg.label}** whitelist ({len(players)}):\n{body}"
        else:
            message = f"**{server_cfg.label}** has no whitelisted players."
        await interaction.followup.send(message, ephemeral=True)


class ModWhitelistGroup(app_commands.Group):
    """/mcmod whitelist — manage arbitrary players, mods only."""

    def __init__(self, bot: "CircuitGuardBot") -> None:
        super().__init__(name="whitelist", description="Manage server whitelists")
        self.bot = bot

    @app_commands.command(name="add", description="Add a player to a server's whitelist")
    @app_commands.autocomplete(server=server_autocomplete)
    @app_commands.describe(server="Server to whitelist on", player="Minecraft username to add")
    @require_mod_of_target_server()
    async def add(self, interaction: discord.Interaction, server: str, player: str) -> None:
        await interaction.response.defer()
        server_cfg = await self.bot.get_server(server)

        response = await run_whitelist_add(self.bot, interaction, server_cfg, player)
        await interaction.followup.send(format_add_response(response, player, server_cfg.label))

    @app_commands.command(name="remove", description="Remove a player from a whitelist")
    @app_commands.autocomplete(server=server_autocomplete, player=whitelisted_player_autocomplete)
    @app_commands.describe(server="Server to remove from", player="Minecraft username to remove")
    @require_mod_of_target_server()
    async def remove(self, interaction: discord.Interaction, server: str, player: str) -> None:
        await interaction.response.defer()
        server_cfg = await self.bot.get_server(server)

        try:
            response = await self.bot.console.execute(server_cfg, f"whitelist remove {player}")
        except Exception as exc:
            await self.bot.audit.record(
                interaction.user.id,
                "whitelist_remove",
                server_label=server_cfg.label,
                target=player,
                success=False,
                detail=str(exc),
            )
            raise

        await self.bot.audit.record(
            interaction.user.id,
            "whitelist_remove",
            server_label=server_cfg.label,
            target=player,
            success=True,
            detail=response,
        )
        await interaction.followup.send(
            f"🗑️ Removed **{player}** from the **{server_cfg.label}** whitelist."
        )
