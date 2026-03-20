from vocablens.core.time import utc_now
from vocablens.infrastructure.unit_of_work import UnitOfWork
from vocablens.services.global_decision_engine import GlobalDecisionEngine
from vocablens.services.learning_engine import LearningEngine
from vocablens.services.learning_roadmap_service import LearningRoadmapService
from vocablens.services.onboarding_service import OnboardingService
from vocablens.services.paywall_service import PaywallService
from vocablens.services.progress_service import ProgressService
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
        paywall_service: PaywallService | None = None,
        progress_service: ProgressService | None = None,
        global_decision_engine: GlobalDecisionEngine | None = None,
        onboarding_service: OnboardingService | None = None,
    ):
        self._uow_factory = uow_factory
        self._learning_engine = learning_engine
        self._roadmap = roadmap_service
        self._retention = retention_engine
        self._subscriptions = subscription_service
        self._paywall = paywall_service
        self._progress = progress_service
        self._global_decision = global_decision_engine
        self._onboarding = onboarding_service

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
        paywall = await self._paywall.evaluate(user_id) if self._paywall else None
        decision = await self._global_decision.decide(user_id) if self._global_decision else None
        onboarding = await self._onboarding.plan(user_id) if self._onboarding else None
        progress = await self._progress.build_dashboard(user_id) if self._progress else {
            "vocabulary_total": len(vocab),
            "due_reviews": len(due),
            "metrics": {},
            "daily": {},
            "weekly": {},
            "trends": {},
            "skill_breakdown": {},
        }

        return {
            "progress": {
                "vocabulary_total": progress["vocabulary_total"],
                "due_reviews": progress["due_reviews"],
                "streak": retention.current_streak,
                "session_frequency": retention.session_frequency,
                "retention_state": retention.state,
                "metrics": progress["metrics"],
                "daily": progress["daily"],
                "weekly": progress["weekly"],
                "trends": progress["trends"],
                "skill_breakdown": progress["skill_breakdown"],
            },
            "subscription": {
                "tier": features.tier,
                "tutor_depth": features.tutor_depth,
                "explanation_quality": features.explanation_quality,
                "personalization_level": features.personalization_level,
                "trial_active": features.trial_active,
                "trial_ends_at": features.trial_ends_at.isoformat() if getattr(features.trial_ends_at, "isoformat", None) else None,
                "usage_percent": features.usage_percent,
            },
            "paywall": {
                "show": paywall.show_paywall if paywall else False,
                "type": paywall.paywall_type if paywall else None,
                "reason": paywall.reason if paywall else None,
                "usage_percent": paywall.usage_percent if paywall else features.usage_percent,
                "allow_access": paywall.allow_access if paywall else True,
                "trial_active": paywall.trial_active if paywall else features.trial_active,
                "trial_ends_at": paywall.trial_ends_at.isoformat() if paywall and getattr(paywall.trial_ends_at, "isoformat", None) else None,
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
            "ui": self._ui_directives(retention, paywall, progress, onboarding),
            "session_config": self._session_config(decision, recommendation),
            "emotion_hooks": self._emotion_hooks(retention, paywall, progress, decision, onboarding),
            "roadmap": roadmap,
        }

    async def recommendations(self, user_id: int) -> dict:
        recommendation = await self._learning_engine.recommend(user_id)
        retention = await self._retention.assess_user(user_id)
        paywall = await self._paywall.evaluate(user_id) if self._paywall else None
        decision = await self._global_decision.decide(user_id) if self._global_decision else None
        onboarding = await self._onboarding.plan(user_id) if self._onboarding else None
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
            "paywall": {
                "show": paywall.show_paywall if paywall else False,
                "type": paywall.paywall_type if paywall else None,
                "reason": paywall.reason if paywall else None,
                "usage_percent": paywall.usage_percent if paywall else 0,
                "trial_active": paywall.trial_active if paywall else False,
            },
            "ui": self._ui_directives(retention, paywall, {}, onboarding),
            "session_config": self._session_config(decision, recommendation),
            "emotion_hooks": self._emotion_hooks(retention, paywall, {}, decision, onboarding),
        }

    async def paywall(self, user_id: int) -> dict:
        paywall = await self._paywall.evaluate(user_id) if self._paywall else None
        if not paywall:
            return {
                "show": False,
                "type": None,
                "reason": None,
                "usage_percent": 0,
                "trial_active": False,
                "allow_access": True,
            }
        return {
            "show": paywall.show_paywall,
            "type": paywall.paywall_type,
            "reason": paywall.reason,
            "usage_percent": paywall.usage_percent,
            "request_usage_percent": paywall.request_usage_percent,
            "token_usage_percent": paywall.token_usage_percent,
            "trial_active": paywall.trial_active,
            "trial_tier": paywall.trial_tier,
            "trial_ends_at": paywall.trial_ends_at.isoformat() if getattr(paywall.trial_ends_at, "isoformat", None) else None,
            "allow_access": paywall.allow_access,
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

    def _ui_directives(self, retention, paywall, progress: dict, onboarding) -> dict:
        daily = progress.get("daily", {}) if progress else {}
        progress_jump = int(daily.get("words_learned", 0) or 0) + int(daily.get("reviews_completed", 0) or 0)
        onboarding_stage = getattr(onboarding, "stage", None)
        return {
            "show_streak_animation": retention.current_streak > 0 or bool(getattr(onboarding, "habit_hook", {}).get("show_streak_starting", False)),
            "show_progress_boost": progress_jump > 0 or bool(getattr(onboarding, "habit_hook", {}).get("show_progress_jump", False)),
            "show_paywall": bool(paywall.show_paywall) if paywall else False,
            "show_celebration": onboarding_stage in {"first_success", "wow_moment", "habit_hook"},
        }

    def _session_config(self, decision, recommendation) -> dict:
        primary = getattr(decision, "primary_action", None)
        mode = (
            "chat" if primary == "conversation"
            else "review" if primary == "review"
            else "drill" if primary in {"learn", "upsell", "nudge"} and getattr(recommendation, "action", "") != "conversation_drill"
            else "chat"
        )
        session_type = getattr(decision, "session_type", "quick")
        session_length = 3 if session_type == "quick" else 8 if session_type == "deep" else 1
        return {
            "session_length": session_length,
            "difficulty": getattr(decision, "difficulty_level", getattr(recommendation, "lesson_difficulty", "medium")),
            "mode": "review" if getattr(recommendation, "action", None) == "review_word" else "chat" if getattr(recommendation, "action", None) == "conversation_drill" else mode,
        }

    def _emotion_hooks(self, retention, paywall, progress: dict, decision, onboarding) -> dict:
        daily = progress.get("daily", {}) if progress else {}
        progress_gain = int(daily.get("words_learned", 0) or 0) + int(daily.get("reviews_completed", 0) or 0)
        onboarding_stage = getattr(onboarding, "stage", None)
        encouragement = (
            "You are one step away from your first win."
            if onboarding_stage in {"onboarding_start", "guided_learning"}
            else "Your first win is in, keep the momentum going."
            if onboarding_stage in {"first_success", "wow_moment", "habit_hook"}
            else f"Your {retention.current_streak}-day streak is building momentum."
            if retention.current_streak > 0
            else "You are making steady progress."
        )
        urgency = (
            "Finish this quick session before your streak cools off."
            if retention.state in {"at-risk", "churned"}
            else f"{getattr(paywall, 'usage_percent', 0)}% of today’s usage is already used."
            if paywall and getattr(paywall, "show_paywall", False)
            else ""
        )
        reward = (
            "Nice start, your streak just began."
            if onboarding_stage == "habit_hook"
            else "That was a strong first success."
            if onboarding_stage in {"first_success", "wow_moment"}
            else f"Complete this session to add {progress_gain or 1} visible progress step(s)."
        )
        return {
            "encouragement_message": encouragement,
            "urgency_message": urgency,
            "reward_message": reward,
        }
