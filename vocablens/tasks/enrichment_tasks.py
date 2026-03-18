from vocablens.worker import celery
from vocablens.infrastructure.jobs.tasks.enrichment import enrich_vocabulary_item as enrich_vocabulary_job


@celery.task
def enrich_vocabulary_item(
    item_id: int,
    source_text: str,
    source_lang: str,
    target_lang: str,
):
    return enrich_vocabulary_job(
        None,
        None,
        item_id,
        source_text,
        source_lang,
        target_lang,
    )
