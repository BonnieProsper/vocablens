import inspect
from pathlib import Path

from vocablens.infrastructure.postgres_conversation_repository import PostgresConversationRepository
from vocablens.infrastructure.postgres_embedding_repository import PostgresEmbeddingRepository
from vocablens.infrastructure.postgres_learning_event_repository import PostgresLearningEventRepository
from vocablens.infrastructure.postgres_skill_tracking_repository import PostgresSkillTrackingRepository
from vocablens.infrastructure.postgres_translation_cache_repository import PostgresTranslationCacheRepository
from vocablens.infrastructure.postgres_user_repository import PostgresUserRepository
from vocablens.infrastructure.postgres_vocabulary_repository import PostgresVocabularyRepository
from vocablens.providers.llm.openai_provider import OpenAIProvider
from vocablens.providers.speech.tts_provider import TextToSpeechProvider
from vocablens.providers.speech.whisper_provider import WhisperProvider
from vocablens.providers.translation.libretranslate_provider import LibreTranslateProvider
from vocablens.services.cached_translator import CachedTranslator
from vocablens.services.conversation_service import ConversationService
from vocablens.services.drill_generation_service import DrillGenerationService
from vocablens.services.embedding_service import EmbeddingService
from vocablens.services.example_sentence_service import ExampleSentenceService
from vocablens.services.grammar_service import GrammarExplanationService
from vocablens.services.lesson_generation_service import LessonGenerationService
from vocablens.services.mistake_engine import MistakeEngine
from vocablens.services.review_service import ReviewService
from vocablens.services.scenario_service import ScenarioService
from vocablens.services.semantic_cluster_service import SemanticClusterService
from vocablens.services.speech_conversation_service import SpeechConversationService
from vocablens.services.vocabulary_service import VocabularyService


ROOT = Path(__file__).resolve().parents[1] / "vocablens"


def test_no_anyio_run_usage_in_codebase():
    offenders = []
    for path in ROOT.rglob("*.py"):
        if "anyio.run" in path.read_text(encoding="utf-8"):
            offenders.append(path)
    assert not offenders, offenders


def test_async_service_methods():
    expected_async = {
        CachedTranslator: ["translate", "translate_batch", "close"],
        ConversationService: ["generate_reply"],
        DrillGenerationService: ["generate_drills"],
        EmbeddingService: ["embed", "store_embedding"],
        ExampleSentenceService: ["generate_example"],
        GrammarExplanationService: ["explain"],
        LessonGenerationService: ["generate_lesson"],
        MistakeEngine: ["analyze"],
        ReviewService: ["due_reviews"],
        ScenarioService: ["start_scenario"],
        SemanticClusterService: ["cluster_word"],
        SpeechConversationService: ["process_audio"],
        VocabularyService: [
            "process_text",
            "process_ocr_text",
            "process_vocabulary_batch",
            "review_item",
            "review_session",
            "list_vocabulary",
            "list_due_items",
        ],
        OpenAIProvider: ["generate", "generate_json", "generate_with_usage", "generate_json_with_usage"],
        LibreTranslateProvider: ["translate", "translate_batch", "close"],
        WhisperProvider: ["transcribe"],
        TextToSpeechProvider: ["synthesize"],
    }

    for cls, method_names in expected_async.items():
        for method_name in method_names:
            method = getattr(cls, method_name)
            assert inspect.iscoroutinefunction(method), f"{cls.__name__}.{method_name} must be async"


def test_repositories_are_async_session_based():
    repos = [
        PostgresConversationRepository,
        PostgresEmbeddingRepository,
        PostgresLearningEventRepository,
        PostgresSkillTrackingRepository,
        PostgresTranslationCacheRepository,
        PostgresUserRepository,
        PostgresVocabularyRepository,
    ]
    for repo in repos:
        annotations = getattr(repo.__init__, "__annotations__", {})
        assert annotations, f"{repo.__name__}.__init__ should be typed for async session usage"
        annotation_values = " ".join(str(value) for value in annotations.values())
        assert "AsyncSession" in annotation_values or "async_sessionmaker" in annotation_values
