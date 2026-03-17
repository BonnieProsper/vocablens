from datetime import datetime
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from vocablens.infrastructure.db.models import UserProfileORM


class PostgresUserProfileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int) -> UserProfileORM:
        result = await self.session.execute(
            select(UserProfileORM).where(UserProfileORM.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            return profile
        await self.session.execute(
            insert(UserProfileORM).values(user_id=user_id)
        )
        await self.session.commit()
        result = await self.session.execute(
            select(UserProfileORM).where(UserProfileORM.user_id == user_id)
        )
        return result.scalar_one()

    async def update(
        self,
        user_id: int,
        learning_speed: float | None = None,
        retention_rate: float | None = None,
        difficulty_preference: str | None = None,
        content_preference: str | None = None,
    ):
        values = {"updated_at": datetime.utcnow()}
        if learning_speed is not None:
            values["learning_speed"] = learning_speed
        if retention_rate is not None:
            values["retention_rate"] = retention_rate
        if difficulty_preference is not None:
            values["difficulty_preference"] = difficulty_preference
        if content_preference is not None:
            values["content_preference"] = content_preference
        await self.session.execute(
            update(UserProfileORM)
            .where(UserProfileORM.user_id == user_id)
            .values(**values)
        )
