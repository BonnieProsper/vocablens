from vocablens.infrastructure.jobs.celery_app import celery_app
from vocablens.infrastructure.db.session import AsyncSessionMaker
from vocablens.infrastructure.postgres_embedding_repository import PostgresEmbeddingRepository
from vocablens.services.embedding_service import EmbeddingService
from vocablens.infrastructure.logging.logger import get_logger
from vocablens.infrastructure.observability.token_tracker import start_request, get_tokens

logger = get_logger("jobs.embedding")


@celery_app.task(name="jobs.generate_embedding", soft_time_limit=20, time_limit=30, max_retries=3, default_retry_delay=10)
def generate_embedding(word: str):
    start_request()
    repo = PostgresEmbeddingRepository(AsyncSessionMaker)
    service = EmbeddingService(repo)
    vector = service.embed(word)
    service.store_embedding(word, vector)
    logger.info(
        "embedding_generated",
        extra={
            "word": word,
            "tokens_used": get_tokens(),
        },
    )
