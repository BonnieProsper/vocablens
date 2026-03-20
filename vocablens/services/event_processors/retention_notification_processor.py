from vocablens.infrastructure.notifications.base import NotificationMessage, NotificationSink
from vocablens.core.time import utc_now
from vocablens.services.notification_decision_engine import NotificationDecisionEngine
from vocablens.services.retention_engine import RetentionEngine


class RetentionNotificationProcessor:
    """
    Emits retention nudges through the notification abstraction.
    """

    SUPPORTED = {"conversation_turn", "word_learned", "word_reviewed"}

    def __init__(
        self,
        retention: RetentionEngine,
        notifier: NotificationSink,
        decision_engine: NotificationDecisionEngine,
    ):
        self._retention = retention
        self._notifier = notifier
        self._decision_engine = decision_engine

    def supports(self, event_type: str) -> bool:
        return event_type in self.SUPPORTED

    async def handle(self, event_type: str, user_id: int, payload: dict) -> None:
        assessment = await self._retention.assess_user(user_id)
        if assessment.state == "active" and not assessment.is_high_engagement:
            return
        decision = await self._decision_engine.decide(user_id, assessment)
        if not decision.should_send or not decision.message:
            return
        if decision.send_at > utc_now() + self._send_window():
            return
        message = NotificationMessage(
            user_id=decision.message.user_id,
            category=decision.message.category,
            title=decision.message.title,
            body=decision.message.body,
            metadata={
                **(decision.message.metadata or {}),
                "scheduled_for": decision.send_at.isoformat(),
            },
        )
        await self._notifier.send(message)

    def _send_window(self):
        from datetime import timedelta
        return timedelta(hours=1)
