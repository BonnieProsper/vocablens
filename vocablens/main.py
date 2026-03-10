from pathlib import Path
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from vocablens.infrastructure.database import init_db
from vocablens.infrastructure.repositories import SQLiteVocabularyRepository
from vocablens.infrastructure.repositories_users import SQLiteUserRepository
from vocablens.infrastructure.repositories_translation_cache import (
    SQLiteTranslationCacheRepository,
)

from vocablens.providers.translation.libretranslate_provider import LibreTranslateProvider
from vocablens.providers.ocr.pytesseract_provider import PyTesseractProvider
from vocablens.providers.llm.openai_provider import OpenAIProvider

from vocablens.services.vocabulary_service import VocabularyService
from vocablens.services.ocr_service import OCRService
from vocablens.services.cached_translator import CachedTranslator
from vocablens.services.word_extraction_service import WordExtractionService
from vocablens.services.conversation_service import ConversationService
from vocablens.services.learning_graph_service import LearningGraphService
from vocablens.services.lesson_generation_service import LessonGenerationService
from vocablens.services.scenario_service import ScenarioService

from vocablens.api.routes import create_routes

from vocablens.domain.errors import TranslationError, PersistenceError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("vocablens")


def create_app() -> FastAPI:

    app = FastAPI(title="VocabLens API", version="1.0.0")

    db_path = Path("vocablens.db")

    vocab_repo = SQLiteVocabularyRepository(db_path)
    user_repo = SQLiteUserRepository(db_path)
    cache_repo = SQLiteTranslationCacheRepository(str(db_path))

    translator_provider = LibreTranslateProvider()
    ocr_provider = PyTesseractProvider()
    llm_provider = OpenAIProvider()

    translator = CachedTranslator(
        provider=translator_provider,
        cache_repo=cache_repo,
    )

    extractor = WordExtractionService()

    vocab_service = VocabularyService(
        translator,
        vocab_repo,
        extractor,
    )

    ocr_service = OCRService(ocr_provider)

    conversation_service = ConversationService(
        llm_provider,
        vocab_repo,
    )

    graph_service = LearningGraphService(vocab_repo)

    lesson_service = LessonGenerationService(
        llm_provider,
        graph_service,
    )

    scenario_service = ScenarioService(llm_provider)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        logger.info(
            "%s %s -> %s (%.3fs)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )

        return response

    @app.get("/health", tags=["System"])
    def health():
        return {"status": "ok"}

    @app.on_event("startup")
    async def startup():
        init_db(db_path)
        logger.info("Database initialized")

    app.include_router(
        create_routes(
            vocab_service,
            ocr_service,
            user_repo,
            conversation_service,
            lesson_service,
            scenario_service,
        )
    )

    return app


app = create_app()