import logging
from typing import List

from vocablens.providers.translation.base import Translator

logger = logging.getLogger(__name__)


class CachedTranslator:

    def __init__(self, provider: Translator, cache_repo):
        self.provider = provider
        self.cache_repo = cache_repo

    # -----------------------------------------
    # Single translation
    # -----------------------------------------

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:

        cached = await self.cache_repo.get(text, source_lang, target_lang)

        if cached:
            logger.debug("Translation cache hit")
            return cached

        logger.debug("Translation cache miss")

        result = await self.provider.translate(
            text,
            source_lang,
            target_lang,
        )

        await self.cache_repo.save(
            text,
            source_lang,
            target_lang,
            result,
        )

        return result

    # -----------------------------------------
    # Batch translation
    # -----------------------------------------

    async def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
    ) -> List[str]:

        results = []
        missing = []
        missing_indexes = []

        for i, text in enumerate(texts):

            cached = await self.cache_repo.get(
                text,
                source_lang,
                target_lang,
            )

            if cached:
                results.append(cached)
            else:
                results.append(None)
                missing.append(text)
                missing_indexes.append(i)

        if missing:

            translations = await self.provider.translate_batch(
                missing,
                source_lang,
                target_lang,
            )

            for idx, text, translation in zip(
                missing_indexes,
                missing,
                translations,
            ):
                results[idx] = translation

                await self.cache_repo.save(
                    text,
                    source_lang,
                    target_lang,
                    translation,
                )

        return results

    async def close(self):
        if hasattr(self.provider, "close"):
            await self.provider.close()
