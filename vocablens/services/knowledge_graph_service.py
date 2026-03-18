from collections import defaultdict
from typing import Dict, List

from vocablens.config.settings import settings
from vocablens.infrastructure.cache.redis_cache import LRUCacheBackend, get_cache_backend
from vocablens.infrastructure.unit_of_work import UnitOfWork


class KnowledgeGraphService:
    """
    Maintains user-scoped concept clusters and word relationships.
    """

    def __init__(self, uow_factory: type[UnitOfWork]):
        self._uow_factory = uow_factory
        self.cache = get_cache_backend() if settings.ENABLE_REDIS_CACHE else LRUCacheBackend()

    async def build_graph(self, user_id: int) -> Dict:
        cache_key = self._graph_cache_key(user_id)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        async with self._uow_factory() as uow:
            items = await uow.vocab.list_all(user_id, limit=10000, offset=0)
            edges = self._build_edges(items)
            await uow.knowledge_graph.replace_user_edges(user_id, edges)
            graph = {
                "topics": await uow.knowledge_graph.list_clusters(user_id),
                "weak_clusters": await uow.knowledge_graph.get_weak_clusters(user_id),
            }
            await uow.commit()

        await self.cache.set(cache_key, graph, ttl=settings.KNOWLEDGE_GRAPH_CACHE_TTL)
        await self.cache.set(self._clusters_cache_key(user_id), graph["topics"], ttl=settings.KNOWLEDGE_GRAPH_CACHE_TTL)
        await self.cache.set(self._weak_clusters_cache_key(user_id), graph["weak_clusters"], ttl=settings.KNOWLEDGE_GRAPH_CACHE_TTL)
        return graph

    async def list_clusters(self, user_id: int) -> Dict[str, Dict]:
        cache_key = self._clusters_cache_key(user_id)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
        await self.build_graph(user_id)
        cached = await self.cache.get(cache_key)
        return cached or {}

    async def get_weak_clusters(self, user_id: int) -> List[Dict]:
        cache_key = self._weak_clusters_cache_key(user_id)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
        await self.build_graph(user_id)
        cached = await self.cache.get(cache_key)
        return cached or []

    async def invalidate_user_graph(self, user_id: int) -> None:
        await self.cache.delete(self._graph_cache_key(user_id))
        await self.cache.delete(self._clusters_cache_key(user_id))
        await self.cache.delete(self._weak_clusters_cache_key(user_id))

    async def refresh_user_graph(self, user_id: int) -> Dict:
        await self.invalidate_user_graph(user_id)
        return await self.build_graph(user_id)

    async def recommend_next_cluster(self, user_id: int) -> str | None:
        weak_clusters = await self.get_weak_clusters(user_id)
        if weak_clusters:
            return weak_clusters[0]["cluster"]
        clusters = await self.list_clusters(user_id)
        if not clusters:
            return None
        return min(clusters.items(), key=lambda item: len(item[1].get("words", [])))[0]

    def topic_scenarios(self, topic: str) -> List[str]:
        scenarios = {
            "food": ["restaurant", "ordering coffee", "grocery shopping"],
            "travel": ["airport", "hotel check-in", "asking directions"],
            "shopping": ["buying clothes", "returning items"],
            "emotion": ["talking about feelings", "sharing experiences"],
        }
        return scenarios.get(topic, ["general conversation"])

    def topic_lessons(self, topic: str) -> List[str]:
        lessons = {
            "food": ["ordering phrases", "menu vocabulary"],
            "travel": ["transport vocabulary", "directions"],
            "shopping": ["numbers", "prices", "transactions"],
        }
        return lessons.get(topic, ["general vocabulary"])

    def _build_edges(self, items) -> List[Dict]:
        edges: list[dict] = []
        cluster_words: dict[str, list[str]] = defaultdict(list)
        cluster_grammar: dict[str, set[str]] = defaultdict(set)
        translation_groups: dict[tuple[str, str], list[str]] = defaultdict(list)

        for item in items:
            cluster = (item.semantic_cluster or "general").strip().lower()
            grammar = self._grammar_label(item.grammar_note)
            word = item.source_text.strip().lower()

            cluster_words[cluster].append(word)
            if grammar:
                cluster_grammar[cluster].add(grammar)

            translation_key = (item.translated_text.strip().lower(), item.target_lang.lower())
            translation_groups[translation_key].append(word)

            edges.append(
                {
                    "source_node": word,
                    "target_node": cluster,
                    "relation_type": "word->topic",
                    "weight": 1.0,
                }
            )
            if grammar:
                edges.append(
                    {
                        "source_node": word,
                        "target_node": grammar,
                        "relation_type": "word->grammar",
                        "weight": 0.85,
                    }
                )

        for cluster, words in cluster_words.items():
            unique_words = sorted(set(words))
            for word in unique_words:
                for related in unique_words:
                    if related != word:
                        edges.append(
                            {
                                "source_node": cluster,
                                "target_node": related,
                                "relation_type": "cluster->word",
                                "weight": 0.65,
                            }
                        )
            for grammar in sorted(cluster_grammar.get(cluster, set())):
                edges.append(
                    {
                        "source_node": cluster,
                        "target_node": grammar,
                        "relation_type": "cluster->grammar",
                        "weight": 0.8,
                    }
                )

        for (_, _), words in translation_groups.items():
            unique_words = sorted(set(words))
            if len(unique_words) < 2:
                continue
            for word in unique_words:
                for related in unique_words:
                    if related != word:
                        edges.append(
                            {
                                "source_node": word,
                                "target_node": related,
                                "relation_type": "word->synonym",
                                "weight": 0.75,
                            }
                        )

        return self._dedupe_edges(edges)

    def _grammar_label(self, grammar_note: str | None) -> str | None:
        if not grammar_note:
            return None
        normalized = grammar_note.strip().lower()
        if not normalized:
            return None
        return normalized[:64]

    def _dedupe_edges(self, edges: List[Dict]) -> List[Dict]:
        deduped = {}
        for edge in edges:
            key = (edge["source_node"], edge["target_node"], edge["relation_type"])
            deduped[key] = edge
        return list(deduped.values())

    def _graph_cache_key(self, user_id: int) -> str:
        return f"kg:{user_id}:graph"

    def _clusters_cache_key(self, user_id: int) -> str:
        return f"kg:{user_id}:clusters"

    def _weak_clusters_cache_key(self, user_id: int) -> str:
        return f"kg:{user_id}:weak"
