import logging
from pathlib import Path
from types import TracebackType

import aiosqlite

log = logging.getLogger(__name__)

MIGRATIONS: list[str] = [
    """
    CREATE TABLE users (
        discord_user_id INTEGER PRIMARY KEY,
        mc_username     TEXT NOT NULL,
        mc_uuid         TEXT NOT NULL,
        linked_at       TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT
    );

    CREATE TABLE audit_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        at              TEXT NOT NULL DEFAULT (datetime('now')),
        discord_user_id INTEGER NOT NULL,
        action          TEXT NOT NULL,
        server_label    TEXT,
        target          TEXT,
        success         INTEGER NOT NULL,
        detail          TEXT
    );
    CREATE INDEX idx_audit_at ON audit_log(at);
    """,
]


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._migrate()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _migrate(self) -> None:
        async with self.conn.execute("PRAGMA user_version") as cursor:
            row = await cursor.fetchone()
            version = row[0] if row else 0
        for index, migration in enumerate(MIGRATIONS[version:], start=version + 1):
            log.info("Applying database migration %d", index)
            await self.conn.executescript(migration)
            await self.conn.execute(f"PRAGMA user_version = {index}")
        await self.conn.commit()

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()
