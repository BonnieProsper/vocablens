from pathlib import Path

from vocablens.worker import celery

from vocablens.providers.llm.openai_provider import OpenAIProvider
from vocablens.infrastructure.repositories import SQLiteVocabularyRepository

from vocablens.services.example_sentence_service import ExampleSentenceService
from vocablens.services.grammar_service import GrammarExplanationService
from vocablens.services.semantic_cluster_service import SemanticClusterService


@celery.task
def enrich_vocabulary_item(
    item_id: int,
    source_text: str,
    source_lang: str,
    target_lang: str,
):

    db_path = Path("vocablens.db")

    repo = SQLiteVocabularyRepository(db_path)

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

    repo.update_enrichment(
        item_id,
        example.get("source_sentence"),
        example.get("translated_sentence"),
        grammar,
        cluster,
    )