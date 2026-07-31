from dataclasses import dataclass

from circuitguard.db.database import Database


@dataclass(frozen=True)
class LinkedUser:
    discord_user_id: int
    mc_username: str
    mc_uuid: str


class UserRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get(self, discord_user_id: int) -> LinkedUser | None:
        async with self._db.conn.execute(
            "SELECT discord_user_id, mc_username, mc_uuid FROM users WHERE discord_user_id = ?",
            (discord_user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return LinkedUser(row["discord_user_id"], row["mc_username"], row["mc_uuid"])

    async def upsert_link(self, discord_user_id: int, mc_username: str, mc_uuid: str) -> None:
        await self._db.conn.execute(
            """
            INSERT INTO users (discord_user_id, mc_username, mc_uuid)
            VALUES (?, ?, ?)
            ON CONFLICT (discord_user_id) DO UPDATE SET
                mc_username = excluded.mc_username,
                mc_uuid = excluded.mc_uuid,
                updated_at = datetime('now')
            """,
            (discord_user_id, mc_username, mc_uuid),
        )
        await self._db.conn.commit()


class AuditRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def record(
        self,
        discord_user_id: int,
        action: str,
        *,
        server_label: str | None = None,
        target: str | None = None,
        success: bool,
        detail: str | None = None,
    ) -> None:
        await self._db.conn.execute(
            """
            INSERT INTO audit_log (discord_user_id, action, server_label, target, success, detail)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (discord_user_id, action, server_label, target, int(success), detail),
        )
        await self._db.conn.commit()
