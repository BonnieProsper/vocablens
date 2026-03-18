from vocablens.infrastructure.jobs.celery_app import celery_app
from vocablens.infrastructure.db.session import AsyncSessionMaker
from vocablens.infrastructure.postgres_embedding_repository import PostgresEmbeddingRepository
from vocablens.services.embedding_service import EmbeddingService
from vocablens.infrastructure.logging.logger import get_logger
from vocablens.infrastructure.observability.token_tracker import start_request, get_tokens
import asyncio

logger = get_logger("jobs.embedding")


@celery_app.task(
    bind=True,
    name="jobs.generate_embedding",
    soft_time_limit=20,
    time_limit=30,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def generate_embedding(self, word: str, user_id: int | None = None):
    async def _run():
        start_request()
        repo = PostgresEmbeddingRepository(AsyncSessionMaker)
        service = EmbeddingService(repo)
        vector = await service.embed(word)
        await service.store_embedding(word, vector)
        if user_id is not None:
            from vocablens.infrastructure.unit_of_work import UnitOfWorkFactory

            factory = UnitOfWorkFactory(AsyncSessionMaker)
            async with factory() as uow:
                await uow.usage_logs.log(
                    user_id=user_id,
                    endpoint="job:generate_embedding",
                    tokens=get_tokens(),
                    success=True,
                )
                await uow.commit()

    asyncio.run(_run())
    logger.info(
        "embedding_generated",
        extra={
            "word": word,
            "tokens_used": get_tokens(),
        },
    )
