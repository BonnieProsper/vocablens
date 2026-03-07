import sqlite3
from typing import Optional


class SQLiteTranslationCacheRepository:

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def get(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> Optional[str]:

        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT translation
                FROM translation_cache
                WHERE text = ?
                AND source_lang = ?
                AND target_lang = ?
                """,
                (text, source_lang, target_lang),
            )

            row = cur.fetchone()

        return row[0] if row else None

    def save(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        translation: str,
    ) -> None:

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO translation_cache
                (text, source_lang, target_lang, translation)
                VALUES (?, ?, ?, ?)
                """,
                (text, source_lang, target_lang, translation),
            )