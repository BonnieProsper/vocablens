from datetime import datetime
from typing import List

from vocablens.domain.models import VocabularyItem
from vocablens.domain.errors import NotFoundError
from vocablens.domain.spaced_repetition import SpacedRepetitionEngine
from vocablens.providers.translation.base import Translator
from vocablens.infrastructure.repositories import SQLiteVocabularyRepository
from vocablens.services.word_extraction_service import WordExtractionService


class VocabularyService:

    def __init__(
        self,
        translator: Translator,
        repository: SQLiteVocabularyRepository,
        extractor: WordExtractionService,
    ) -> None:

        self._translator = translator
        self._repository = repository
        self._extractor = extractor
        self._srs = SpacedRepetitionEngine()

    # ------------------------------------------------
    # OCR → vocabulary pipeline
    # ------------------------------------------------

    def process_ocr_text(
        self,
        user_id: int,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> List[VocabularyItem]:

        words = self._extractor.extract_words(text)

        return self.process_vocabulary_batch(
            user_id,
            words,
            source_lang,
            target_lang,
        )

    # ------------------------------------------------
    # Batch vocabulary creation
    # ------------------------------------------------

    def process_vocabulary_batch(
        self,
        user_id: int,
        words: List[str],
        source_lang: str,
        target_lang: str,
    ) -> List[VocabularyItem]:

        words = list(set(words))

        translations = self._translator.translate_batch(
            words,
            source_lang,
            target_lang,
        )

        items = []

        for word, translated in zip(words, translations):

            if self._repository.exists(
                user_id,
                word,
                source_lang,
                target_lang,
            ):
                continue

            item = VocabularyItem(
                id=None,
                source_text=word,
                translated_text=translated,
                source_lang=source_lang,
                target_lang=target_lang,
                created_at=datetime.utcnow(),
            )

            saved = self._repository.add(user_id, item)

            items.append(saved)

        return items

    # ------------------------------------------------
    # Vocabulary queries
    # ------------------------------------------------

    def list_vocabulary(
        self,
        user_id: int,
        limit: int,
        offset: int,
    ) -> List[VocabularyItem]:

        return self._repository.list_all(
            user_id,
            limit,
            offset,
        )

    def list_due_items(
        self,
        user_id: int,
    ) -> List[VocabularyItem]:

        return self._repository.list_due(user_id)

    # ------------------------------------------------
    # Spaced repetition review
    # ------------------------------------------------

    def review_item(
        self,
        user_id: int,
        item_id: int,
        rating: str,
    ) -> VocabularyItem:

        item = self._repository.get(user_id, item_id)

        if not item:
            raise NotFoundError(
                f"Vocabulary item {item_id} not found"
            )

        updated = self._srs.review(item, rating)

        return self._repository.update(updated)

    def review_session(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[VocabularyItem]:

        items = self._repository.list_due(user_id)

        return items[:limit]