from vocablens.tasks.celery_app import celery_app


@celery_app.task(name="speech.transcribe")
def speech_transcribe_task(audio_bytes: bytes, source_lang: str = "auto"):
    # Placeholder for future wiring.
    return {"length": len(audio_bytes), "source_lang": source_lang}
