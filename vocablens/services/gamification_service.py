from __future__ import annotations

from dataclasses import dataclass

from vocablens.infrastructure.unit_of_work import UnitOfWork
from vocablens.services.event_service import EventService
from vocablens.services.progress_service import ProgressService
from vocablens.services.retention_engine import RetentionEngine

STREAK_MILESTONES: tuple[int, ...] = (3, 7, 14, 30, 60, 100)
XP_PER_LEVEL = 250

XP_EVENT_VALUES = {
    "lesson_completed": 50,
    "review_completed": 20,
    "session_started": 10,
    "session_ended": 5,
    "message_sent": 5,
    "mistake_made": 2,
    "subscription_upgraded": 100,
    "upgrade_completed": 100,
    "referral_reward_granted": 0,
    "progress_shared": 15,
    "reward_chest_unlocked": 25,
}


@dataclass(frozen=True)
class Badge:
    key: str
    label: str
    reason: str


@dataclass(frozen=True)
class GamificationProfile:
    xp: int
    level: int
    xp_into_level: int
    xp_to_next_level: int
    current_streak: int
    longest_streak: int
    streak_milestones_reached: list[int]
    next_streak_milestone: int | None
    badges: list[Badge]
    stats: dict[str, float | int]


class GamificationService:
    def __init__(
        self,
        uow_factory: type[UnitOfWork],
        progress_service: ProgressService,
        retention_engine: RetentionEngine,
        event_service: EventService | None = None,
    ):
        self._uow_factory = uow_factory
        self._progress = progress_service
        self._retention = retention_engine
        self._events = event_service

    async def summary(self, user_id: int) -> GamificationProfile:
        async with self._uow_factory() as uow:
            events = await uow.events.list_by_user(user_id, limit=5000)
            await uow.commit()
        progress = await self._progress.build_dashboard(user_id)
        retention = await self._retention.assess_user(user_id)

        xp = self._xp_total(events)
        level = self._level(xp)
        milestones_reached = [milestone for milestone in STREAK_MILESTONES if retention.current_streak >= milestone]
        next_milestone = next((milestone for milestone in STREAK_MILESTONES if milestone > retention.current_streak), None)
        stats = self._stats(events, progress)

        return GamificationProfile(
            xp=xp,
            level=level,
            xp_into_level=xp % XP_PER_LEVEL,
            xp_to_next_level=(XP_PER_LEVEL - (xp % XP_PER_LEVEL)) % XP_PER_LEVEL or XP_PER_LEVEL,
            current_streak=retention.current_streak,
            longest_streak=retention.longest_streak,
            streak_milestones_reached=milestones_reached,
            next_streak_milestone=next_milestone,
            badges=self._badges(stats, progress, retention),
            stats=stats,
        )

    async def refresh(self, user_id: int) -> dict:
        profile = await self.summary(user_id)
        if not self._events:
            return {
                "profile": profile,
                "new_badges": [],
                "new_streak_milestones": [],
            }

        async with self._uow_factory() as uow:
            events = await uow.events.list_by_user(user_id, limit=5000)
            await uow.commit()

        seen_badges = {
            getattr(event, "payload", {}).get("badge")
            for event in events
            if getattr(event, "event_type", None) == "badge_unlocked"
        }
        seen_milestones = {
            int(getattr(event, "payload", {}).get("milestone"))
            for event in events
            if getattr(event, "event_type", None) == "streak_milestone_reached"
            and getattr(event, "payload", {}).get("milestone") is not None
        }

        new_badges = [badge for badge in profile.badges if badge.key not in seen_badges]
        new_milestones = [milestone for milestone in profile.streak_milestones_reached if milestone not in seen_milestones]

        for badge in new_badges:
            await self._events.track_event(
                user_id,
                "badge_unlocked",
                {
                    "badge": badge.key,
                    "label": badge.label,
                    "reason": badge.reason,
                },
            )
        for milestone in new_milestones:
            await self._events.track_event(
                user_id,
                "streak_milestone_reached",
                {
                    "milestone": milestone,
                    "current_streak": profile.current_streak,
                },
            )
        await self._events.track_event(
            user_id,
            "xp_awarded",
            {
                "xp_total": profile.xp,
                "level": profile.level,
            },
        )

        return {
            "profile": profile,
            "new_badges": new_badges,
            "new_streak_milestones": new_milestones,
        }

    def _xp_total(self, events) -> int:
        total = 0
        for event in events:
            event_type = getattr(event, "event_type", None)
            total += XP_EVENT_VALUES.get(event_type, 0)
            if event_type == "referral_reward_granted":
                payload = getattr(event, "payload", {}) or {}
                total += int(payload.get("xp_reward", 0) or 0)
        return total

    def _level(self, xp: int) -> int:
        return max(1, (xp // XP_PER_LEVEL) + 1)

    def _stats(self, events, progress: dict) -> dict[str, float | int]:
        counts = {}
        for event in events:
            key = getattr(event, "event_type", "unknown")
            counts[key] = counts.get(key, 0) + 1
        return {
            "sessions": counts.get("session_started", 0),
            "lessons_completed": counts.get("lesson_completed", 0),
            "reviews_completed": counts.get("review_completed", 0),
            "messages_sent": counts.get("message_sent", 0),
            "progress_shares": counts.get("progress_shared", 0),
            "mastery_percent": float(progress.get("metrics", {}).get("vocabulary_mastery_percent", 0.0) or 0.0),
            "accuracy_rate": float(progress.get("metrics", {}).get("accuracy_rate", 0.0) or 0.0),
            "fluency_score": float(progress.get("metrics", {}).get("fluency_score", 0.0) or 0.0),
        }

    def _badges(self, stats: dict[str, float | int], progress: dict, retention) -> list[Badge]:
        badges: list[Badge] = []
        if int(stats["sessions"]) >= 1:
            badges.append(Badge("first_session", "First Session", "Completed the first learning session."))
        if int(stats["messages_sent"]) >= 10:
            badges.append(Badge("conversation_starter", "Conversation Starter", "Sent 10 tutor messages."))
        if int(stats["lessons_completed"]) >= 5:
            badges.append(Badge("lesson_climber", "Lesson Climber", "Completed 5 lessons."))
        if float(stats["accuracy_rate"]) >= 85.0:
            badges.append(Badge("accuracy_ace", "Accuracy Ace", "Reached 85% accuracy."))
        if float(stats["mastery_percent"]) >= 50.0:
            badges.append(Badge("mastery_builder", "Mastery Builder", "Reached 50% vocabulary mastery."))
        if retention.current_streak >= 3:
            badges.append(Badge("streak_keeper", "Streak Keeper", "Held a 3-day streak."))
        if retention.current_streak >= 7:
            badges.append(Badge("streak_master", "Streak Master", "Held a 7-day streak."))
        if int(stats["progress_shares"]) >= 1:
            badges.append(Badge("share_your_win", "Share Your Win", "Shared progress with someone else."))
        return badges
