from discord import app_commands

from circuitguard.config import ServerConfig


class CircuitGuardError(app_commands.AppCommandError):
    """Base for domain errors so they flow through the app-command error funnel."""


class PermissionDenied(CircuitGuardError):
    def __init__(self, server: ServerConfig | None = None) -> None:
        self.server = server
        super().__init__("Permission denied")


class ServerNotFound(CircuitGuardError):
    def __init__(self, label: str) -> None:
        self.label = label
        super().__init__(f"Unknown server: {label}")


class NotLinkedError(CircuitGuardError):
    pass


class UsernameNotFound(CircuitGuardError):
    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"Minecraft account not found: {username}")


class InvalidUsername(CircuitGuardError):
    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"Invalid Minecraft username: {username}")


class MojangRateLimited(CircuitGuardError):
    pass


class CraftyUnavailable(CircuitGuardError):
    pass


class ConsoleUnavailable(CircuitGuardError):
    def __init__(self, server: ServerConfig) -> None:
        self.server = server
        super().__init__(f"Console unreachable for {server.label}")
