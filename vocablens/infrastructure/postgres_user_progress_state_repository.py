from __future__ import annotations

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vocablens.core.time import utc_now
from vocablens.domain.models import UserProgressState
from vocablens.infrastructure.db.models import UserProgressStateORM


def _map_row(row: UserProgressStateORM) -> UserProgressState:
    return UserProgressState(
        user_id=row.user_id,
        xp=int(row.xp or 0),
        level=int(row.level or 1),
        milestones=list(row.milestones or []),
        updated_at=row.updated_at,
    )


class PostgresUserProgressStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int) -> UserProgressState:
        result = await self.session.execute(
            select(UserProgressStateORM).where(UserProgressStateORM.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            await self.session.execute(insert(UserProgressStateORM).values(user_id=user_id))
            await self.session.flush()
            result = await self.session.execute(
                select(UserProgressStateORM).where(UserProgressStateORM.user_id == user_id)
            )
            row = result.scalar_one()
        return _map_row(row)

    async def update(
        self,
        user_id: int,
        *,
        xp: int | None = None,
        level: int | None = None,
        milestones: list[int] | None = None,
    ) -> UserProgressState:
        await self.get_or_create(user_id)
        values: dict[str, object] = {"updated_at": utc_now()}
        if xp is not None:
            values["xp"] = int(xp)
        if level is not None:
            values["level"] = int(level)
        if milestones is not None:
            values["milestones"] = list(milestones)
        await self.session.execute(
            update(UserProgressStateORM)
            .where(UserProgressStateORM.user_id == user_id)
            .values(**values)
        )
        result = await self.session.execute(
            select(UserProgressStateORM).where(UserProgressStateORM.user_id == user_id)
        )
        return _map_row(result.scalar_one())
