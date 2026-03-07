import sqlite3


class SQLiteTranslationCacheRepository:

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, text: str, source: str, target: str):
        cur = self.conn.execute(
            """
            SELECT translation
            FROM translation_cache
            WHERE text=? AND source_lang=? AND target_lang=?
            """,
            (text, source, target),
        )

        row = cur.fetchone()
        return row[0] if row else None

    def save(self, text: str, source: str, target: str, translation: str):
        self.conn.execute(
            """
            INSERT OR REPLACE INTO translation_cache
            (text, source_lang, target_lang, translation)
            VALUES (?, ?, ?, ?)
            """,
            (text, source, target, translation),
        )