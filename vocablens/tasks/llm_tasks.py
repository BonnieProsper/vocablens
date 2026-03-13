from vocablens.tasks.celery_app import celery_app


@celery_app.task(name="llm.generate_drills")
def generate_drills_task(mistakes):
    # Placeholder to be wired later.
    return {"mistakes": mistakes}
