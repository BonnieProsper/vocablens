from datetime import datetime
from typing import List

from vocablens.domain.models import VocabularyItem
from vocablens.domain.errors import NotFoundError
from vocablens.providers.translation.base import Translator
from vocablens.infrastructure.repositories import SQLiteVocabularyRepository


class VocabularyService:
    def __init__(
        self,
        translator: Translator,
        repository: SQLiteVocabularyRepository,
    ) -> None:
        self._translator = translator
        self._repository = repository

    def process_text(
        self,
        user_id: int,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> VocabularyItem:

        translated = self._translator.translate(text, target_lang)

        item = VocabularyItem(
            id=None,
            source_text=text,
            translated_text=translated,
            source_lang=source_lang,
            target_lang=target_lang,
            created_at=datetime.utcnow(),
        )

        return self._repository.add(user_id, item)

    def list_vocabulary(
        self,
        user_id: int,
        limit: int,
        offset: int,
    ) -> List[VocabularyItem]:
        return self._repository.list_all(user_id, limit, offset)

    def review_item(self, user_id: int, item_id: int) -> VocabularyItem:
        try:
            return self._repository.increment_review(user_id, item_id)
        except ValueError:
            raise NotFoundError(f"Vocabulary item {item_id} not found")

    def list_due_items(self, user_id: int) -> List[VocabularyItem]:
        return self._repository.list_due(user_id)