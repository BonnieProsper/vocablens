from vocablens.tasks.celery_app import celery_app


@celery_app.task(name="translation.translate_batch")
def translate_batch_task(words, source_lang: str, target_lang: str):
    # Placeholder; real wiring will be added later.
    return {"words": words, "source_lang": source_lang, "target_lang": target_lang}
