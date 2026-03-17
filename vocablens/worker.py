from vocablens.infrastructure.jobs.celery_app import celery_app

celery = celery_app
celery.autodiscover_tasks(["vocablens.infrastructure.jobs.tasks"])
