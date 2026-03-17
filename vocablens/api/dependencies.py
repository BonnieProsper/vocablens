from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from vocablens.auth.jwt import decode_token
from vocablens.domain.user import User
from vocablens.infrastructure.db.session import AsyncSessionMaker
from vocablens.infrastructure.postgres_user_repository import PostgresUserRepository
from vocablens.infrastructure.postgres_vocabulary_repository import PostgresVocabularyRepository
from vocablens.infrastructure.postgres_conversation_repository import PostgresConversationRepository
from vocablens.infrastructure.postgres_translation_cache_repository import PostgresTranslationCacheRepository
from vocablens.infrastructure.postgres_learning_event_repository import PostgresLearningEventRepository
from vocablens.infrastructure.postgres_skill_tracking_repository import PostgresSkillTrackingRepository
from vocablens.infrastructure.knowledge_graph_repository import KnowledgeGraphRepository
from vocablens.providers.translation.libretranslate_provider import LibreTranslateProvider
from vocablens.providers.llm.openai_provider import OpenAIProvider
from vocablens.services.vocabulary_service import VocabularyService
from vocablens.services.conversation_service import ConversationService
from vocablens.services.conversation_memory_service import ConversationMemoryService
from vocablens.services.conversation_vocab_service import ConversationVocabularyService
from vocablens.services.skill_tracking_service import SkillTrackingService
from vocablens.services.language_brain_service import LanguageBrainService
from vocablens.services.learning_event_service import LearningEventService
from vocablens.services.mistake_engine import MistakeEngine
from vocablens.services.drill_generation_service import DrillGenerationService
from vocablens.services.event_processors.skill_update_processor import SkillUpdateProcessor
from vocablens.services.event_processors.retention_processor import RetentionProcessor
from vocablens.services.event_processors.knowledge_graph_processor import KnowledgeGraphProcessor
from vocablens.services.retention_engine import RetentionEngine
from vocablens.services.knowledge_graph_service import KnowledgeGraphService
from vocablens.services.speech_conversation_service import SpeechConversationService
from vocablens.providers.speech.whisper_provider import WhisperProvider
from vocablens.providers.speech.tts_provider import TextToSpeechProvider

security = HTTPBearer()

def _state(request: Request):
    return request.app.state


async def get_user_repo():
    return PostgresUserRepository(AsyncSessionMaker)

def get_vocab_repo():
    return PostgresVocabularyRepository(AsyncSessionMaker)

def get_translation_cache_repo():
    return PostgresTranslationCacheRepository(AsyncSessionMaker)

def get_conversation_repo():
    return PostgresConversationRepository(AsyncSessionMaker)

def get_learning_event_repo():
    return PostgresLearningEventRepository(AsyncSessionMaker)

def get_skill_tracking_repo():
    return PostgresSkillTrackingRepository(AsyncSessionMaker)

def get_knowledge_graph_repo():
    return KnowledgeGraphRepository(AsyncSessionMaker)

def get_translation_provider(state=Depends(_state)) -> LibreTranslateProvider:
    return state.translation_provider

def get_llm_provider(state=Depends(_state)) -> OpenAIProvider:
    return state.llm_provider

def get_whisper_provider(state=Depends(_state)) -> WhisperProvider:
    return state.whisper_provider

def get_tts_provider(state=Depends(_state)) -> TextToSpeechProvider:
    return state.tts_provider

def get_skill_tracking_service(state=Depends(_state)) -> SkillTrackingService:
    return state.skill_tracking_service

def get_learning_event_service(state=Depends(_state)) -> LearningEventService:
    return state.learning_event_service

def get_vocabulary_service(state=Depends(_state)) -> VocabularyService:
    return state.vocabulary_service

def get_conversation_service(state=Depends(_state)) -> ConversationService:
    return state.conversation_service

def get_speech_conversation_service(state=Depends(_state)) -> SpeechConversationService:
    return state.speech_conversation_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_repo=Depends(get_user_repo),
) -> User:

    try:
        user_id = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication",
        )

    user = await user_repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
