from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vocablens.core.time import utc_now
from vocablens.infrastructure.db.models import ExperimentAssignmentORM


class PostgresExperimentAssignmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int, experiment_key: str):
        result = await self.session.execute(
            select(ExperimentAssignmentORM).where(
                ExperimentAssignmentORM.user_id == user_id,
                ExperimentAssignmentORM.experiment_key == experiment_key,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: int,
        experiment_key: str,
        variant: str,
        assigned_at=None,
    ):
        assignment = ExperimentAssignmentORM(
            user_id=user_id,
            experiment_key=experiment_key,
            variant=variant,
            assigned_at=assigned_at or utc_now(),
        )
        self.session.add(assignment)
        return assignment
