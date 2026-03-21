import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

from vocablens.core.time import utc_now
from vocablens.infrastructure.unit_of_work import UnitOfWork
from vocablens.services.event_service import EventService
from vocablens.services.experiment_service import ExperimentService
from vocablens.services.global_decision_engine import GlobalDecisionEngine
from vocablens.services.personalization_service import PersonalizationAdaptation, PersonalizationService
from vocablens.services.retention_engine import RetentionAssessment, RetentionEngine
from vocablens.services.spaced_repetition_service import SpacedRepetitionService
from vocablens.services.subscription_service import SubscriptionService

NextAction = Literal["review_word", "learn_new_word", "practice_grammar", "conversation_drill"]


@dataclass
class LearningRecommendation:
    action: NextAction
    target: str | None
    reason: str
    lesson_difficulty: str = "medium"
    review_frequency_multiplier: float = 1.0
    content_type: str = "mixed"
    review_priority: float = 0.0
    skill_focus: str | None = None
    due_items_count: int = 0


@dataclass(frozen=True)
class ReviewedKnowledge:
    item_id: int
    quality: int
    response_accuracy: float | None = None
    mistake_frequency: int = 0
    difficulty_score: float | None = None


@dataclass(frozen=True)
class SessionResult:
    reviewed_items: list[ReviewedKnowledge] = field(default_factory=list)
    learned_item_ids: list[int] = field(default_factory=list)
    skill_scores: dict[str, float] = field(default_factory=dict)
    mistakes: list[dict[str, str]] = field(default_factory=list)
    weak_areas: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KnowledgeUpdateSummary:
    reviewed_count: int
    learned_count: int
    weak_areas: list[str]
    updated_item_ids: list[int]


class LearningEngine:
    """
    Decides the next best learning action using vocabulary mastery, skills,
    recent learning events, and the knowledge graph.
    """

    def __init__(
        self,
        uow_factory: type[UnitOfWork],
        retention_engine: RetentionEngine | None = None,
        personalization: PersonalizationService | None = None,
        subscription_service: SubscriptionService | None = None,
        experiment_service: ExperimentService | None = None,
        event_service: EventService | None = None,
        global_decision_engine: GlobalDecisionEngine | None = None,
    ):
        self._uow_factory = uow_factory
        self._retention = retention_engine or RetentionEngine()
        self._personalization = personalization
        self._subscription_service = subscription_service
        self._experiments = experiment_service
        self._event_service = event_service
        self._global_decision = global_decision_engine
        self._scheduler = SpacedRepetitionService()

    async def recommend(self, user_id: int) -> LearningRecommendation:
        return await self.get_next_lesson(user_id)

    async def get_next_lesson(self, user_id: int) -> LearningRecommendation:
        if self._global_decision:
            return await self._recommend_from_global_decision(user_id)
        retention = await self._get_retention_assessment(user_id)
        async with self._uow_factory() as uow:
            due_items = await uow.vocab.list_due(user_id)
            total_vocab = await uow.vocab.list_all(user_id, limit=200, offset=0)
            skills = await uow.skill_tracking.latest_scores(user_id)
            grammar_score = skills.get("grammar", 0.5)
            vocab_score = skills.get("vocabulary", 0.5)
            fluency_score = skills.get("fluency", 0.5)
            kg = await uow.knowledge_graph.list_clusters(user_id)
            weak_clusters = await uow.knowledge_graph.get_weak_clusters(user_id)
            sparse_cluster = None
            if kg:
                populated = {
                    cluster: cluster_data.get("words", [])
                    for cluster, cluster_data in kg.items()
                    if cluster_data.get("words")
                }
                sparse_cluster = min(populated, key=lambda k: len(populated[k])) if populated else None
            patterns = await uow.mistake_patterns.top_patterns(user_id, limit=3)
            repeated_patterns = await uow.mistake_patterns.repeated_patterns(user_id, threshold=2, limit=3)
            yesterday = utc_now() - timedelta(hours=24)
            recent_events = await uow.learning_events.list_since(user_id, since=yesterday)
            profile = await uow.profiles.get_or_create(user_id)
            await uow.commit()

        adaptation = await self._get_adaptation(user_id, profile)
        feature_level = await self._personalization_level(user_id)
        learning_variant = await self._learning_variant(user_id)
        difficulty_pref = (profile.difficulty_preference if profile else "medium").lower()
        retention_rate = profile.retention_rate if profile else 0.8

        grammar_thresh = 0.45 if difficulty_pref != "easy" else 0.55
        vocab_thresh = 0.5 if difficulty_pref != "easy" else 0.6
        due_pressure = self._review_pressure(
            due_items,
            retention_rate,
            adaptation.review_frequency_multiplier,
            patterns,
        )
        review_vs_new_bias = self._review_vs_new_bias(total_vocab, recent_events, retention_rate)
        prioritized_due = self._prioritize_due_items(due_items, retention_rate, patterns)
        if learning_variant == "review_heavy":
            review_vs_new_bias = max(review_vs_new_bias, 0.7)
        if learning_variant == "vocab_focus":
            adaptation.content_type = "vocab"

        if retention and retention.state in {"at-risk", "churned"} and prioritized_due:
            return await self._finalize_recommendation(
                user_id,
                LearningRecommendation(
                    "review_word",
                    prioritized_due[0].source_text,
                    f"Retention state is {retention.state}; bring back due material first",
                    review_priority=due_pressure,
                    due_items_count=len(prioritized_due),
                ),
                adaptation,
            )

        if retention and retention.state in {"at-risk", "churned"} and repeated_patterns:
            return await self._finalize_recommendation(
                user_id,
                LearningRecommendation(
                    "conversation_drill",
                    repeated_patterns[0].pattern,
                    f"Retention state is {retention.state}; use a quick targeted drill",
                    skill_focus="fluency",
                ),
                adaptation,
            )

        if prioritized_due and (due_pressure >= 0.4 or review_vs_new_bias >= 0.5):
            top_due = prioritized_due[0]
            reason = (
                f"{len(prioritized_due)} items due with retention pressure {due_pressure:.2f}; "
                f"'{top_due.source_text}' has the highest decay"
            )
            return await self._finalize_recommendation(
                user_id,
                LearningRecommendation(
                    "review_word",
                    top_due.source_text,
                    reason,
                    review_priority=self._item_review_priority(top_due, retention_rate, patterns),
                    due_items_count=len(prioritized_due),
                ),
                adaptation,
            )

        if grammar_score < grammar_thresh or any(p.category == "grammar" for p in (patterns or [])):
            return await self._finalize_recommendation(
                user_id,
                LearningRecommendation(
                    "practice_grammar",
                    "grammar",
                    "Grammar skill below threshold",
                    skill_focus="grammar",
                ),
                adaptation,
            )

        if (
            adaptation.content_type == "vocab"
            or vocab_score < vocab_thresh
            or (feature_level != "basic" and weak_clusters)
            or sparse_cluster
            or any(p.category == "vocabulary" for p in (patterns or []))
        ):
            target = None
            reason = "Vocabulary coverage low in cluster"
            if feature_level != "basic" and weak_clusters:
                target = weak_clusters[0]["cluster"]
                related = ", ".join(weak_clusters[0].get("words", [])[:3])
                reason = f"Weak cluster '{target}' should be reinforced with related words: {related or 'general set'}"
            elif sparse_cluster:
                target = sparse_cluster
            else:
                target = "general"
            return await self._finalize_recommendation(
                user_id,
                LearningRecommendation(
                    "learn_new_word",
                    target,
                    reason,
                    skill_focus="vocabulary",
                ),
                adaptation,
            )

        if repeated_patterns:
            top = repeated_patterns[0]
            return await self._finalize_recommendation(
                user_id,
                LearningRecommendation(
                    "conversation_drill",
                    top.pattern,
                    "Address repeated errors",
                    skill_focus="fluency",
                ),
                adaptation,
            )

        if learning_variant == "conversation_focus" and fluency_score < 0.75:
            return await self._finalize_recommendation(
                user_id,
                LearningRecommendation(
                    "conversation_drill",
                    None,
                    "Conversation experiment variant prioritizes fluency practice",
                    skill_focus="fluency",
                ),
                adaptation,
            )

        if adaptation.content_type == "conversation" or fluency_score < 0.6:
            return await self._finalize_recommendation(
                user_id,
                LearningRecommendation(
                    "conversation_drill",
                    None,
                    "Build fluency through guided practice",
                    skill_focus="fluency",
                ),
                adaptation,
            )

        return await self._finalize_recommendation(
            user_id,
            LearningRecommendation(
                "learn_new_word",
                sparse_cluster or "general",
                "Balanced progression into new material",
                skill_focus="vocabulary",
            ),
            adaptation,
        )

    async def update_knowledge(self, user_id: int, session_result: SessionResult) -> KnowledgeUpdateSummary:
        updated_item_ids: list[int] = []
        reviewed_count = 0
        learned_count = 0
        now = utc_now()

        async with self._uow_factory() as uow:
            profile = await uow.profiles.get_or_create(user_id)
            retention_rate = getattr(profile, "retention_rate", 0.8)
            review_multiplier = self._review_multiplier(profile)

            for review in session_result.reviewed_items:
                item = await uow.vocab.get(user_id, review.item_id)
                if not item:
                    continue
                accuracy = max(0.0, min(1.0, review.response_accuracy if review.response_accuracy is not None else review.quality / 5.0))
                difficulty_score = review.difficulty_score
                if difficulty_score is None:
                    difficulty_score = min(1.0, max(0.0, len(item.source_text or "") / 12.0))
                previous_reviews = int(getattr(item, "review_count", 0) or 0)
                previous_success = float(getattr(item, "success_rate", 0.0) or 0.0)

                updated = self._scheduler.review(
                    item,
                    review.quality,
                    retention_rate=retention_rate,
                    mistake_frequency=review.mistake_frequency,
                    difficulty_score=difficulty_score,
                    review_frequency_multiplier=review_multiplier,
                )
                updated.last_seen_at = now
                updated.success_rate = self._rolling_success_rate(previous_success, previous_reviews, accuracy)
                updated.decay_score = self._scheduler.decay_score(
                    updated,
                    retention_rate=retention_rate,
                    mistake_frequency=review.mistake_frequency,
                    difficulty_score=difficulty_score,
                    as_of=now,
                )
                await uow.vocab.update(updated)
                await uow.learning_events.record(
                    user_id,
                    "word_reviewed",
                    json.dumps(
                        {
                            "item_id": updated.id,
                            "quality": review.quality,
                            "response_accuracy": accuracy,
                            "success_rate": updated.success_rate,
                            "decay_score": updated.decay_score,
                            "next_review_due": updated.next_review_due.isoformat() if updated.next_review_due else None,
                        }
                    ),
                )
                updated_item_ids.append(updated.id)
                reviewed_count += 1

            for item_id in session_result.learned_item_ids:
                item = await uow.vocab.get(user_id, item_id)
                if not item:
                    continue
                item.last_seen_at = now
                if not getattr(item, "success_rate", None):
                    item.success_rate = 0.6
                item.decay_score = self._scheduler.decay_score(
                    item,
                    retention_rate=retention_rate,
                    mistake_frequency=0,
                    difficulty_score=min(1.0, max(0.0, len(item.source_text or "") / 12.0)),
                    as_of=now,
                )
                await uow.vocab.update(item)
                updated_item_ids.append(item.id)
                learned_count += 1

            for skill, score in session_result.skill_scores.items():
                await uow.skill_tracking.record(user_id, skill, max(0.0, min(1.0, float(score))))
                await uow.learning_events.record(
                    user_id,
                    "skill_update",
                    json.dumps({skill: max(0.0, min(1.0, float(score)))}),
                )

            for mistake in session_result.mistakes:
                category = (mistake.get("category") or "general").strip().lower()
                pattern = (mistake.get("pattern") or "").strip()
                if not pattern:
                    continue
                await uow.mistake_patterns.record(user_id, category, pattern)

            await uow.commit()

        if self._event_service:
            await self._event_service.track_event(
                user_id=user_id,
                event_type="knowledge_updated",
                payload={
                    "source": "learning_engine",
                    "reviewed_count": reviewed_count,
                    "learned_count": learned_count,
                    "updated_item_ids": updated_item_ids,
                    "weak_areas": list(session_result.weak_areas),
                },
            )

        return KnowledgeUpdateSummary(
            reviewed_count=reviewed_count,
            learned_count=learned_count,
            weak_areas=list(session_result.weak_areas),
            updated_item_ids=updated_item_ids,
        )

    def _review_pressure(self, due_items, retention_rate: float, frequency_multiplier: float, patterns) -> float:
        if not due_items:
            return 0.0
        max_urgency = 0.0
        total_urgency = 0.0
        for item in due_items:
            urgency = self._item_review_priority(item, retention_rate, patterns)
            total_urgency += urgency
            max_urgency = max(max_urgency, urgency)
        average_urgency = total_urgency / max(1, len(due_items))
        due_load = min(1.0, len(due_items) / max(4, int(8 * max(frequency_multiplier, 0.6))))
        return max(max_urgency, average_urgency, due_load)

    def _review_vs_new_bias(self, total_vocab, recent_events, retention_rate: float) -> float:
        total_count = len(total_vocab)
        recent_new = sum(1 for event in recent_events if event.event_type == "word_learned")
        recent_reviews = sum(1 for event in recent_events if event.event_type == "word_reviewed")
        if total_count < 20:
            return 0.25
        if recent_new > recent_reviews and retention_rate < 0.75:
            return 0.7
        if recent_reviews > recent_new:
            return 0.35
        return 0.5

    async def _get_adaptation(self, user_id: int, profile) -> PersonalizationAdaptation:
        if self._personalization:
            return await self._personalization.get_adaptation(user_id)
        difficulty = profile.difficulty_preference if profile else "medium"
        retention_rate = profile.retention_rate if profile else 0.8
        content_type = profile.content_preference if profile else "mixed"
        return PersonalizationAdaptation(
            lesson_difficulty=difficulty,
            review_frequency_multiplier=1.0 if retention_rate >= 0.75 else 0.8,
            content_type=content_type,
        )

    async def _get_retention_assessment(self, user_id: int) -> RetentionAssessment | None:
        if not self._retention or not hasattr(self._retention, "assess_user"):
            return None
        return await self._retention.assess_user(user_id)

    def _decorate(self, recommendation: LearningRecommendation, adaptation: PersonalizationAdaptation):
        recommendation.lesson_difficulty = adaptation.lesson_difficulty
        recommendation.review_frequency_multiplier = adaptation.review_frequency_multiplier
        recommendation.content_type = adaptation.content_type
        return recommendation

    def _mistake_frequency(self, source_text: str | None, patterns) -> int:
        if not source_text:
            return 0
        frequency = 0
        needle = source_text.lower()
        for pattern in patterns or []:
            if needle in str(getattr(pattern, "pattern", "")).lower():
                frequency += int(getattr(pattern, "count", 1) or 1)
        return frequency

    def _item_review_priority(self, item, retention_rate: float, patterns) -> float:
        difficulty_score = min(1.0, max(0.0, (len(getattr(item, "source_text", "") or "") / 12.0)))
        mistake_frequency = self._mistake_frequency(getattr(item, "source_text", None), patterns)
        stored_decay = float(getattr(item, "decay_score", 0.0) or 0.0)
        dynamic_decay = self._scheduler.decay_score(
            item,
            retention_rate=retention_rate,
            mistake_frequency=mistake_frequency,
            difficulty_score=difficulty_score,
        )
        success_penalty = max(0.0, 0.7 - float(getattr(item, "success_rate", 0.0) or 0.0))
        return max(stored_decay, dynamic_decay) + (success_penalty * 0.4)

    def _prioritize_due_items(self, due_items, retention_rate: float, patterns):
        return sorted(
            due_items,
            key=lambda item: (
                -self._item_review_priority(item, retention_rate, patterns),
                getattr(item, "next_review_due", utc_now()),
            ),
        )

    async def _personalization_level(self, user_id: int) -> str:
        if not self._subscription_service:
            return "premium"
        features = await self._subscription_service.get_features(user_id)
        await self._subscription_service.record_feature_gate(
            user_id=user_id,
            feature_name="personalization_level",
            allowed=True,
            current_tier=features.tier,
            required_tier=features.tier,
        )
        return features.personalization_level

    async def _learning_variant(self, user_id: int) -> str | None:
        if not self._experiments or not self._experiments.has_experiment("learning_strategy"):
            return None
        return await self._experiments.assign(user_id, "learning_strategy")

    async def _finalize_recommendation(
        self,
        user_id: int,
        recommendation: LearningRecommendation,
        adaptation: PersonalizationAdaptation,
    ) -> LearningRecommendation:
        decorated = self._decorate(recommendation, adaptation)
        if self._event_service:
            await self._event_service.track_event(
                user_id=user_id,
                event_type="lesson_recommended",
                payload={
                    "source": "learning_engine",
                    "action": decorated.action,
                    "target": decorated.target,
                    "difficulty": decorated.lesson_difficulty,
                    "content_type": decorated.content_type,
                    "reason": decorated.reason,
                    "review_priority": decorated.review_priority,
                    "skill_focus": decorated.skill_focus,
                    "due_items_count": decorated.due_items_count,
                },
            )
        return decorated

    async def _recommend_from_global_decision(self, user_id: int) -> LearningRecommendation:
        decision = await self._global_decision.decide(user_id)
        async with self._uow_factory() as uow:
            due_items = await uow.vocab.list_due(user_id)
            weak_clusters = await uow.knowledge_graph.get_weak_clusters(user_id)
            repeated_patterns = await uow.mistake_patterns.repeated_patterns(user_id, threshold=2, limit=3)
            profile = await uow.profiles.get_or_create(user_id)
            await uow.commit()
        adaptation = await self._get_adaptation(user_id, profile)
        adaptation = PersonalizationAdaptation(
            lesson_difficulty=decision.difficulty_level,
            review_frequency_multiplier=adaptation.review_frequency_multiplier,
            content_type=adaptation.content_type,
        )

        if decision.primary_action == "review":
            prioritized_due = self._prioritize_due_items(due_items, getattr(profile, "retention_rate", 0.8), [])
            recommendation = LearningRecommendation(
                "review_word",
                getattr(prioritized_due[0], "source_text", None) if prioritized_due else None,
                decision.reason,
                due_items_count=len(prioritized_due),
                review_priority=1.0 if prioritized_due else 0.0,
            )
        elif decision.primary_action == "conversation":
            target = getattr(repeated_patterns[0], "pattern", None) if repeated_patterns else None
            recommendation = LearningRecommendation(
                "conversation_drill",
                target,
                decision.reason,
                skill_focus="fluency",
            )
        else:
            target = weak_clusters[0]["cluster"] if weak_clusters else "general"
            recommendation = LearningRecommendation(
                "learn_new_word",
                target,
                decision.reason,
                skill_focus="vocabulary",
            )
        return await self._finalize_recommendation(user_id, recommendation, adaptation)

    def _rolling_success_rate(self, previous_success: float, previous_reviews: int, response_accuracy: float) -> float:
        total = (max(0.0, previous_success) * max(0, previous_reviews)) + response_accuracy
        return round(total / max(1, previous_reviews + 1), 4)

    def _review_multiplier(self, profile) -> float:
        preference = (getattr(profile, "difficulty_preference", "medium") or "medium").lower()
        if preference == "easy":
            return 0.9
        if preference == "hard":
            return 1.1
        return 1.0
