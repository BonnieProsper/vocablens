from vocablens.core.time import utc_now
from vocablens.infrastructure.unit_of_work import UnitOfWork
from vocablens.services.learning_engine import LearningEngine
from vocablens.services.learning_roadmap_service import LearningRoadmapService
from vocablens.services.retention_engine import RetentionEngine
from vocablens.services.subscription_service import SubscriptionService


class FrontendService:
    """
    Aggregates frontend-facing data to reduce client round trips.
    """

    def __init__(
        self,
        uow_factory: type[UnitOfWork],
        learning_engine: LearningEngine,
        roadmap_service: LearningRoadmapService,
        retention_engine: RetentionEngine,
        subscription_service: SubscriptionService,
    ):
        self._uow_factory = uow_factory
        self._learning_engine = learning_engine
        self._roadmap = roadmap_service
        self._retention = retention_engine
        self._subscriptions = subscription_service

    async def dashboard(self, user_id: int) -> dict:
        async with self._uow_factory() as uow:
            vocab = await uow.vocab.list_all(user_id, limit=1000, offset=0)
            due = await uow.vocab.list_due(user_id)
            skills = await uow.skill_tracking.latest_scores(user_id)
            weak_clusters = await uow.knowledge_graph.get_weak_clusters(user_id)
            profile = await uow.profiles.get_or_create(user_id)
            mistakes = await uow.mistake_patterns.top_patterns(user_id, limit=5)
            await uow.commit()

        features = await self._subscriptions.get_features(user_id)
        recommendation = await self._learning_engine.recommend(user_id)
        roadmap = await self._roadmap.generate_today_plan(user_id)
        retention = await self._retention.assess_user(user_id)

        return {
            "progress": {
                "vocabulary_total": len(vocab),
                "due_reviews": len(due),
                "streak": retention.current_streak,
                "session_frequency": retention.session_frequency,
                "retention_state": retention.state,
            },
            "subscription": {
                "tier": features.tier,
                "tutor_depth": features.tutor_depth,
                "explanation_quality": features.explanation_quality,
                "personalization_level": features.personalization_level,
            },
            "skills": skills,
            "next_action": {
                "action": recommendation.action,
                "target": recommendation.target,
                "reason": recommendation.reason,
                "difficulty": recommendation.lesson_difficulty,
                "content_type": recommendation.content_type,
            },
            "retention": {
                "state": retention.state,
                "drop_off_risk": retention.drop_off_risk,
                "actions": [
                    {"kind": action.kind, "reason": action.reason, "target": action.target}
                    for action in retention.suggested_actions
                ],
            },
            "weak_areas": {
                "clusters": weak_clusters,
                "mistakes": [
                    {
                        "category": getattr(pattern, "category", None),
                        "pattern": getattr(pattern, "pattern", None),
                        "count": getattr(pattern, "count", None),
                    }
                    for pattern in mistakes
                ],
            },
            "roadmap": roadmap,
        }

    async def recommendations(self, user_id: int) -> dict:
        recommendation = await self._learning_engine.recommend(user_id)
        retention = await self._retention.assess_user(user_id)
        return {
            "next_action": {
                "action": recommendation.action,
                "target": recommendation.target,
                "reason": recommendation.reason,
                "difficulty": recommendation.lesson_difficulty,
                "content_type": recommendation.content_type,
            },
            "retention_actions": [
                {"kind": action.kind, "reason": action.reason, "target": action.target}
                for action in retention.suggested_actions
            ],
        }

    async def weak_areas(self, user_id: int) -> dict:
        async with self._uow_factory() as uow:
            weak_clusters = await uow.knowledge_graph.get_weak_clusters(user_id)
            skills = await uow.skill_tracking.latest_scores(user_id)
            mistakes = await uow.mistake_patterns.top_patterns(user_id, limit=5)
            await uow.commit()

        sorted_skills = sorted(skills.items(), key=lambda item: item[1])
        return {
            "weak_skills": [{"skill": name, "score": score} for name, score in sorted_skills[:3]],
            "weak_clusters": weak_clusters,
            "mistake_patterns": [
                {
                    "category": getattr(pattern, "category", None),
                    "pattern": getattr(pattern, "pattern", None),
                    "count": getattr(pattern, "count", None),
                }
                for pattern in mistakes
            ],
        }

    def meta(self, *, source: str, difficulty: str | None = None, next_action: str | None = None) -> dict:
        meta = {
            "source": source,
            "generated_at": utc_now().isoformat(),
        }
        if difficulty:
            meta["difficulty"] = difficulty
        if next_action:
            meta["next_action"] = next_action
        return meta
