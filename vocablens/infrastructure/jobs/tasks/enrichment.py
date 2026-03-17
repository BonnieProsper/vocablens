from vocablens.infrastructure.jobs.celery_app import celery_app
from vocablens.infrastructure.unit_of_work import UnitOfWorkFactory
from vocablens.infrastructure.db.session import AsyncSessionMaker
from vocablens.providers.llm.openai_provider import OpenAIProvider
from vocablens.services.example_sentence_service import ExampleSentenceService
from vocablens.services.grammar_service import GrammarExplanationService
from vocablens.services.semantic_cluster_service import SemanticClusterService
from vocablens.infrastructure.logging.logger import get_logger
import anyio


logger = get_logger("jobs.enrichment")


@celery_app.task(name="jobs.enrich_vocabulary")
def enrich_vocabulary_item(
    item_id: int,
    source_text: str,
    source_lang: str,
    target_lang: str,
):

    llm = OpenAIProvider()

    sentence_service = ExampleSentenceService(llm)
    grammar_service = GrammarExplanationService(llm)
    cluster_service = SemanticClusterService(llm)

    example = sentence_service.generate_example(
        source_text,
        source_lang,
        target_lang,
    )

    grammar = grammar_service.explain(
        example.get("source_sentence", ""),
        source_lang,
        target_lang,
    )

    cluster = cluster_service.cluster_word(
        source_text,
        source_lang,
    )

    async def _persist():
        factory = UnitOfWorkFactory(AsyncSessionMaker)
        async with factory() as uow:
            await uow.vocab.update_enrichment(
                item_id,
                example.get("source_sentence"),
                example.get("translated_sentence"),
                grammar,
                cluster,
            )
            await uow.commit()

    anyio.run(_persist)

    logger.info(
        "enrichment_completed",
        extra={
            "item_id": item_id,
            "source_text": source_text,
        },
    )
