from __future__ import annotations

from dataclasses import dataclass

from vocablens.services.global_decision_engine import GlobalDecisionEngine
from vocablens.services.notification_decision_engine import NotificationDecisionEngine
from vocablens.services.progress_service import ProgressService
from vocablens.services.retention_engine import RetentionAssessment, RetentionEngine


@dataclass(frozen=True)
class HabitLoopPlan:
    trigger: dict
    action: dict
    reward: dict
    repeat: dict


class HabitEngine:
    def __init__(
        self,
        retention_engine: RetentionEngine,
        notification_engine: NotificationDecisionEngine,
        progress_service: ProgressService,
        global_decision_engine: GlobalDecisionEngine | None = None,
    ):
        self._retention = retention_engine
        self._notifications = notification_engine
        self._progress = progress_service
        self._global_decision = global_decision_engine

    async def execute(self, user_id: int) -> HabitLoopPlan:
        if self._global_decision:
            return await self._execute_from_global_decision(user_id)
        retention = await self._retention.assess_user(user_id)
        progress = await self._progress.build_dashboard(user_id)
        notification = await self._notifications.decide(user_id, retention)

        trigger = self._trigger(retention, notification)
        action = self._action(retention, progress)
        reward = self._reward(retention, progress, action)
        repeat = self._repeat(retention, trigger, reward)

        return HabitLoopPlan(
            trigger=trigger,
            action=action,
            reward=reward,
            repeat=repeat,
        )

    def _trigger(self, retention: RetentionAssessment, notification) -> dict:
        streak_action = next(
            (action for action in retention.suggested_actions if action.kind == "streak_nudge"),
            None,
        )
        if notification.should_send and notification.message is not None:
            return {
                "type": "notification",
                "channel": notification.channel,
                "send_at": notification.send_at.isoformat(),
                "category": notification.message.category,
                "reason": notification.reason,
                "streak_reminder": bool(streak_action or "streak_nudge" in notification.message.category),
            }
        if streak_action is not None:
            return {
                "type": "streak_reminder",
                "channel": None,
                "send_at": None,
                "category": streak_action.kind,
                "reason": streak_action.reason,
                "streak_reminder": True,
            }
        return {
            "type": "passive_reentry",
            "channel": None,
            "send_at": None,
            "category": "habit_reentry",
            "reason": "No outbound trigger available; surface the next habit action in-app.",
            "streak_reminder": False,
        }

    def _action(self, retention: RetentionAssessment, progress: dict) -> dict:
        quick_session = next(
            (action for action in retention.suggested_actions if action.kind == "quick_session"),
            None,
        )
        if quick_session is not None:
            return {
                "type": "quick_session",
                "duration_minutes": 3,
                "target": quick_session.target or "review",
                "reason": quick_session.reason,
            }
        due_reviews = int(progress.get("due_reviews", 0) or 0)
        focus_area = "review" if due_reviews > 0 else "conversation"
        return {
            "type": "quick_session",
            "duration_minutes": 2,
            "target": focus_area,
            "reason": "Keep the daily habit alive with a low-friction session.",
        }

    def _reward(self, retention: RetentionAssessment, progress: dict, action: dict) -> dict:
        daily = progress.get("daily", {})
        weekly = progress.get("weekly", {})
        trends = progress.get("trends", {})
        metrics = progress.get("metrics", {})
        progress_gain = max(
            int(daily.get("reviews_completed", 0) or 0),
            int(daily.get("words_learned", 0) or 0),
            1 if float(trends.get("weekly_accuracy_rate_delta", 0.0) or 0.0) > 0 else 0,
        )
        return {
            "progress_increase": progress_gain,
            "streak_boost": retention.current_streak + 1,
            "feedback": self._feedback_message(retention, progress_gain, action, metrics, weekly),
        }

    def _repeat(self, retention: RetentionAssessment, trigger: dict, reward: dict) -> dict:
        return {
            "should_repeat": retention.state in {"active", "at-risk"},
            "next_best_trigger": "streak_reminder" if reward["streak_boost"] >= 2 else trigger["type"],
            "cadence": "daily",
        }

    def _feedback_message(
        self,
        retention: RetentionAssessment,
        progress_gain: int,
        action: dict,
        metrics: dict,
        weekly: dict,
    ) -> str:
        accuracy = float(metrics.get("accuracy_rate", 0.0) or 0.0)
        reviews = int(weekly.get("reviews_completed", 0) or 0)
        return (
            f"A {action['duration_minutes']}-minute {action['target']} session can add "
            f"{progress_gain} visible progress step(s), move the streak to {retention.current_streak + 1}, "
            f"and build on {reviews} review(s) this week at {accuracy:.1f}% accuracy."
        )

    async def _execute_from_global_decision(self, user_id: int) -> HabitLoopPlan:
        decision = await self._global_decision.decide(user_id)
        retention = await self._retention.assess_user(user_id)
        progress = await self._progress.build_dashboard(user_id)
        notification = await self._notifications.decide(user_id, retention)
        trigger = self._trigger(retention, notification)
        action = {
            "type": "quick_session",
            "duration_minutes": 3 if decision.session_type == "quick" else 2 if decision.session_type == "passive" else 5,
            "target": decision.primary_action if decision.primary_action in {"learn", "review", "conversation"} else "review",
            "reason": decision.reason,
        }
        reward = self._reward(retention, progress, action)
        repeat = {
            "should_repeat": decision.lifecycle_stage in {"new_user", "activating", "at_risk", "engaged"},
            "next_best_trigger": "streak_reminder" if decision.engagement_action == "streak_push" else "notification",
            "cadence": "daily",
        }
        return HabitLoopPlan(trigger=trigger, action=action, reward=reward, repeat=repeat)
