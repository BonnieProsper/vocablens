from datetime import datetime
from pathlib import Path
import sqlite3

from vocablens.domain.user import User
from vocablens.domain.errors import PersistenceError


class SQLiteUserRepository:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def create(self, email: str, password_hash: str) -> User:
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users (email, password_hash, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (email, password_hash, datetime.utcnow().isoformat()),
                )

                user_id = cursor.lastrowid
                row = conn.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()

                return self._row_to_domain(row)

        except sqlite3.IntegrityError:
            raise ValueError("Email already registered")
        except sqlite3.Error as exc:
            raise PersistenceError(str(exc)) from exc

    def get_by_email(self, email: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            ).fetchone()

            return self._row_to_domain(row) if row else None

    def get_by_id(self, user_id: int) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

            return self._row_to_domain(row) if row else None

    def _row_to_domain(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )