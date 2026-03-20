from types import SimpleNamespace

from tests.conftest import run_async
from vocablens.core.time import utc_now
from vocablens.services.notification_decision_engine import NotificationDecision
from vocablens.services.event_processors.retention_notification_processor import RetentionNotificationProcessor


class FakeNotifier:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(message)


class FakeRetention:
    def __init__(self, assessment):
        self.assessment = assessment

    async def assess_user(self, user_id: int):
        return self.assessment


class FakeDecisionEngine:
    def __init__(self, decision: NotificationDecision):
        self.decision = decision

    async def decide(self, user_id: int, assessment):
        return self.decision


def test_retention_notification_processor_emits_messages_for_at_risk_users():
    notifier = FakeNotifier()
    assessment = SimpleNamespace(
        state="at-risk",
        is_high_engagement=False,
        drop_off_risk=0.62,
        suggested_actions=[
            SimpleNamespace(kind="quick_session", reason="Usage is declining", target=None),
            SimpleNamespace(kind="review_reminder", reason="3 words are due", target="hola"),
        ],
    )
    decision = NotificationDecision(
        should_send=True,
        send_at=utc_now(),
        channel="push",
        cooldown_until=None,
        message=SimpleNamespace(
            user_id=7,
            category="retention:quick_session",
            title="Quick session suggestion",
            body="Usage is declining",
            metadata={"target": "hola", "priority": 1},
        ),
        reason="retention action selected",
    )
    processor = RetentionNotificationProcessor(FakeRetention(assessment), notifier, FakeDecisionEngine(decision))

    run_async(processor.handle("conversation_turn", 7, {}))

    assert len(notifier.messages) == 1
    assert notifier.messages[0].user_id == 7
    assert notifier.messages[0].category == "retention:quick_session"
    assert notifier.messages[0].metadata["target"] == "hola"
