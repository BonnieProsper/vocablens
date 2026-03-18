from datetime import datetime
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from vocablens.infrastructure.db.models import ConversationHistoryORM


class PostgresConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_turn(self, user_id: int, role: str, message: str, created_at: datetime | None = None):
        await self.session.execute(
            insert(ConversationHistoryORM).values(
                user_id=user_id,
                role=role,
                message=message,
                created_at=created_at or datetime.utcnow(),
            )
        )
        await self.session.commit()
