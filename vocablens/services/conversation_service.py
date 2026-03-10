from typing import List

from vocablens.providers.llm.base import LLMProvider
from vocablens.infrastructure.repositories import SQLiteVocabularyRepository
from vocablens.services.language_brain_service import LanguageBrainService
from vocablens.services.conversation_memory_service import ConversationMemoryService


class ConversationService:
    """
    AI language tutor that adapts to the learner's vocabulary,
    conversation context, and mistake analysis.
    """

    def __init__(
        self,
        llm: LLMProvider,
        vocab_repo: SQLiteVocabularyRepository,
        brain: LanguageBrainService,
        memory: ConversationMemoryService,
    ):
        self._llm = llm
        self._repo = vocab_repo
        self._brain = brain
        self._memory = memory

    # ------------------------------------------------
    # Vocabulary retrieval
    # ------------------------------------------------

    def _get_known_words(self, user_id: int) -> List[str]:

        items = self._repo.list_all(user_id, limit=500, offset=0)

        return [i.source_text for i in items][:200]

    # ------------------------------------------------
    # Conversation reply
    # ------------------------------------------------

    def generate_reply(
        self,
        user_id: int,
        user_message: str,
        source_lang: str,
        target_lang: str,
    ) -> dict:

        # analyze message using language brain
        brain_output = self._brain.process_message(
            user_id,
            user_message,
            source_lang,
        )

        # retrieve conversation context
        context = self._memory.get_context(user_id)

        known_words = self._get_known_words(user_id)

        vocab_list = ", ".join(known_words)

        context_text = "\n".join(context[-5:])

        prompt = f"""
You are an AI language tutor helping a student practice {source_lang}.

Conversation history:
{context_text}

Student message:
{user_message}

Known vocabulary:
{vocab_list}

Rules:
- Use mostly known vocabulary
- Introduce at most 1–2 new words
- Keep sentences short
- Correct mistakes politely
- Encourage the learner

Respond in {source_lang}.
"""

        reply = self._llm.generate(prompt)

        # store conversation
        self._memory.add_message(user_id, user_message)
        self._memory.add_message(user_id, reply)

        return {
            "reply": reply,
            "analysis": brain_output["analysis"],
            "drills": brain_output["drills"],
        }