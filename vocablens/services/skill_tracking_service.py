from collections import defaultdict


class SkillTrackingService:
    """
    Tracks user language weaknesses.
    """

    def __init__(self):

        self.grammar_errors = defaultdict(int)
        self.vocab_errors = defaultdict(int)

    def record_grammar_error(self, user_id: int):

        self.grammar_errors[user_id] += 1

    def record_vocab_error(self, user_id: int):

        self.vocab_errors[user_id] += 1

    def get_skill_profile(self, user_id: int):

        return {
            "grammar_errors": self.grammar_errors[user_id],
            "vocab_errors": self.vocab_errors[user_id],
        }