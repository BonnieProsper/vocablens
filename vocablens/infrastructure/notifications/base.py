from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NotificationMessage:
    user_id: int
    category: str
    title: str
    body: str
    metadata: dict | None = None


class NotificationSink(Protocol):
    async def send(self, message: NotificationMessage) -> None:
        ...


class NullNotificationSink:
    async def send(self, message: NotificationMessage) -> None:
        return None


class CompositeNotificationSink:
    def __init__(self, *sinks: NotificationSink):
        self._sinks = [sink for sink in sinks if sink is not None]

    async def send(self, message: NotificationMessage) -> None:
        for sink in self._sinks:
            await sink.send(message)
