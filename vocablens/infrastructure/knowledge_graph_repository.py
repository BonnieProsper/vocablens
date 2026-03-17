import asyncio
from typing import List, Dict
from collections import defaultdict

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from vocablens.infrastructure.db.models import KnowledgeGraphEdgeORM


class KnowledgeGraphRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _run(self, coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        else:
            return loop.run_until_complete(coro)  # type: ignore

    async def add_edge(self, source_node: str, target_node: str, relation_type: str, weight: float = 1.0):
        await self.session.execute(
            insert(KnowledgeGraphEdgeORM).values(
                source_node=source_node,
                target_node=target_node,
                relation_type=relation_type,
                weight=weight,
            )
        )
        await self.session.commit()

    async def list_edges(self) -> List[Dict]:
        result = await self.session.execute(select(KnowledgeGraphEdgeORM))
        return [dict(row._mapping) for row in result.all()]

    async def list_clusters(self) -> Dict[str, List[str]]:
        result = await self.session.execute(
            select(KnowledgeGraphEdgeORM).where(
                KnowledgeGraphEdgeORM.relation_type == "word->topic"
            )
        )
        clusters: Dict[str, List[str]] = defaultdict(list)
        for edge in result.scalars().all():
            clusters[edge.target_node].append(edge.source_node)
        return dict(clusters)
