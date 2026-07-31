import asyncio
import logging

import aiomcrcon

from circuitguard.config import ServerConfig
from circuitguard.errors import ConsoleUnavailable

log = logging.getLogger(__name__)

RCON_TIMEOUT = 5.0


class RconService:
    async def execute(self, server: ServerConfig, command: str) -> str:
        """Run a console command on the server and return its response."""
        if server.rcon_host is None or server.rcon_password is None:
            log.error("Server %s has no RCON configuration", server.label)
            raise ConsoleUnavailable(server)
        try:
            async with asyncio.timeout(RCON_TIMEOUT):
                client = aiomcrcon.Client(
                    server.rcon_host, server.rcon_port, server.rcon_password.get_secret_value()
                )
                try:
                    await client.connect()
                    response, _ = await client.send_cmd(command)
                    return str(response).strip()
                finally:
                    await client.close()
        except (TimeoutError, OSError, aiomcrcon.RCONConnectionError) as exc:
            log.warning("RCON failed for %s: %s", server.label, exc)
            raise ConsoleUnavailable(server) from exc
        except aiomcrcon.IncorrectPasswordError as exc:
            log.error("RCON password rejected for %s", server.label)
            raise ConsoleUnavailable(server) from exc
