from datetime import timedelta
from types import SimpleNamespace

from tests.conftest import run_async
from vocablens.core.time import utc_now
from vocablens.domain.models import VocabularyItem
from vocablens.services.knowledge_graph_service import KnowledgeGraphService


class FakeKnowledgeGraphRepo:
    def __init__(self):
        self.edges = []

    async def replace_user_edges(self, user_id: int, edges):
        self.edges = [dict(edge, user_id=user_id) for edge in edges]

    async def list_clusters(self, user_id: int):
        clusters = {}
        for edge in self.edges:
            if edge["user_id"] != user_id or edge["relation_type"] != "word->topic":
                continue
            bucket = clusters.setdefault(
                edge["target_node"],
                {"words": [], "related_words": [], "grammar_links": [], "score": 0.0},
            )
            bucket["words"].append(edge["source_node"])
        for edge in self.edges:
            if edge["user_id"] != user_id:
                continue
            if edge["relation_type"] == "cluster->word":
                clusters.setdefault(
                    edge["source_node"],
                    {"words": [], "related_words": [], "grammar_links": [], "score": 0.0},
                )["related_words"].append(edge["target_node"])
            if edge["relation_type"] == "cluster->grammar":
                clusters.setdefault(
                    edge["source_node"],
                    {"words": [], "related_words": [], "grammar_links": [], "score": 0.0},
                )["grammar_links"].append(edge["target_node"])
        return clusters

    async def get_weak_clusters(self, user_id: int, limit: int = 3):
        travel_words = [
            edge["source_node"]
            for edge in self.edges
            if edge["user_id"] == user_id and edge["relation_type"] == "word->topic" and edge["target_node"] == "travel"
        ]
        if not travel_words:
            return []
        return [{"cluster": "travel", "weakness": 1.4, "words": travel_words[:3]}]


class FakeUOW:
    def __init__(self, items):
        self.vocab = SimpleNamespace(list_all=self._list_all)
        self.knowledge_graph = FakeKnowledgeGraphRepo()
        self.items = items

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self):
        return None

    async def _list_all(self, user_id: int, limit: int, offset: int):
        return self.items


def test_knowledge_graph_builds_clusters_relationships_and_weak_clusters():
    now = utc_now()
    items = [
        VocabularyItem(
            id=1,
            source_text="bonjour",
            translated_text="hello",
            source_lang="fr",
            target_lang="en",
            created_at=now - timedelta(days=10),
            semantic_cluster="travel",
            grammar_note="greeting",
            ease_factor=1.7,
            repetitions=1,
            interval=2,
            next_review_due=now - timedelta(days=1),
        ),
        VocabularyItem(
            id=2,
            source_text="salut",
            translated_text="hello",
            source_lang="fr",
            target_lang="en",
            created_at=now - timedelta(days=8),
            semantic_cluster="travel",
            grammar_note="greeting",
            ease_factor=1.8,
            repetitions=1,
            interval=2,
            next_review_due=now - timedelta(days=1),
        ),
        VocabularyItem(
            id=3,
            source_text="manger",
            translated_text="eat",
            source_lang="fr",
            target_lang="en",
            created_at=now - timedelta(days=3),
            semantic_cluster="food",
            grammar_note="verb infinitive",
            ease_factor=2.4,
            repetitions=3,
            interval=6,
        ),
    ]
    uow = FakeUOW(items)
    service = KnowledgeGraphService(lambda: uow)

    graph = run_async(service.build_graph(1))
    clusters = run_async(service.list_clusters(1))
    weak_clusters = run_async(service.get_weak_clusters(1))

    assert "travel" in graph["topics"]
    assert sorted(clusters["travel"]["words"]) == ["bonjour", "salut"]
    assert "greeting" in clusters["travel"]["grammar_links"]
    synonym_targets = {
        edge["target_node"]
        for edge in uow.knowledge_graph.edges
        if edge["relation_type"] == "word->synonym" and edge["source_node"] == "bonjour"
    }
    assert "salut" in synonym_targets
    assert weak_clusters[0]["cluster"] == "travel"
