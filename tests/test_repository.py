from pathlib import Path

import pytest

from circuitguard.db.database import Database
from circuitguard.db.repository import AuditRepository, UserRepository


@pytest.fixture
async def db(tmp_path: Path):  # type: ignore[no-untyped-def]
    async with Database(tmp_path / "test.db") as database:
        yield database


async def test_migrations_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    async with Database(path):
        pass
    async with Database(path) as db:
        async with db.conn.execute("PRAGMA user_version") as cursor:
            row = await cursor.fetchone()
        assert row is not None and row[0] == 1


async def test_get_missing_user_returns_none(db: Database) -> None:
    assert await UserRepository(db).get(1) is None


async def test_upsert_overwrites(db: Database) -> None:
    repo = UserRepository(db)
    await repo.upsert_link(1, "Steve", "uuid-1")
    await repo.upsert_link(1, "Alex", "uuid-2")

    user = await repo.get(1)
    assert user is not None
    assert user.mc_username == "Alex"
    assert user.mc_uuid == "uuid-2"

    async with db.conn.execute("SELECT COUNT(*) FROM users") as cursor:
        row = await cursor.fetchone()
    assert row is not None and row[0] == 1


async def test_audit_rows_persist(db: Database) -> None:
    audit = AuditRepository(db)
    await audit.record(1, "whitelist_add", server_label="Survival", target="Steve", success=True)
    await audit.record(2, "stop", server_label="Creative", success=False, detail="denied")

    async with db.conn.execute(
        "SELECT discord_user_id, action, server_label, target, success, detail "
        "FROM audit_log ORDER BY id"
    ) as cursor:
        rows = await cursor.fetchall()

    assert len(rows) == 2
    assert rows[0]["action"] == "whitelist_add"
    assert rows[0]["success"] == 1
    assert rows[1]["detail"] == "denied"
    assert rows[1]["success"] == 0
