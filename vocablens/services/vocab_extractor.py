import re

STOPWORDS = {
    "the", "and", "is", "a", "an", "of", "to"
}


class VocabularyExtractor:

    def extract(self, text: str) -> list[str]:

        words = re.findall(r"[a-zA-ZÀ-ÿ]+", text.lower())

        words = [
            w for w in words
            if len(w) > 2 and w not in STOPWORDS
        ]

        return list(set(words))