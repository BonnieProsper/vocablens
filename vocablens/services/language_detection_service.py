from langdetect import detect


class LanguageDetectionService:

    def detect(self, text: str) -> str:

        try:
            return detect(text)

        except Exception:
            return "unknown"