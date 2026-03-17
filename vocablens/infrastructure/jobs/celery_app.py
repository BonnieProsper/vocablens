from celery import Celery

from vocablens.config.settings import settings

celery_app = Celery(
    "vocablens",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_ignore_result=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=30,
    task_time_limit=60,
    result_expires=3600,
    broker_transport_options={"visibility_timeout": 3600},
)

# Monitoring hooks
from celery import signals  # noqa: E402
from vocablens.infrastructure.logging.logger import get_logger  # noqa: E402

logger = get_logger("celery")


@signals.task_failure.connect
def _task_failure_handler(sender=None, exception=None, **kwargs):
    logger.error("task_failed", extra={"task": sender.name if sender else None, "error": str(exception)})


@signals.task_success.connect
def _task_success_handler(sender=None, **kwargs):
    logger.info("task_succeeded", extra={"task": sender.name if sender else None})
