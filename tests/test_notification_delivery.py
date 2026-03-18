from vocablens.infrastructure.notifications.base import NotificationMessage
from vocablens.infrastructure.notifications.webhook_notifier import WebhookNotificationSink
from tests.conftest import run_async


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeAsyncClient:
    last_request = None

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, json):
        FakeAsyncClient.last_request = {"url": url, "json": json, "timeout": self.timeout}
        return FakeResponse()


def test_webhook_notification_sink_posts_outbound_payload(monkeypatch):
    monkeypatch.setattr("vocablens.infrastructure.notifications.webhook_notifier.httpx.AsyncClient", FakeAsyncClient)
    sink = WebhookNotificationSink("https://example.test/notify", timeout=2.5)

    run_async(
        sink.send(
            NotificationMessage(
                user_id=5,
                category="retention:quick_session",
                title="Quick session suggestion",
                body="Come back for a 3 minute review.",
                metadata={"state": "at-risk"},
            )
        )
    )

    assert FakeAsyncClient.last_request["url"] == "https://example.test/notify"
    assert FakeAsyncClient.last_request["json"]["user_id"] == 5
    assert FakeAsyncClient.last_request["json"]["metadata"]["state"] == "at-risk"
