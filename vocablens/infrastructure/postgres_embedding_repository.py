from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vocablens.infrastructure.db.models import EmbeddingORM


class PostgresEmbeddingRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def store(self, word: str, embedding: List[float]) -> None:
        async with self._session_factory() as session:
            await session.execute(
                insert(EmbeddingORM)
                .values(word=word, embedding=embedding)
                .on_conflict_do_update(
                    index_elements=[EmbeddingORM.word],
                    set_={"embedding": embedding},
                )
            )
            await session.commit()

    async def get(self, word: str) -> Optional[List[float]]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EmbeddingORM.embedding).where(EmbeddingORM.word == word)
            )
            return result.scalar_one_or_none()
