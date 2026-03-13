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
)


@celery_app.task
def ping():
    return "pong"
