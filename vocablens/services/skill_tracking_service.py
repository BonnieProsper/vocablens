from collections import defaultdict


class SkillTrackingService:
    """
    Tracks language skill levels for each user.
    Values range 0–1 and adjust over time.
    """

    def __init__(self):

        self.skills = defaultdict(
            lambda: {
                "grammar": 0.5,
                "vocabulary": 0.5,
                "fluency": 0.5,
            }
        )

    def update_from_analysis(self, user_id: int, analysis: dict):

        profile = self.skills[user_id]

        if analysis.get("grammar_mistakes"):
            profile["grammar"] -= 0.02
        else:
            profile["grammar"] += 0.01

        if analysis.get("unknown_words"):
            profile["vocabulary"] -= 0.01
        else:
            profile["vocabulary"] += 0.01

        profile["grammar"] = min(max(profile["grammar"], 0), 1)
        profile["vocabulary"] = min(max(profile["vocabulary"], 0), 1)
        profile["fluency"] = min(max(profile["fluency"], 0), 1)

    def get_skill_profile(self, user_id: int):

        return self.skills[user_id]