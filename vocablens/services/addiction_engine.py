from __future__ import annotations

import hashlib
from dataclasses import dataclass

from vocablens.core.time import utc_now
from vocablens.services.habit_engine import HabitEngine
from vocablens.services.notification_decision_engine import NotificationDecisionEngine
from vocablens.services.progress_service import ProgressService
from vocablens.services.retention_engine import RetentionEngine


@dataclass(frozen=True)
class AddictionLoopPlan:
    trigger: dict
    action: dict
    reward: dict
    pressure: dict
    identity: dict
    ritual: dict


class AddictionEngine:
    def __init__(
        self,
        habit_engine: HabitEngine,
        retention_engine: RetentionEngine,
        notification_engine: NotificationDecisionEngine,
        progress_service: ProgressService,
    ):
        self._habit = habit_engine
        self._retention = retention_engine
        self._notifications = notification_engine
        self._progress = progress_service

    async def execute(self, user_id: int) -> AddictionLoopPlan:
        habit = await self._habit.execute(user_id)
        retention = await self._retention.assess_user(user_id)
        progress = await self._progress.build_dashboard(user_id)
        notification = await self._notifications.decide(user_id, retention)

        reward = self._variable_reward(user_id, retention.current_streak, habit.reward, progress)
        pressure = self._loss_aversion(retention, progress)
        identity = self._identity_reinforcement(progress)
        ritual = self._ritual_hook(notification, retention)

        return AddictionLoopPlan(
            trigger=habit.trigger,
            action=habit.action,
            reward=reward,
            pressure=pressure,
            identity=identity,
            ritual=ritual,
        )

    def _variable_reward(self, user_id: int, streak: int, reward: dict, progress: dict) -> dict:
        progress_gain = int(reward.get("progress_increase", 0) or 0)
        ordinal = utc_now().date().toordinal()
        digest = hashlib.sha256(f"{user_id}:{ordinal}:{streak}:{progress_gain}".encode("utf-8")).digest()
        bucket = digest[0] % 3
        reward_type = ("bonus_xp", "surprise_streak_boost", "mystery_reward")[bucket]
        xp_bonus = (digest[1] % 11) + 5
        streak_bonus = 1 if reward_type == "surprise_streak_boost" else 0
        return {
            "type": reward_type,
            "bonus_xp": xp_bonus,
            "surprise_streak_boost": streak_bonus,
            "progress_increase": reward.get("progress_increase", 0),
            "feedback": reward.get("feedback"),
        }

    def _loss_aversion(self, retention, progress: dict) -> dict:
        stale_hours = (
            (utc_now() - retention.last_active_at).total_seconds() / 3600
            if getattr(retention, "last_active_at", None) is not None
            else 999.0
        )
        risk = float(getattr(retention, "drop_off_risk", 0.0) or 0.0)
        trigger_warning = retention.current_streak > 0 and (risk >= 0.45 or stale_hours >= 20)
        progress_loss = max(
            int(progress.get("due_reviews", 0) or 0),
            int(progress.get("daily", {}).get("words_learned", 0) or 0),
        )
        return {
            "show_streak_decay_warning": trigger_warning,
            "will_lose_progress": trigger_warning and progress_loss > 0,
            "warning_message": (
                f"Come back today or you will lose progress on {progress_loss} learning step(s)."
                if trigger_warning
                else ""
            ),
        }

    def _identity_reinforcement(self, progress: dict) -> dict:
        fluency = float(progress.get("metrics", {}).get("fluency_score", 0.0) or 0.0)
        accuracy = float(progress.get("metrics", {}).get("accuracy_rate", 0.0) or 0.0)
        message = (
            "You are becoming fluent."
            if fluency >= 60 or accuracy >= 75
            else "You are building the habits of a fluent speaker."
        )
        return {
            "message": message,
            "identity_state": "becoming_fluent",
        }

    def _ritual_hook(self, notification, retention) -> dict:
        send_at = getattr(notification, "send_at", None)
        ritual_hour = send_at.hour if send_at is not None else 18
        return {
            "daily_ritual_hour": ritual_hour,
            "daily_ritual_message": f"Make this your daily ritual around {ritual_hour:02d}:00.",
            "streak_anchor": retention.current_streak + 1,
        }
