from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands

from circuitguard.errors import CraftyUnavailable
from circuitguard.permissions import require_mod_of_target_server
from circuitguard.services.crafty import PowerAction, ServerStats

if TYPE_CHECKING:
    from circuitguard.bot import CircuitGuardBot


def _bot(interaction: discord.Interaction) -> "CircuitGuardBot":
    return cast("CircuitGuardBot", interaction.client)


async def server_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    bot = _bot(interaction)
    try:
        await bot.ensure_fresh_servers()
    except CraftyUnavailable:
        return []  # autocomplete can't show errors; the command itself will report it
    return await bot.registry.autocomplete(interaction, current)


class McGroup(app_commands.Group):
    """Top-level /mc command group; domain subgroups are attached in setup_hook."""

    def __init__(self, bot: "CircuitGuardBot") -> None:
        super().__init__(name="mc", description="Minecraft commands", guild_only=True)
        self.bot = bot

    @app_commands.command(name="servers", description="List all servers with status and players")
    async def servers(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        await self.bot.ensure_fresh_servers()
        registry = self.bot.registry
        if not registry.servers:
            await interaction.followup.send(
                "🤷 Crafty reports no servers — create one in Crafty and it will show up here."
            )
            return
        stats = await self.bot.crafty.get_stats_many([s.crafty_id for s in registry.servers])

        embed = discord.Embed(title="Minecraft servers", color=discord.Color.green())
        for server in registry.servers:
            embed.add_field(
                name=server.label,
                value=format_stats(stats.get(server.crafty_id)),
                inline=False,
            )
        await interaction.followup.send(embed=embed)


def format_stats(stats: ServerStats | None) -> str:
    if stats is None:
        return "❓ Status unavailable"
    if not stats.running:
        return "⛔ Offline"
    lines = [f"✅ Online — `{stats.version}` — {stats.online}/{stats.max_players} players"]
    lines.extend(f"• {player}" for player in stats.players)
    return "\n".join(lines)


class ServerGroup(app_commands.Group):
    """/mc server — lifecycle and console commands, mod/admin only."""

    def __init__(self, bot: "CircuitGuardBot") -> None:
        super().__init__(name="server", description="Manage a Minecraft server")
        self.bot = bot

    @app_commands.command(name="start", description="Start a server")
    @app_commands.autocomplete(server=server_autocomplete)
    @require_mod_of_target_server()
    async def start(self, interaction: discord.Interaction, server: str) -> None:
        await self._power(interaction, server, PowerAction.START, "▶️ Starting")

    @app_commands.command(name="stop", description="Stop a server")
    @app_commands.autocomplete(server=server_autocomplete)
    @require_mod_of_target_server()
    async def stop(self, interaction: discord.Interaction, server: str) -> None:
        await self._power(interaction, server, PowerAction.STOP, "⏹️ Stopping")

    @app_commands.command(name="restart", description="Restart a server")
    @app_commands.autocomplete(server=server_autocomplete)
    @require_mod_of_target_server()
    async def restart(self, interaction: discord.Interaction, server: str) -> None:
        await self._power(interaction, server, PowerAction.RESTART, "🔄 Restarting")

    @app_commands.command(name="backup", description="Trigger a backup of a server")
    @app_commands.autocomplete(server=server_autocomplete)
    @require_mod_of_target_server()
    async def backup(self, interaction: discord.Interaction, server: str) -> None:
        await self._power(interaction, server, PowerAction.BACKUP, "💾 Backing up")

    async def _power(
        self,
        interaction: discord.Interaction,
        server_label: str,
        action: PowerAction,
        verb: str,
    ) -> None:
        await interaction.response.defer()
        server = await self.bot.get_server(server_label)
        audit_action = action.name.lower()

        warning = ""
        if action in (PowerAction.STOP, PowerAction.RESTART):
            stats = (await self.bot.crafty.get_stats_many([server.crafty_id]))[server.crafty_id]
            if stats is not None and stats.online > 0:
                warning = f" — ⚠️ {stats.online} player(s) currently online!"

        try:
            await self.bot.crafty.power_action(server.crafty_id, action)
        except Exception as exc:
            await self.bot.audit.record(
                interaction.user.id,
                audit_action,
                server_label=server.label,
                success=False,
                detail=str(exc),
            )
            raise

        await self.bot.audit.record(
            interaction.user.id, audit_action, server_label=server.label, success=True
        )
        await interaction.followup.send(
            f"{verb} **{server.label}**{warning} — requested by {interaction.user.mention}"
        )

    @app_commands.command(name="command", description="Run a console command on a server")
    @app_commands.autocomplete(server=server_autocomplete)
    @app_commands.describe(command="Console command to run (without leading slash)")
    @require_mod_of_target_server()
    async def console(self, interaction: discord.Interaction, server: str, command: str) -> None:
        await interaction.response.defer(ephemeral=True)
        server_cfg = await self.bot.get_server(server)

        try:
            response = await self.bot.console.execute(server_cfg, command)
        except Exception as exc:
            await self.bot.audit.record(
                interaction.user.id,
                "command",
                server_label=server_cfg.label,
                target=command,
                success=False,
                detail=str(exc),
            )
            raise

        await self.bot.audit.record(
            interaction.user.id,
            "command",
            server_label=server_cfg.label,
            target=command,
            success=True,
            detail=response[:500],
        )
        shown = response or "(no output)"
        if len(shown) > 1900:
            shown = shown[:1900] + "…"
        await interaction.followup.send(f"```\n{shown}\n```", ephemeral=True)
