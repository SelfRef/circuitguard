import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from circuitguard.config import ServerConfig, Settings
from circuitguard.db.database import Database
from circuitguard.db.repository import AuditRepository, UserRepository
from circuitguard.errors import (
    ConsoleUnavailable,
    CraftyUnavailable,
    InvalidUsername,
    MojangRateLimited,
    NotLinkedError,
    PermissionDenied,
    ServerNotFound,
    UsernameNotFound,
)
from circuitguard.services.console import ConsoleService, CraftyConsoleService
from circuitguard.services.crafty import CraftyClient
from circuitguard.services.mojang import MojangClient
from circuitguard.services.rcon import RconService
from circuitguard.services.registry import ServerRegistry, build_auto_configs

log = logging.getLogger(__name__)

SERVER_CACHE_TTL = 600.0


class CircuitGuardBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents.default())
        self.settings = settings
        self.auto_detect_servers = not settings.servers
        self.registry = ServerRegistry(settings.servers)
        self._servers_refreshed_at: float | None = None
        self._refresh_lock = asyncio.Lock()
        self.db = Database(settings.db_path)
        self.user_repo = UserRepository(self.db)
        self.audit = AuditRepository(self.db)
        self.crafty = CraftyClient(
            str(settings.crafty_url),
            settings.crafty_api_token.get_secret_value(),
            verify_ssl=settings.crafty_verify_ssl,
        )
        self.console: ConsoleService = (
            CraftyConsoleService(self.crafty)
            if settings.console_backend == "crafty"
            else RconService()
        )
        self.mojang = MojangClient()
        self.tree.on_error = self.on_app_command_error  # type: ignore[method-assign]

    async def setup_hook(self) -> None:
        await self.db.connect()

        if self.auto_detect_servers:
            try:
                await self.ensure_fresh_servers()
            except CraftyUnavailable:
                log.warning("Starting without a server list — will retry on first command")

        from circuitguard.commands.servers import McGroup, ServerGroup
        from circuitguard.commands.whitelist import WhitelistGroup, make_link_command

        mc = McGroup(self)
        mc.add_command(ServerGroup(self))
        mc.add_command(WhitelistGroup(self))
        mc.add_command(make_link_command(self))
        self.tree.add_command(mc)

        if self.settings.discord_guild_id is not None:
            guild = discord.Object(id=self.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Commands synced to guild %d", self.settings.discord_guild_id)
        else:
            await self.tree.sync()
            log.info("Commands synced globally")

    async def ensure_fresh_servers(self) -> None:
        """Refresh the auto-detected server list if it is older than SERVER_CACHE_TTL.

        No-op with a manual MC_SERVERS config. When a refresh fails but a stale
        list exists, it is kept so actions still work while Crafty is briefly
        down (warning); with nothing cached the failure is fatal for the action
        (error + raise). The timestamp is not advanced on failure, so the next
        action retries.
        """
        if not self.auto_detect_servers:
            return
        async with self._refresh_lock:
            if (
                self._servers_refreshed_at is not None
                and time.monotonic() - self._servers_refreshed_at < SERVER_CACHE_TTL
            ):
                return
            try:
                await self.refresh_servers()
                self._servers_refreshed_at = time.monotonic()
            except CraftyUnavailable as exc:
                if not self.registry.servers:
                    log.error("Server auto-detection failed and no list is cached: %s", exc)
                    raise
                log.warning(
                    "Server auto-detection refresh failed; keeping %d cached server(s): %s",
                    len(self.registry.servers),
                    exc,
                )

    async def refresh_servers(self) -> None:
        """Rebuild the registry from Crafty's live server list."""
        crafty_servers = await self.crafty.list_servers()
        configs = build_auto_configs(crafty_servers, self.settings.mod_role_ids)
        if [s.label for s in configs] != [s.label for s in self.registry.servers]:
            log.info("Auto-detected %d server(s): %s", len(configs), [s.label for s in configs])
        self.registry.update(configs)

    async def get_server(self, label: str) -> ServerConfig:
        """Resolve a server label, refreshing the auto-detected list first if stale."""
        await self.ensure_fresh_servers()
        return self.registry.get(label)

    async def close(self) -> None:
        await self.crafty.close()
        await self.mojang.close()
        await self.db.close()
        await super().close()

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        message = await self._describe_error(error)
        if message is None:
            log.exception("Unhandled command error", exc_info=error)
            message = "❌ Something went wrong. Try again, or ping an admin if it keeps failing."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            log.exception("Failed to deliver error message")

    async def _describe_error(self, error: app_commands.AppCommandError) -> str | None:
        if isinstance(error, app_commands.CommandInvokeError):
            original = error.original
            if isinstance(original, app_commands.AppCommandError):
                error = original

        match error:
            case PermissionDenied(server=server):
                target = f" manage **{server.label}**" if server else " do that"
                return f"⛔ You don't have permission to{target}."
            case ServerNotFound(label=label):
                return f"❓ Unknown server **{label}** — pick one from the autocomplete list."
            case NotLinkedError():
                return "🔗 Link your Minecraft username first with `/mc link`, then try again."
            case InvalidUsername(username=username):
                return (
                    f"❌ **{username}** is not a valid Minecraft username "
                    "(3–16 characters: letters, digits, underscore)."
                )
            case UsernameNotFound(username=username):
                return f"❌ No Minecraft account named **{username}** exists."
            case MojangRateLimited():
                return "⏳ Mojang API rate limit hit — try again in a minute."
            case ConsoleUnavailable(server=server):
                return await self._describe_console_error(server)
            case CraftyUnavailable():
                return (
                    "🔌 Crafty Controller is unreachable — server management is temporarily down."
                )
            case app_commands.NoPrivateMessage():
                return "🏠 This command only works inside a server."
            case app_commands.CheckFailure():
                return "⛔ You don't have permission to do that."
            case _:
                return None

    async def _describe_console_error(self, server: ServerConfig) -> str:
        try:
            stats = await self.crafty.get_stats(server.crafty_id)
            if not stats.running:
                return (
                    f"💤 **{server.label}** is stopped — a mod can start it with "
                    f"`/mc server start`."
                )
        except CraftyUnavailable:
            pass
        return (
            f"🔌 Couldn't reach the console of **{server.label}**. "
            "Try again shortly or ping an admin."
        )
