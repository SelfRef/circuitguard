import discord
from discord import app_commands

from circuitguard.config import ServerConfig
from circuitguard.errors import ServerNotFound
from circuitguard.services.crafty import CraftyServer

# ServerConfig.label allows 100 chars (also Discord's choice-name limit); leave
# room for a " (12345678)" disambiguation suffix.
MAX_BASE_LABEL = 88


def build_auto_configs(
    crafty_servers: list[CraftyServer], mod_role_ids: list[int]
) -> list[ServerConfig]:
    """Turn Crafty's server list into ServerConfigs (no RCON — Crafty console only).

    Labels come from Crafty server names; duplicates get a short server-id
    suffix so registry lookups stay unambiguous.
    """
    configs: list[ServerConfig] = []
    seen: set[str] = set()
    for server in crafty_servers:
        label = server.name.strip()[:MAX_BASE_LABEL] or server.server_id[:8]
        if label.casefold() in seen:
            label = f"{label} ({server.server_id[:8]})"
        seen.add(label.casefold())
        configs.append(
            ServerConfig(label=label, crafty_id=server.server_id, mod_role_ids=mod_role_ids)
        )
    return configs


class ServerRegistry:
    def __init__(self, servers: list[ServerConfig]) -> None:
        self.servers: list[ServerConfig] = []
        self._by_label: dict[str, ServerConfig] = {}
        self.update(servers)

    def update(self, servers: list[ServerConfig]) -> None:
        self._by_label = {server.label.casefold(): server for server in servers}
        self.servers = servers

    def get(self, label: str) -> ServerConfig:
        server = self._by_label.get(label.casefold())
        if server is None:
            raise ServerNotFound(label)
        return server

    async def autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        needle = current.casefold()
        return [
            app_commands.Choice(name=server.label, value=server.label)
            for server in self.servers
            if needle in server.label.casefold()
        ][:25]
