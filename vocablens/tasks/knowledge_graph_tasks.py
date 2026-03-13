from vocablens.tasks.celery_app import celery_app


@celery_app.task(name="kg.enrich")
def kg_enrichment_task(user_id: int, words: list[str]):
    # Placeholder for future wiring.
    return {"user_id": user_id, "words": words}
