from datetime import datetime


class RetentionEngine:

    def forgetting_probability(self, item):

        if not item.last_reviewed_at:
            return 0.8

        days = (datetime.utcnow() - item.last_reviewed_at).days

        score = item.retention_score

        probability = min(1.0, (days / 7) * (1 - score))

        return probability

    def needs_review(self, item):

        return self.forgetting_probability(item) > 0.6