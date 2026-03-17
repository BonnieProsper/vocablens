from dataclasses import dataclass
from typing import Protocol, Any, Optional


@dataclass
class RetryPolicy:
    """Retry configuration for a background job."""

    max_attempts: int = 3
    backoff_seconds: float = 5.0


@dataclass
class JobOptions:
    """Common job options."""

    idempotency_key: Optional[str] = None
    retry: RetryPolicy = RetryPolicy()
    metadata: dict[str, Any] | None = None


class JobQueue(Protocol):
    """Abstraction for enqueueing background work."""

    def enqueue(self, name: str, payload: dict, options: JobOptions | None = None) -> str:
        ...
