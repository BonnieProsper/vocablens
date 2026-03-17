from vocablens.infrastructure.jobs.celery_app import celery_app
from vocablens.infrastructure.db.session import AsyncSessionMaker
from vocablens.infrastructure.postgres_embedding_repository import PostgresEmbeddingRepository
from vocablens.services.embedding_service import EmbeddingService
from vocablens.infrastructure.logging.logger import get_logger

logger = get_logger("jobs.embedding")


@celery_app.task(name="jobs.generate_embedding")
def generate_embedding(word: str):
    repo = PostgresEmbeddingRepository(AsyncSessionMaker)
    service = EmbeddingService(repo)
    vector = service.embed(word)
    service.store_embedding(word, vector)
    logger.info("embedding_generated", extra={"word": word})
