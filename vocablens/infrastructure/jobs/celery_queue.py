import uuid
from typing import Any

from vocablens.infrastructure.jobs.base import JobOptions, JobQueue, RetryPolicy
from vocablens.infrastructure.jobs.celery_app import celery_app
from vocablens.infrastructure.logging.logger import get_logger


class CeleryJobQueue(JobQueue):
    """Celery-backed JobQueue implementation."""

    def __init__(self):
        self._logger = get_logger("jobs.celery")

    def enqueue(self, name: str, payload: dict[str, Any], options: JobOptions | None = None) -> str:
        opts = options or JobOptions()
        task_id = opts.idempotency_key or str(uuid.uuid4())
        retry_policy = opts.retry or RetryPolicy()

        self._logger.info(
            "enqueue_job",
            extra={
                "name": name,
                "task_id": task_id,
                "payload_keys": list(payload.keys()),
                "retry_max_attempts": retry_policy.max_attempts,
                "retry_backoff_seconds": retry_policy.backoff_seconds,
            },
        )

        async_result = celery_app.send_task(
            name,
            kwargs=payload,
            task_id=task_id,
            retry=True,
            retry_policy={
                "max_retries": retry_policy.max_attempts,
                "interval_start": retry_policy.backoff_seconds,
                "interval_step": retry_policy.backoff_seconds,
            },
        )

        return async_result.id
