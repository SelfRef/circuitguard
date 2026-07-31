from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class ServerConfig(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    crafty_id: str
    rcon_host: str | None = None
    rcon_port: int = 25575
    rcon_password: SecretStr | None = None
    mod_role_ids: list[int] = Field(default_factory=list)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_token: SecretStr
    discord_guild_id: int | None = None
    admin_role_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    # Applied to every auto-detected server; ignored when MC_SERVERS is set
    # (there, each server carries its own mod_role_ids).
    mod_role_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    crafty_url: HttpUrl
    crafty_api_token: SecretStr
    crafty_verify_ssl: bool = True

    # "rcon" talks to each server's RCON port; "crafty" goes through the Crafty
    # API only (stdin + log scraping) so no RCON ports need to be reachable.
    console_backend: Literal["rcon", "crafty"] = "rcon"

    # Optional: when empty, servers are auto-detected from Crafty instead
    # (requires CONSOLE_BACKEND=crafty).
    servers: list[ServerConfig] = Field(default_factory=list, validation_alias="MC_SERVERS")

    db_path: Path = Path("/data/circuitguard.db")
    log_level: str = "INFO"

    @field_validator("admin_role_ids", "mod_role_ids", mode="before")
    @classmethod
    def _split_role_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def _check_unique_servers(self) -> "Settings":
        labels = [server.label.casefold() for server in self.servers]
        if len(set(labels)) != len(labels):
            raise ValueError("MC_SERVERS contains duplicate labels")
        crafty_ids = [server.crafty_id for server in self.servers]
        if len(set(crafty_ids)) != len(crafty_ids):
            raise ValueError("MC_SERVERS contains duplicate crafty_ids")
        return self

    @model_validator(mode="after")
    def _check_rcon_config(self) -> "Settings":
        if not self.servers and self.console_backend == "rcon":
            raise ValueError(
                "MC_SERVERS is empty, so servers will be auto-detected from Crafty — "
                "that requires CONSOLE_BACKEND=crafty (RCON details cannot be auto-detected)"
            )
        if self.console_backend == "rcon":
            missing = [
                server.label
                for server in self.servers
                if server.rcon_host is None or server.rcon_password is None
            ]
            if missing:
                raise ValueError(
                    "CONSOLE_BACKEND=rcon requires rcon_host and rcon_password for: "
                    + ", ".join(missing)
                )
        return self
