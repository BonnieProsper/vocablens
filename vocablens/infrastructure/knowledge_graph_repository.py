from collections import defaultdict
from typing import Dict, List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vocablens.domain.models import VocabularyItem
from vocablens.infrastructure.db.models import KnowledgeGraphEdgeORM, VocabularyORM


class KnowledgeGraphRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def replace_user_edges(self, user_id: int, edges: List[Dict]) -> None:
        await self.session.execute(
            delete(KnowledgeGraphEdgeORM).where(KnowledgeGraphEdgeORM.user_id == user_id)
        )
        if not edges:
            return
        payload = []
        for edge in edges:
            row = dict(edge)
            row["user_id"] = user_id
            payload.append(row)
        await self.session.execute(KnowledgeGraphEdgeORM.__table__.insert(), payload)

    async def list_edges(self, user_id: int) -> List[KnowledgeGraphEdgeORM]:
        result = await self.session.execute(
            select(KnowledgeGraphEdgeORM).where(KnowledgeGraphEdgeORM.user_id == user_id)
        )
        return result.scalars().all()

    async def list_clusters(self, user_id: int) -> Dict[str, Dict[str, List[str] | int | float]]:
        edges = await self.list_edges(user_id)
        clusters: dict[str, dict] = {}
        for edge in edges:
            if edge.relation_type != "word->topic":
                continue
            bucket = clusters.setdefault(
                edge.target_node,
                {"words": [], "related_words": [], "grammar_links": [], "score": 0.0},
            )
            bucket["words"].append(edge.source_node)

        related_by_cluster = defaultdict(set)
        grammar_by_cluster = defaultdict(set)
        for edge in edges:
            if edge.relation_type == "cluster->word":
                related_by_cluster[edge.source_node].add(edge.target_node)
            elif edge.relation_type == "cluster->grammar":
                grammar_by_cluster[edge.source_node].add(edge.target_node)

        for cluster_name, bucket in clusters.items():
            bucket["words"] = sorted(set(bucket["words"]))
            bucket["related_words"] = sorted(related_by_cluster.get(cluster_name, set()))
            bucket["grammar_links"] = sorted(grammar_by_cluster.get(cluster_name, set()))
            bucket["score"] = float(len(bucket["words"]))
        return clusters

    async def get_weak_clusters(self, user_id: int, limit: int = 3) -> List[Dict]:
        result = await self.session.execute(
            select(VocabularyORM).where(VocabularyORM.user_id == user_id)
        )
        items = [self._map_vocab(row) for row in result.scalars().all()]
        by_cluster: dict[str, list[VocabularyItem]] = defaultdict(list)
        for item in items:
            by_cluster[item.semantic_cluster or "general"].append(item)

        weak_clusters: list[dict] = []
        for cluster, words in by_cluster.items():
            if not words:
                continue
            due_count = sum(1 for item in words if item.next_review_due is not None)
            low_ease = sum(1 for item in words if item.ease_factor < 2.0)
            low_repetition = sum(1 for item in words if item.repetitions < 2)
            weakness = ((due_count * 1.2) + low_ease + (low_repetition * 0.7)) / max(1, len(words))
            weak_clusters.append(
                {
                    "cluster": cluster,
                    "weakness": round(float(weakness), 3),
                    "words": [item.source_text for item in words[:6]],
                }
            )

        weak_clusters.sort(key=lambda item: (-item["weakness"], item["cluster"]))
        return weak_clusters[:limit]

    def _map_vocab(self, row: VocabularyORM) -> VocabularyItem:
        return VocabularyItem(
            id=row.id,
            source_text=row.source_text,
            translated_text=row.translated_text,
            source_lang=row.source_lang,
            target_lang=row.target_lang,
            created_at=row.created_at,
            last_reviewed_at=row.last_reviewed_at,
            review_count=row.review_count,
            ease_factor=row.ease_factor,
            interval=row.interval,
            repetitions=row.repetitions,
            next_review_due=row.next_review_due,
            example_source_sentence=row.example_source_sentence,
            example_translated_sentence=row.example_translated_sentence,
            grammar_note=row.grammar_note,
            semantic_cluster=row.semantic_cluster,
        )
