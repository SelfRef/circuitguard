from collections.abc import Callable, Iterable
from typing import TypeVar

import discord
from discord import app_commands

from circuitguard.config import ServerConfig, Settings
from circuitguard.errors import PermissionDenied

T = TypeVar("T")


def is_admin(role_ids: Iterable[int], settings: Settings) -> bool:
    return bool(set(role_ids) & set(settings.admin_role_ids))


def is_mod_for(role_ids: Iterable[int], server: ServerConfig, settings: Settings) -> bool:
    ids = set(role_ids)
    return bool(ids & set(settings.admin_role_ids)) or bool(ids & set(server.mod_role_ids))


def member_role_ids(user: discord.User | discord.Member) -> set[int]:
    if isinstance(user, discord.Member):
        return {role.id for role in user.roles}
    return set()


def require_mod_of_target_server() -> Callable[[T], T]:
    """Check factory: caller must be admin or mod of the server named in the
    command's `server` option. Runs before parameter transformation, so the raw
    option value is read from interaction.namespace.
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        from circuitguard.bot import CircuitGuardBot

        assert isinstance(interaction.client, CircuitGuardBot)
        bot = interaction.client
        label = str(interaction.namespace.server)
        server = await bot.get_server(label)  # raises ServerNotFound
        if not is_mod_for(member_role_ids(interaction.user), server, bot.settings):
            raise PermissionDenied(server)
        return True

    return app_commands.check(predicate)
