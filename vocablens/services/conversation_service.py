from typing import List

from vocablens.providers.llm.base import LLMProvider
from vocablens.infrastructure.repositories import SQLiteVocabularyRepository

from vocablens.services.language_brain_service import LanguageBrainService
from vocablens.services.conversation_memory_service import ConversationMemoryService
from vocablens.services.conversation_vocab_service import ConversationVocabularyService
from vocablens.services.skill_tracking_service import SkillTrackingService


class ConversationService:
    """
    AI language tutor that adapts to vocabulary,
    skill level, and conversation history.
    """

    def __init__(
        self,
        llm: LLMProvider,
        vocab_repo: SQLiteVocabularyRepository,
        brain: LanguageBrainService,
        memory: ConversationMemoryService,
        vocab_extractor: ConversationVocabularyService,
        skill_tracker: SkillTrackingService,
    ):
        self._llm = llm
        self._repo = vocab_repo
        self._brain = brain
        self._memory = memory
        self._vocab_extractor = vocab_extractor
        self._skills = skill_tracker

    def _get_known_words(self, user_id: int) -> List[str]:

        items = self._repo.list_all(user_id, limit=500, offset=0)

        return [i.source_text for i in items][:200]

    def generate_reply(
        self,
        user_id: int,
        user_message: str,
        source_lang: str,
        target_lang: str,
    ) -> dict:

        # --------------------------------
        # Discover new vocabulary
        # --------------------------------

        self._vocab_extractor.process_message(
            user_id,
            user_message,
            source_lang,
            target_lang,
        )

        # --------------------------------
        # Brain analysis
        # --------------------------------

        brain_output = self._brain.process_message(
            user_id=user_id,
            message=user_message,
            language=source_lang,
        )

        analysis = brain_output["analysis"]

        # --------------------------------
        # Update skill model
        # --------------------------------

        self._skills.update_from_analysis(user_id, analysis)

        skill_profile = self._skills.get_skill_profile(user_id)

        # --------------------------------
        # Conversation context
        # --------------------------------

        history = self._memory.get_recent_context(user_id)

        known_words = self._get_known_words(user_id)

        vocab_list = ", ".join(known_words)

        prompt = f"""
You are an expert language tutor helping a student learn {source_lang}.

Student skill profile:
Grammar: {skill_profile["grammar"]}
Vocabulary: {skill_profile["vocabulary"]}
Fluency: {skill_profile["fluency"]}

Conversation history:
{history}

Student message:
{user_message}

Known vocabulary:
{vocab_list}

Detected mistakes:
{analysis.get("grammar_mistakes", [])}

Rules:
- Use mostly known vocabulary
- Introduce at most 1–2 new words
- Keep sentences short
- Correct mistakes gently
- Encourage the learner
- Adjust difficulty based on skill profile
- Respond ONLY in {source_lang}
"""

        reply = self._llm.generate(prompt)

        self._memory.store_turn(
            user_id,
            user_message,
            reply,
        )

        return {
            "reply": reply,
            "analysis": analysis,
            "drills": brain_output["drills"],
        }