class CachedTranslator:

    def __init__(self, provider, cache_repo):
        self.provider = provider
        self.cache_repo = cache_repo

    def translate(self, text, source, target):

        cached = self.cache_repo.get(text, source, target)

        if cached:
            return cached

        result = self.provider.translate(text, source, target)

        self.cache_repo.save(text, source, target, result)

        return result
    

# TO ADD

CREATE TABLE IF NOT EXISTS translation_cache (
    text TEXT NOT NULL,
    source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    translation TEXT NOT NULL,
    PRIMARY KEY (text, source_lang, target_lang)
);


