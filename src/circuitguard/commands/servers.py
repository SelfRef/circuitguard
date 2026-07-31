import time
from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands

from circuitguard.errors import CircuitGuardError, CraftyUnavailable
from circuitguard.permissions import require_mod_of_target_server
from circuitguard.services.console import parse_whitelist_list
from circuitguard.services.crafty import PowerAction, ServerStats

if TYPE_CHECKING:
    from circuitguard.bot import CircuitGuardBot


def _bot(interaction: discord.Interaction) -> "CircuitGuardBot":
    return cast("CircuitGuardBot", interaction.client)


# Java Edition gamerules (snake_case names introduced in 1.21.11) with their
# types, for autocomplete. Suggestions only — free-typed names still go
# through, so modded/datapack rules (e.g. `jade:max_position_deviation`) and
# older camelCase servers work too.
GAMERULES: dict[str, str] = {
    "advance_time": "bool",
    "advance_weather": "bool",
    "allow_entering_nether_using_portals": "bool",
    "block_drops": "bool",
    "block_explosion_drop_decay": "bool",
    "command_block_output": "bool",
    "command_blocks_work": "bool",
    "drowning_damage": "bool",
    "elytra_movement_check": "bool",
    "ender_pearls_vanish_on_death": "bool",
    "entity_drops": "bool",
    "fall_damage": "bool",
    "fire_damage": "bool",
    "fire_spread_radius_around_player": "int",
    "forgive_dead_players": "bool",
    "freeze_damage": "bool",
    "global_sound_events": "bool",
    "immediate_respawn": "bool",
    "keep_inventory": "bool",
    "lava_source_conversion": "bool",
    "limited_crafting": "bool",
    "locator_bar": "bool",
    "log_admin_commands": "bool",
    "max_block_modifications": "int",
    "max_command_forks": "int",
    "max_command_sequence_length": "int",
    "max_entity_cramming": "int",
    "max_minecart_speed": "int",
    "max_snow_accumulation_height": "int",
    "mob_drops": "bool",
    "mob_explosion_drop_decay": "bool",
    "mob_griefing": "bool",
    "natural_health_regeneration": "bool",
    "player_movement_check": "bool",
    "players_nether_portal_creative_delay": "int",
    "players_nether_portal_default_delay": "int",
    "players_sleeping_percentage": "int",
    "projectiles_can_break_blocks": "bool",
    "pvp": "bool",
    "raids": "bool",
    "random_tick_speed": "int",
    "reduced_debug_info": "bool",
    "respawn_radius": "int",
    "send_command_feedback": "bool",
    "show_advancement_messages": "bool",
    "show_death_messages": "bool",
    "spawn_mobs": "bool",
    "spawn_monsters": "bool",
    "spawn_patrols": "bool",
    "spawn_phantoms": "bool",
    "spawn_wandering_traders": "bool",
    "spawn_wardens": "bool",
    "spawner_blocks_work": "bool",
    "spectators_generate_chunks": "bool",
    "spread_vines": "bool",
    "tnt_explodes": "bool",
    "tnt_explosion_drop_decay": "bool",
    "universal_anger": "bool",
    "water_source_conversion": "bool",
}


def matching_gamerules(current: str) -> list[str]:
    needle = current.casefold()
    return [rule for rule in GAMERULES if needle in rule.casefold()][:25]


def gamerule_value_options(rule: str, current: str) -> list[str]:
    if GAMERULES.get(rule) == "bool":
        return [v for v in ("true", "false") if current.casefold() in v]
    return []


async def gamerule_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=rule, value=rule) for rule in matching_gamerules(current)]


async def gamerule_value_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    rule = str(interaction.namespace.rule or "")
    return [
        app_commands.Choice(name=value, value=value)
        for value in gamerule_value_options(rule, current)
    ]


# Whitelist fetches for player autocomplete are cached briefly so each
# keystroke doesn't hit the server console again.
WHITELIST_SUGGEST_TTL = 30.0
_whitelist_cache: dict[str, tuple[float, list[str]]] = {}


async def cached_whitelist(bot: "CircuitGuardBot", server_label: str) -> list[str]:
    server_cfg = await bot.get_server(server_label)
    now = time.monotonic()
    cached = _whitelist_cache.get(server_cfg.label)
    if cached is not None and now - cached[0] < WHITELIST_SUGGEST_TTL:
        return cached[1]
    response = await bot.console.execute(server_cfg, "whitelist list")
    players = parse_whitelist_list(response)
    _whitelist_cache[server_cfg.label] = (now, players)
    return players


async def whitelisted_player_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Suggest whitelisted players of the server chosen in the `server` option."""
    label = str(interaction.namespace.server or "")
    if not label:
        return []
    try:
        players = await cached_whitelist(_bot(interaction), label)
    except CircuitGuardError:
        return []  # autocomplete can't show errors; free-typed names still work
    needle = current.casefold()
    return [
        app_commands.Choice(name=player, value=player)
        for player in sorted(players, key=str.casefold)
        if needle in player.casefold()
    ][:25]


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


class McModGroup(app_commands.Group):
    """Top-level /mcmod group for moderation commands.

    default_permissions hides it from members without Manage Server; server
    admins can expose it to mod roles via Server Settings → Integrations.
    Visibility only — the real authorization is the role checks at runtime.
    """

    def __init__(self, bot: "CircuitGuardBot") -> None:
        super().__init__(
            name="mcmod",
            description="Minecraft moderation commands",
            guild_only=True,
            default_permissions=discord.Permissions(manage_guild=True),
        )
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

    @app_commands.command(name="gamerule", description="Get or set a gamerule on a server")
    @app_commands.autocomplete(
        server=server_autocomplete,
        rule=gamerule_autocomplete,
        value=gamerule_value_autocomplete,
    )
    @app_commands.describe(
        server="Server to query",
        rule="Gamerule name",
        value="New value — omit to read the current value",
    )
    @require_mod_of_target_server()
    async def gamerule(
        self,
        interaction: discord.Interaction,
        server: str,
        rule: str,
        value: str | None = None,
    ) -> None:
        # Reads are ephemeral; changes are visible to the channel.
        await interaction.response.defer(ephemeral=value is None)
        server_cfg = await self.bot.get_server(server)

        command = f"gamerule {rule}" if value is None else f"gamerule {rule} {value}"
        try:
            response = await self.bot.console.execute(server_cfg, command)
        except Exception as exc:
            if value is not None:
                await self.bot.audit.record(
                    interaction.user.id,
                    "gamerule",
                    server_label=server_cfg.label,
                    target=f"{rule}={value}",
                    success=False,
                    detail=str(exc),
                )
            raise

        if value is not None:
            await self.bot.audit.record(
                interaction.user.id,
                "gamerule",
                server_label=server_cfg.label,
                target=f"{rule}={value}",
                success=True,
                detail=response,
            )
        shown = response or "(no response from server)"
        await interaction.followup.send(
            f"🎛️ **{server_cfg.label}**: {shown}", ephemeral=value is None
        )
