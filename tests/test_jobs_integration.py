from types import SimpleNamespace

from vocablens.infrastructure.observability.token_tracker import add_tokens
from vocablens.infrastructure.jobs.tasks import embedding as embedding_task
from vocablens.infrastructure.jobs.tasks import enrichment as enrichment_task


class FakeUsageLogsRepo:
    def __init__(self):
        self.logged = []

    async def log(self, user_id: int, endpoint: str, tokens: int, success: bool = True):
        self.logged.append(
            {
                "user_id": user_id,
                "endpoint": endpoint,
                "tokens": tokens,
                "success": success,
            }
        )


class FakeVocabRepo:
    def __init__(self):
        self.updates = []

    async def update_enrichment(self, item_id, example_source, example_translated, grammar, cluster):
        self.updates.append(
            {
                "item_id": item_id,
                "example_source": example_source,
                "example_translated": example_translated,
                "grammar": grammar,
                "cluster": cluster,
            }
        )


class FakeJobUOW:
    def __init__(self, usage_logs=None, vocab=None):
        self.usage_logs = usage_logs or FakeUsageLogsRepo()
        self.vocab = vocab or FakeVocabRepo()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self):
        return None


def test_embedding_job_executes_async_path_and_logs_usage(monkeypatch):
    usage_logs = FakeUsageLogsRepo()
    uow = FakeJobUOW(usage_logs=usage_logs)
    stored = {}

    class FakeEmbeddingService:
        def __init__(self, repo):
            self.repo = repo

        async def embed(self, word: str):
            add_tokens(13)
            return [0.1, 0.2, 0.3]

        async def store_embedding(self, word: str, vector):
            stored["word"] = word
            stored["vector"] = vector

    monkeypatch.setattr(embedding_task, "PostgresEmbeddingRepository", lambda session_maker: object())
    monkeypatch.setattr(embedding_task, "EmbeddingService", FakeEmbeddingService)
    monkeypatch.setattr(
        "vocablens.infrastructure.unit_of_work.UnitOfWorkFactory",
        lambda session_maker: (lambda: uow),
    )

    embedding_task.generate_embedding.run("hola", user_id=7)

    assert stored == {"word": "hola", "vector": [0.1, 0.2, 0.3]}
    assert usage_logs.logged == [
        {
            "user_id": 7,
            "endpoint": "job:generate_embedding",
            "tokens": 13,
            "success": True,
        }
    ]


def test_enrichment_job_executes_and_persists_usage(monkeypatch):
    usage_logs = FakeUsageLogsRepo()
    vocab = FakeVocabRepo()
    uow = FakeJobUOW(usage_logs=usage_logs, vocab=vocab)

    class FakeExampleSentenceService:
        def __init__(self, llm):
            self.llm = llm

        async def generate_example(self, source_text: str, source_lang: str, target_lang: str):
            add_tokens(9)
            return {
                "source_sentence": f"{source_text} example",
                "translated_sentence": "translated example",
            }

    class FakeGrammarExplanationService:
        def __init__(self, llm):
            self.llm = llm

        async def explain(self, sentence: str, source_lang: str, target_lang: str):
            add_tokens(4)
            return "Grammar explanation"

    class FakeSemanticClusterService:
        def __init__(self, llm):
            self.llm = llm

        async def cluster_word(self, source_text: str, source_lang: str):
            return "travel"

    monkeypatch.setattr(enrichment_task, "OpenAIProvider", lambda: object())
    monkeypatch.setattr(enrichment_task, "ExampleSentenceService", FakeExampleSentenceService)
    monkeypatch.setattr(enrichment_task, "GrammarExplanationService", FakeGrammarExplanationService)
    monkeypatch.setattr(enrichment_task, "SemanticClusterService", FakeSemanticClusterService)
    monkeypatch.setattr(enrichment_task, "UnitOfWorkFactory", lambda session_maker: (lambda: uow))

    enrichment_task.enrich_vocabulary_item.run(
        user_id=5,
        item_id=22,
        source_text="bonjour",
        source_lang="fr",
        target_lang="en",
    )

    assert vocab.updates == [
        {
            "item_id": 22,
            "example_source": "bonjour example",
            "example_translated": "translated example",
            "grammar": "Grammar explanation",
            "cluster": "travel",
        }
    ]
    assert usage_logs.logged == [
        {
            "user_id": 5,
            "endpoint": "job:enrich_vocabulary",
            "tokens": 13,
            "success": True,
        }
    ]
