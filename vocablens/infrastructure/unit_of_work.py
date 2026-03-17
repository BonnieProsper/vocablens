from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vocablens.infrastructure.postgres_vocabulary_repository import PostgresVocabularyRepository
from vocablens.infrastructure.postgres_translation_cache_repository import PostgresTranslationCacheRepository
from vocablens.infrastructure.postgres_conversation_repository import PostgresConversationRepository
from vocablens.infrastructure.postgres_learning_event_repository import PostgresLearningEventRepository
from vocablens.infrastructure.postgres_skill_tracking_repository import PostgresSkillTrackingRepository
from vocablens.infrastructure.postgres_user_repository import PostgresUserRepository
from vocablens.infrastructure.knowledge_graph_repository import KnowledgeGraphRepository


class UnitOfWork:
    """
    Coordinates a shared AsyncSession and repositories in a single transaction.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self.session: Optional[AsyncSession] = None
        self._committed = False
        self._vocab: Optional[PostgresVocabularyRepository] = None
        self._cache: Optional[PostgresTranslationCacheRepository] = None
        self._conversation: Optional[PostgresConversationRepository] = None
        self._learning_events: Optional[PostgresLearningEventRepository] = None
        self._skill_tracking: Optional[PostgresSkillTrackingRepository] = None
        self._users: Optional[PostgresUserRepository] = None
        self._knowledge_graph: Optional[KnowledgeGraphRepository] = None

    async def __aenter__(self):
        self.session = self._session_factory()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if not self.session:
            return
        if exc:
            await self.session.rollback()
        elif not self._committed:
            await self.session.rollback()
        await self.session.close()

    async def commit(self):
        if self.session:
            await self.session.commit()
            self._committed = True

    # Repository accessors (lazy, shared session)
    @property
    def vocab(self) -> PostgresVocabularyRepository:
        if not self.session:
            raise RuntimeError("UnitOfWork session not initialized")
        if self._vocab is None:
            self._vocab = PostgresVocabularyRepository(self.session)
        return self._vocab

    @property
    def translation_cache(self) -> PostgresTranslationCacheRepository:
        if not self.session:
            raise RuntimeError("UnitOfWork session not initialized")
        if self._cache is None:
            self._cache = PostgresTranslationCacheRepository(self.session)
        return self._cache

    @property
    def conversation(self) -> PostgresConversationRepository:
        if not self.session:
            raise RuntimeError("UnitOfWork session not initialized")
        if self._conversation is None:
            self._conversation = PostgresConversationRepository(self.session)
        return self._conversation

    @property
    def learning_events(self) -> PostgresLearningEventRepository:
        if not self.session:
            raise RuntimeError("UnitOfWork session not initialized")
        if self._learning_events is None:
            self._learning_events = PostgresLearningEventRepository(self.session)
        return self._learning_events

    @property
    def skill_tracking(self) -> PostgresSkillTrackingRepository:
        if not self.session:
            raise RuntimeError("UnitOfWork session not initialized")
        if self._skill_tracking is None:
            self._skill_tracking = PostgresSkillTrackingRepository(self.session)
        return self._skill_tracking

    @property
    def users(self) -> PostgresUserRepository:
        if not self.session:
            raise RuntimeError("UnitOfWork session not initialized")
        if self._users is None:
            self._users = PostgresUserRepository(self.session)
        return self._users

    @property
    def knowledge_graph(self) -> KnowledgeGraphRepository:
        if not self.session:
            raise RuntimeError("UnitOfWork session not initialized")
        if self._knowledge_graph is None:
            self._knowledge_graph = KnowledgeGraphRepository(self.session)
        return self._knowledge_graph


def UnitOfWorkFactory(session_factory: async_sessionmaker[AsyncSession]):
    def _factory():
        return UnitOfWork(session_factory)

    return _factory
