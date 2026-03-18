import httpx

from vocablens.config.settings import settings
from vocablens.infrastructure.notifications.base import NotificationMessage
from vocablens.infrastructure.resilience import async_retry


class WebhookNotificationSink:
    """
    Outbound notification backend for external delivery systems.
    """

    def __init__(self, webhook_url: str, timeout: float | None = None):
        self._webhook_url = webhook_url
        self._timeout = timeout or settings.NOTIFICATION_TIMEOUT

    async def send(self, message: NotificationMessage) -> None:
        payload = {
            "user_id": message.user_id,
            "category": message.category,
            "title": message.title,
            "body": message.body,
            "metadata": message.metadata or {},
        }

        async def _post():
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._webhook_url, json=payload)
                response.raise_for_status()

        await async_retry(
            name="notification_webhook",
            func=_post,
            attempts=max(1, settings.NOTIFICATION_MAX_RETRIES),
            backoff_base=0.5,
        )
