import logging
from vocablens.providers.translation.base import Translator

logger = logging.getLogger(__name__)


class CachedTranslator(Translator):

    def __init__(self, provider: Translator, cache_repo):
        self.provider = provider
        self.cache_repo = cache_repo

    def translate(self, text: str, target_lang: str) -> str:

        cached = self.cache_repo.get(text, target_lang)

        if cached:
            logger.info("Translation cache hit")
            return cached

        logger.info("Translation cache miss")

        result = self.provider.translate(text, target_lang)

        self.cache_repo.save(text, target_lang, result)

        return result

    def close(self):
        if hasattr(self.provider, "close"):
            self.provider.close()