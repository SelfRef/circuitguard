from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands

from circuitguard.errors import NotLinkedError, PermissionDenied
from circuitguard.permissions import is_mod_for, member_role_ids
from circuitguard.services.console import parse_whitelist_list

from .servers import server_autocomplete

if TYPE_CHECKING:
    from circuitguard.bot import CircuitGuardBot


def make_link_command(bot: "CircuitGuardBot") -> app_commands.Command[Any, ..., None]:
    @app_commands.command(
        name="link", description="Link your Minecraft username to your Discord account"
    )
    @app_commands.describe(username="Your Minecraft username")
    async def link(interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer(ephemeral=True)

        profile = await bot.mojang.lookup(username)
        await bot.user_repo.upsert_link(interaction.user.id, profile.name, profile.uuid)
        await bot.audit.record(interaction.user.id, "link", target=profile.name, success=True)
        await interaction.followup.send(
            f"✅ Linked your Discord account to Minecraft player **{profile.name}**. "
            "You can now use `/mc whitelist add`.",
            ephemeral=True,
        )

    return link


class WhitelistGroup(app_commands.Group):
    """/mc whitelist — self-service for everyone, arbitrary players for mods."""

    def __init__(self, bot: "CircuitGuardBot") -> None:
        super().__init__(name="whitelist", description="Manage server whitelists")
        self.bot = bot

    @app_commands.command(name="add", description="Add yourself (or a player, mods only)")
    @app_commands.autocomplete(server=server_autocomplete)
    @app_commands.describe(
        server="Server to whitelist on",
        player="Minecraft username to add (mods only; omit to add yourself)",
    )
    async def add(
        self, interaction: discord.Interaction, server: str, player: str | None = None
    ) -> None:
        await interaction.response.defer()
        server_cfg = await self.bot.get_server(server)

        if player is not None:
            if not is_mod_for(member_role_ids(interaction.user), server_cfg, self.bot.settings):
                raise PermissionDenied(server_cfg)
            username = player
        else:
            linked = await self.bot.user_repo.get(interaction.user.id)
            if linked is None:
                raise NotLinkedError("User has no linked Minecraft account")
            username = linked.mc_username

        try:
            response = await self.bot.console.execute(server_cfg, f"whitelist add {username}")
        except Exception as exc:
            await self.bot.audit.record(
                interaction.user.id,
                "whitelist_add",
                server_label=server_cfg.label,
                target=username,
                success=False,
                detail=str(exc),
            )
            raise

        await self.bot.audit.record(
            interaction.user.id,
            "whitelist_add",
            server_label=server_cfg.label,
            target=username,
            success=True,
            detail=response,
        )
        if "already whitelisted" in response.lower():
            message = f"ℹ️ **{username}** is already whitelisted on **{server_cfg.label}**."
        else:
            message = f"✅ Added **{username}** to the **{server_cfg.label}** whitelist."
        await interaction.followup.send(message)

    @app_commands.command(name="remove", description="Remove a player from a whitelist")
    @app_commands.autocomplete(server=server_autocomplete)
    @app_commands.describe(server="Server to remove from", player="Minecraft username to remove")
    async def remove(self, interaction: discord.Interaction, server: str, player: str) -> None:
        await interaction.response.defer()
        server_cfg = await self.bot.get_server(server)

        if not is_mod_for(member_role_ids(interaction.user), server_cfg, self.bot.settings):
            raise PermissionDenied(server_cfg)

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
