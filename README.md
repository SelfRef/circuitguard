# CircuitGuard

Discord bot for managing Minecraft servers running under [Crafty Controller](https://craftycontrol.com/). Server status comes from the Crafty API, lifecycle actions (start/stop/restart/backup) go through Crafty, and game commands (whitelist, custom console commands) go through a configurable console backend: RCON directly to each server, or the Crafty API alone (no RCON ports needed).

## Commands

Commands are split into two top-level groups: `/mc` for everyone, and `/mcmod` for moderation. `/mcmod` is hidden from members without the **Manage Server** permission by default — to make it visible to your mod roles instead, grant them access in **Server Settings → Integrations → CircuitGuard → /mcmod**. Visibility is cosmetic; the bot enforces the configured role IDs at runtime either way.

| Command | Who | What |
|---|---|---|
| `/mc servers` | everyone | Status, version and online players for all servers |
| `/mc whitelist me server: [username:]` | everyone | Whitelist yourself — provide `username` the first time (validated against Mojang) and it's remembered for next time |
| `/mc whitelist list server:` | everyone | Show the whitelist (ephemeral) |
| `/mcmod whitelist add server: player:` | mod | Add any player to the whitelist |
| `/mcmod whitelist remove server: player:` | mod | Remove a player from the whitelist |
| `/mcmod server start\|stop\|restart server:` | mod | Power actions via Crafty |
| `/mcmod server backup server:` | mod | Trigger a Crafty backup |
| `/mcmod server command server: command:` | mod | Run any console command (response is ephemeral, everything is audit-logged) |
| `/mcmod server gamerule server: rule: [value:]` | mod | Read a gamerule (omit `value`) or set it — rule names and boolean values autocomplete |
| `/mcmod op add server: player:` | mod | Grant operator status — `player` autocompletes from the server's whitelist |
| `/mcmod op remove server: player:` | mod | Revoke operator status — `player` autocompletes from the current operators |
| `/mcmod op list server:` | mod | Show a server's operators with their permission levels (read from `ops.json` via the Crafty file API) |

Permissions: users with a role listed in `ADMIN_ROLE_IDS` can do everything on every server. Each server's `mod_role_ids` (or the global `MOD_ROLE_IDS` for auto-detected servers) grants mod access. Everyone else can view status and whitelist their own single remembered username.

All state-changing actions are recorded in an audit log (SQLite, `/data`).

## Setup

### 1. Discord application

1. Create an application at <https://discord.com/developers/applications>, add a **Bot**.
2. No privileged intents are needed (slash commands only).
3. Copy the bot token → `DISCORD_TOKEN`.
4. Invite it with the `bot` + `applications.commands` scopes:
   `https://discord.com/oauth2/authorize?client_id=<APP_ID>&scope=bot+applications.commands`
5. Optionally set `DISCORD_GUILD_ID` to your guild ID — commands then sync instantly instead of taking up to an hour globally.

### 2. Crafty Controller

1. In Crafty, create an API token for a user that can view servers and send commands → `CRAFTY_API_TOKEN`.
2. `CRAFTY_URL` is the base URL of your Crafty instance. Set `CRAFTY_VERIFY_SSL=false` for self-signed certificates.
3. Find each server's UUID (Crafty UI or `GET /api/v2/servers`) → `crafty_id` in `MC_SERVERS`.

### 3. Console backend

Game commands (whitelist, `/mc server command`) need console access to each server. Pick one of two backends via `CONSOLE_BACKEND`:

**`rcon` (default)** — talks to each server's RCON port. Responses are immediate and exact, but every RCON port must be reachable from the bot container. In each server's `server.properties`:

```properties
enable-rcon=true
rcon.port=25575
rcon.password=<strong password>
```

The RCON port must be reachable from the bot container (same Docker network or exposed port). **Never expose RCON to the internet.**

**`crafty`** — everything goes through the Crafty API: commands are written to the server's stdin and the response is scraped from the console log. No RCON ports, passwords, or extra network exposure — the bot only needs to reach Crafty. The trade-off is that log scraping is best effort: responses take up to a second, and on a busy server unrelated console output (chat, join messages) can occasionally be mixed into the captured response. The Crafty API token must belong to a user allowed to send commands and read logs on every managed server.

### 4. Configuration

Copy [.env.example](.env.example) to `.env` and fill it in.

**Auto-detection (recommended with `CONSOLE_BACKEND=crafty`):** omit `MC_SERVERS` and the bot manages every server visible to the Crafty API token. The list is fetched on demand — before a command runs (or autocomplete fires) it is refreshed if older than 10 minutes — so servers added, removed, or renamed in Crafty show up without a restart and without polling Crafty in the background. `MOD_ROLE_IDS` (optional, comma-separated) grants mod access to all auto-detected servers; without it, only `ADMIN_ROLE_IDS` can manage them. Auto-detection requires the Crafty console backend, because RCON credentials can't be discovered through the API.

**Manual:** set `MC_SERVERS` to a JSON array defining every managed server (required when `CONSOLE_BACKEND=rcon`):

```json
[
  {
    "label": "Survival",
    "crafty_id": "a1b2c3d4-...",
    "rcon_host": "mc-survival",
    "rcon_port": 25575,
    "rcon_password": "secret",
    "mod_role_ids": [333333333333333333]
  }
]
```

With `CONSOLE_BACKEND=crafty` the `rcon_*` fields can be omitted entirely.

The bot validates the whole configuration at startup and refuses to boot on errors (duplicate labels, missing fields, bad JSON).

### 5. Deploy

```sh
docker compose up -d
```

The image is published to `ghcr.io/selfref/circuitguard` by GitHub Actions. Pushing `master` to the `release` branch triggers a build (VSCode task **Release: replace release branch with master**, or `git push origin master:release --force-with-lease`). The SQLite database lives in the `circuitguard-data` volume.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync              # install deps
uv run python -m circuitguard   # run the bot (reads .env)
uv run pytest        # tests
uv run ruff check . && uv run mypy   # lint + typecheck
```

VSCode tasks exist for all of the above (`Terminal → Run Task`).
