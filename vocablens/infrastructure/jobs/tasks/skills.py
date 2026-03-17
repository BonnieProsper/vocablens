from vocablens.infrastructure.jobs.celery_app import celery_app
from vocablens.infrastructure.db.session import AsyncSessionMaker
from vocablens.infrastructure.unit_of_work import UnitOfWorkFactory
from vocablens.services.skill_tracking_service import SkillTrackingService
from vocablens.infrastructure.logging.logger import get_logger
import anyio

logger = get_logger("jobs.skills")


@celery_app.task(name="jobs.skill_snapshot")
def skill_snapshot(user_id: int, profile: dict):
    async def _persist():
        factory = UnitOfWorkFactory(AsyncSessionMaker)
        service = SkillTrackingService(factory)
        service.skills[user_id] = profile
        await service._save_snapshot(user_id)

    anyio.run(_persist)
    logger.info("skill_snapshot_persisted", extra={"user_id": user_id})
