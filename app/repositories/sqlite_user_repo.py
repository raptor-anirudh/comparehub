"""SQLite implementation of UserRepository."""

from __future__ import annotations

import aiosqlite
import json
from app.domain.users.models import User, UserPreferences, UserId
from app.repositories.base import UserRepository

class SQLiteUserRepository(UserRepository):
    """Persistence layer using SQLite.

    Stored in a file-based DB. Preferences are stored as a JSON blob for flexibility,
    though they could be normalized into a separate table if they grow complex.
    """

    def __init__(self, db_path: str = "comparehub.db") -> None:
        self._db_path = db_path

    async def init_db(self) -> None:
        """Initialize the database schema."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    email TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    preferred_provider_ids TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """
            )
            await db.commit()

    async def create_user(self, username: str, email: str | None = None) -> User:
        import uuid
        user_id = str(uuid.uuid4())
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO users (id, username, email) VALUES (?, ?, ?)",
                (user_id, username, email),
            )
            await db.commit()
            return User(id=user_id, username=username, email=email)

    async def get_user(self, user_id: UserId) -> User | None:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(id=row[0], username=row[1], email=row[2])
                return None

    async def get_preferences(self, user_id: UserId) -> UserPreferences:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT preferred_provider_ids FROM user_preferences WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    ids = json.loads(row[0])
                    return UserPreferences(preferred_provider_ids=frozenset(ids))
                return UserPreferences()

    async def update_preferences(self, user_id: UserId, preferences: UserPreferences) -> None:
        ids_json = json.dumps(list(preferences.preferred_provider_ids))
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO user_preferences (user_id, preferred_provider_ids)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET preferred_provider_ids = excluded.preferred_provider_ids
                """,
                (user_id, ids_json),
            )
            await db.commit()
