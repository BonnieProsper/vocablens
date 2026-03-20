from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

from vocablens.core.time import utc_now
from vocablens.infrastructure.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class WowScore:
    score: float
    tutor_interaction_score: float
    accuracy_improvement_score: float
    engagement_score: float
    baseline_accuracy: float
    current_accuracy: float
    qualifies: bool
    triggers: dict[str, bool]


class WowEngine:
    def __init__(self, uow_factory: type[UnitOfWork] | None = None):
        self._uow_factory = uow_factory

    async def score_session(
        self,
        user_id: int,
        *,
        tutor_mode: bool,
        correction_feedback_count: int,
        new_words_count: int,
        grammar_mistake_count: int,
        session_turn_count: int,
        reply_length: int,
    ) -> WowScore:
        baseline_accuracy = await self._baseline_accuracy(user_id)
        current_accuracy = self._current_accuracy(
            correction_feedback_count=correction_feedback_count,
            new_words_count=new_words_count,
            grammar_mistake_count=grammar_mistake_count,
        )
        tutor_score = self._tutor_interaction_score(
            tutor_mode=tutor_mode,
            correction_feedback_count=correction_feedback_count,
            new_words_count=new_words_count,
        )
        accuracy_score = self._accuracy_improvement_score(
            baseline_accuracy=baseline_accuracy,
            current_accuracy=current_accuracy,
        )
        engagement_score = self._engagement_score(
            session_turn_count=session_turn_count,
            reply_length=reply_length,
        )
        total = round(min(1.0, tutor_score + accuracy_score + engagement_score), 3)
        qualifies = total >= 0.65
        return WowScore(
            score=total,
            tutor_interaction_score=round(tutor_score, 3),
            accuracy_improvement_score=round(accuracy_score, 3),
            engagement_score=round(engagement_score, 3),
            baseline_accuracy=round(baseline_accuracy, 3),
            current_accuracy=round(current_accuracy, 3),
            qualifies=qualifies,
            triggers={
                "paywall": total >= 0.65,
                "trial": total >= 0.8,
                "upsell": total >= 0.72,
            },
        )

    async def _baseline_accuracy(self, user_id: int) -> float:
        if not self._uow_factory:
            return 0.5
        async with self._uow_factory() as uow:
            events = await uow.learning_events.list_since(
                user_id,
                since=utc_now() - timedelta(days=14),
            )
            await uow.commit()
        scores = []
        for event in events:
            if getattr(event, "event_type", None) != "word_reviewed":
                continue
            payload = self._payload(event)
            if payload.get("response_accuracy") is not None:
                scores.append(float(payload["response_accuracy"]))
        if not scores:
            return 0.5
        return max(0.0, min(1.0, sum(scores) / len(scores)))

    def _current_accuracy(
        self,
        *,
        correction_feedback_count: int,
        new_words_count: int,
        grammar_mistake_count: int,
    ) -> float:
        correction_bonus = min(0.2, correction_feedback_count * 0.05)
        vocabulary_bonus = min(0.15, new_words_count * 0.05)
        mistake_penalty = min(0.45, grammar_mistake_count * 0.1)
        return max(0.0, min(1.0, 0.65 + correction_bonus + vocabulary_bonus - mistake_penalty))

    def _tutor_interaction_score(
        self,
        *,
        tutor_mode: bool,
        correction_feedback_count: int,
        new_words_count: int,
    ) -> float:
        if not tutor_mode:
            return 0.0
        score = 0.15
        if correction_feedback_count > 0:
            score += 0.15
        score += min(0.1, correction_feedback_count * 0.03)
        score += min(0.1, new_words_count * 0.05)
        return min(0.4, score)

    def _accuracy_improvement_score(self, *, baseline_accuracy: float, current_accuracy: float) -> float:
        improvement = max(0.0, current_accuracy - baseline_accuracy)
        if improvement <= 0:
            return 0.0
        return min(0.35, improvement * 0.7)

    def _engagement_score(self, *, session_turn_count: int, reply_length: int) -> float:
        turns_score = min(0.2, max(0, session_turn_count) * 0.04)
        reply_bonus = 0.05 if reply_length >= 120 else 0.0
        return min(0.25, turns_score + reply_bonus)

    def _payload(self, event) -> dict:
        payload = getattr(event, "payload", None)
        if isinstance(payload, dict):
            return payload
        payload_json = getattr(event, "payload_json", None)
        if not payload_json:
            return {}
        try:
            return json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            return {}
