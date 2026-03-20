from datetime import datetime

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from vocablens.infrastructure.db.models import EventORM


class PostgresEventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self,
        *,
        user_id: int,
        event_type: str,
        payload: dict,
        created_at: datetime | None = None,
    ) -> None:
        await self.session.execute(
            insert(EventORM).values(
                user_id=user_id,
                event_type=event_type,
                payload=payload,
                created_at=created_at,
            )
        )

    async def list_by_user(self, user_id: int, limit: int = 1000):
        result = await self.session.execute(
            select(EventORM)
            .where(EventORM.user_id == user_id)
            .order_by(EventORM.created_at.desc(), EventORM.id.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def list_by_type(self, event_type: str, limit: int = 1000):
        result = await self.session.execute(
            select(EventORM)
            .where(EventORM.event_type == event_type)
            .order_by(EventORM.created_at.desc(), EventORM.id.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def list_since(self, since: datetime, event_types: list[str] | None = None, limit: int = 5000):
        query = (
            select(EventORM)
            .where(EventORM.created_at >= since)
            .order_by(EventORM.created_at.asc(), EventORM.id.asc())
            .limit(limit)
        )
        if event_types:
            query = query.where(EventORM.event_type.in_(event_types))
        result = await self.session.execute(query)
        return result.scalars().all()
