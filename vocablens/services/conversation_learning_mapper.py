from __future__ import annotations

from vocablens.services.learning_engine import SessionResult


class ConversationLearningMapper:
    def build_session_result(
        self,
        *,
        analysis: dict,
        recommendation,
        known_words: list[str],
        skill_profile: dict,
        learned_item_ids: list[int],
    ) -> SessionResult:
        weak_areas = self.weak_areas(analysis, recommendation)
        learned_words = self._learned_words(weak_areas, known_words)
        return SessionResult(
            learned_item_ids=list(learned_item_ids),
            skill_scores={
                key: float(value)
                for key, value in skill_profile.items()
                if isinstance(value, (int, float))
            },
            mistakes=self.session_mistakes(analysis),
            weak_areas=self._merge_weak_areas(weak_areas, recommendation, learned_words),
        )

    def weak_areas(self, analysis: dict, recommendation) -> list[str]:
        weak_areas: list[str] = []
        for item in analysis.get("grammar_mistakes", []) or []:
            weak_areas.append(str(item))
        for item in analysis.get("vocab_misuse", []) or []:
            weak_areas.append(str(item))
        if recommendation and getattr(recommendation, "target", None):
            weak_areas.append(str(recommendation.target))
        return self._dedupe_preserve_order(weak_areas)

    def session_mistakes(self, analysis: dict) -> list[dict[str, str]]:
        mistakes: list[dict[str, str]] = []
        for item in analysis.get("grammar_mistakes", []) or []:
            mistakes.append({"category": "grammar", "pattern": str(item)})
        for item in analysis.get("vocab_misuse", []) or []:
            mistakes.append({"category": "vocabulary", "pattern": str(item)})
        for item in analysis.get("repeated_errors", []) or []:
            if isinstance(item, dict):
                pattern = item.get("pattern")
                category = item.get("category") or "repetition"
            else:
                pattern = str(getattr(item, "pattern", item))
                category = str(getattr(item, "category", "repetition"))
            if pattern:
                mistakes.append({"category": str(category), "pattern": str(pattern)})
        return mistakes

    def _learned_words(self, weak_areas: list[str], known_words: list[str]) -> list[str]:
        known = {word.lower() for word in known_words}
        learned_words: list[str] = []
        for word in weak_areas:
            normalized = str(word).strip()
            if normalized and normalized.lower() not in known:
                learned_words.append(normalized)
        return self._dedupe_preserve_order(learned_words)

    def _merge_weak_areas(self, weak_areas: list[str], recommendation, learned_words: list[str]) -> list[str]:
        merged = list(weak_areas)
        if recommendation and getattr(recommendation, "skill_focus", None):
            merged.append(str(recommendation.skill_focus))
        merged.extend(learned_words)
        return self._dedupe_preserve_order(merged)

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            normalized = value.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(normalized)
        return output
