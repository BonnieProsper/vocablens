from datetime import timedelta
from types import SimpleNamespace

from tests.conftest import run_async
from vocablens.core.time import utc_now
from vocablens.services.daily_loop_service import DailyLoopService


class FakeUOW:
    def __init__(self, events=None, weak_clusters=None, mistakes=None, due_items=None, profile=None):
        self.events = SimpleNamespace(list_by_user=self._list_by_user)
        self.knowledge_graph = SimpleNamespace(get_weak_clusters=self._get_weak_clusters)
        self.mistake_patterns = SimpleNamespace(top_patterns=self._top_patterns)
        self.vocab = SimpleNamespace(list_due=self._list_due)
        self.profiles = SimpleNamespace(get_or_create=self._get_or_create)
        self._events = list(events or [])
        self._weak_clusters = weak_clusters or []
        self._mistakes = mistakes or []
        self._due_items = due_items or []
        self._profile = profile or SimpleNamespace(current_streak=4)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self):
        return None

    async def _list_by_user(self, user_id: int, limit: int = 200):
        return self._events[:limit]

    async def _get_weak_clusters(self, user_id: int, limit: int = 3):
        return self._weak_clusters[:limit]

    async def _top_patterns(self, user_id: int, limit: int = 3):
        return self._mistakes[:limit]

    async def _list_due(self, user_id: int):
        return self._due_items

    async def _get_or_create(self, user_id: int):
        return self._profile


class FakeLearningEngine:
    def __init__(self, recommendation):
        self.recommendation = recommendation

    async def get_next_lesson(self, user_id: int):
        return self.recommendation


class FakeGamificationService:
    def __init__(self, streak=4, xp=120, badges=None):
        self.streak = streak
        self.xp = xp
        self.badges = badges or [SimpleNamespace(label="Accuracy Ace")]

    async def summary(self, user_id: int):
        return SimpleNamespace(
            current_streak=self.streak,
            xp=self.xp,
            badges=self.badges,
        )


class FakeNotificationEngine:
    async def decide(self, user_id: int, assessment):
        return SimpleNamespace(
            should_send=True,
            channel="push",
            send_at=utc_now().replace(hour=18, minute=0, second=0, microsecond=0),
            reason="retention action selected",
        )


class FakeRetentionEngine:
    def __init__(self, *, streak=4, drop_off_risk=0.3):
        self.streak = streak
        self.drop_off_risk = drop_off_risk
        self.recorded = []

    async def assess_user(self, user_id: int):
        return SimpleNamespace(
            current_streak=self.streak,
            drop_off_risk=self.drop_off_risk,
            state="active",
            suggested_actions=[],
        )

    async def record_activity(self, user_id: int, occurred_at=None):
        self.recorded.append((user_id, occurred_at))


class FakeEventService:
    def __init__(self):
        self.calls = []

    async def track_event(self, user_id: int, event_type: str, payload: dict | None = None):
        self.calls.append((user_id, event_type, payload or {}))


def _factory_for(uow):
    return lambda: uow


def _event(event_type: str, days_ago: int = 0):
    return SimpleNamespace(
        event_type=event_type,
        created_at=utc_now() - timedelta(days=days_ago),
    )


def test_daily_loop_service_always_generates_a_mission():
    recommendation = SimpleNamespace(
        action="learn_new_word",
        target="travel",
        reason="Weak cluster",
        lesson_difficulty="medium",
        skill_focus="vocabulary",
    )
    service = DailyLoopService(
        _factory_for(
            FakeUOW(
                events=[_event("session_started", days_ago=1), _event("review_completed", days_ago=2)],
                weak_clusters=[{"cluster": "travel"}],
                due_items=[SimpleNamespace(source_text="hola")],
            )
        ),
        FakeLearningEngine(recommendation),
        FakeGamificationService(),
        FakeNotificationEngine(),
        FakeRetentionEngine(drop_off_risk=0.2),
        FakeEventService(),
    )

    plan = run_async(service.build_daily_loop(1))

    assert len(plan.mission) >= 1
    assert len(plan.mission) <= 3
    assert plan.weak_area == "vocabulary"
    assert plan.mission[0].target == "travel"
    assert plan.notification_preview["should_send"] is True


def test_daily_loop_service_skip_shield_updates_correctly():
    recommendation = SimpleNamespace(
        action="review_word",
        target="hola",
        reason="Due review",
        lesson_difficulty="easy",
        skill_focus="vocabulary",
    )
    event_service = FakeEventService()
    service = DailyLoopService(
        _factory_for(FakeUOW(events=[])),
        FakeLearningEngine(recommendation),
        FakeGamificationService(streak=5),
        FakeNotificationEngine(),
        FakeRetentionEngine(streak=5),
        event_service,
    )

    result = run_async(service.use_skip_shield(1))

    assert result.applied is True
    assert result.streak_preserved is True
    assert result.shields_remaining_this_week == 0
    assert event_service.calls[-1][1] == "skip_shield_used"


def test_daily_loop_service_rewards_trigger_after_completion():
    recommendation = SimpleNamespace(
        action="practice_grammar",
        target="grammar",
        reason="Grammar weak",
        lesson_difficulty="medium",
        skill_focus="grammar",
    )
    retention = FakeRetentionEngine(streak=6)
    event_service = FakeEventService()
    service = DailyLoopService(
        _factory_for(FakeUOW(events=[_event("lesson_completed", days_ago=1)])),
        FakeLearningEngine(recommendation),
        FakeGamificationService(streak=6, xp=200),
        FakeNotificationEngine(),
        retention,
        event_service,
    )

    result = run_async(service.complete_daily_mission(1))

    assert result.completed is True
    assert result.reward_chest_unlocked is True
    assert result.reward_preview["xp_reward"] == 25
    emitted_types = [call[1] for call in event_service.calls]
    assert "daily_mission_completed" in emitted_types
    assert "reward_chest_unlocked" in emitted_types
    assert retention.recorded[0][0] == 1
