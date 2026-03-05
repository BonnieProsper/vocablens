from datetime import datetime, timedelta
from vocablens.domain.models import VocabularyItem


class SpacedRepetitionEngine:

    INITIAL_INTERVAL = 1
    EASY_BONUS = 1.3
    HARD_PENALTY = 0.8

    def review(self, item: VocabularyItem, rating: str) -> VocabularyItem:
        now = datetime.utcnow()

        interval = item.review_count + 1
        retention = item.retention_score

        if rating == "again":
            interval = 1
            retention = max(1.3, retention - 0.2)

        elif rating == "hard":
            retention *= self.HARD_PENALTY

        elif rating == "good":
            interval = int(interval * retention)

        elif rating == "easy":
            interval = int(interval * retention * self.EASY_BONUS)
            retention += 0.15

        next_due = now + timedelta(days=max(1, interval))

        item.review_count += 1
        item.last_reviewed_at = now
        item.next_review_due = next_due
        item.retention_score = retention

        return item