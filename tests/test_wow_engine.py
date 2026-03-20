import json
from datetime import timedelta
from types import SimpleNamespace

from tests.conftest import run_async
from vocablens.core.time import utc_now
from vocablens.services.wow_engine import WowEngine


class FakeLearningEventsRepo:
    def __init__(self, events):
        self.events = events

    async def list_since(self, user_id: int, since):
        return [event for event in self.events if getattr(event, "created_at", utc_now()) >= since]


class FakeUOW:
    def __init__(self, events):
        self.learning_events = FakeLearningEventsRepo(events)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self):
        return None


def test_wow_engine_scores_successful_high_value_session():
    now = utc_now()
    events = [
        SimpleNamespace(
            event_type="word_reviewed",
            payload_json=json.dumps({"response_accuracy": 0.45}),
            created_at=now - timedelta(days=2),
        ),
        SimpleNamespace(
            event_type="word_reviewed",
            payload_json=json.dumps({"response_accuracy": 0.55}),
            created_at=now - timedelta(days=1),
        ),
    ]
    engine = WowEngine(lambda: FakeUOW(events))

    wow = run_async(
        engine.score_session(
            1,
            tutor_mode=True,
            correction_feedback_count=3,
            new_words_count=2,
            grammar_mistake_count=0,
            session_turn_count=5,
            reply_length=160,
        )
    )

    assert wow.score >= 0.8
    assert wow.qualifies is True
    assert wow.triggers["paywall"] is True
    assert wow.triggers["trial"] is True
    assert wow.triggers["upsell"] is True
    assert wow.current_accuracy > wow.baseline_accuracy


def test_wow_engine_keeps_low_value_session_below_threshold():
    now = utc_now()
    events = [
        SimpleNamespace(
            event_type="word_reviewed",
            payload_json=json.dumps({"response_accuracy": 0.8}),
            created_at=now - timedelta(days=1),
        )
    ]
    engine = WowEngine(lambda: FakeUOW(events))

    wow = run_async(
        engine.score_session(
            2,
            tutor_mode=False,
            correction_feedback_count=0,
            new_words_count=0,
            grammar_mistake_count=3,
            session_turn_count=1,
            reply_length=40,
        )
    )

    assert wow.score < 0.4
    assert wow.qualifies is False
    assert wow.triggers["paywall"] is False
    assert wow.triggers["trial"] is False
