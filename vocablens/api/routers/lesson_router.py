from fastapi import APIRouter, Depends

from vocablens.api.dependencies import get_current_user
from vocablens.domain.user import User
from vocablens.services.lesson_generation_service import LessonGenerationService


def create_lesson_router(service: LessonGenerationService) -> APIRouter:

    router = APIRouter(
        prefix="/lesson",
        tags=["Lessons"],
    )

    @router.get("/generate")
    def generate_lesson(
        user: User = Depends(get_current_user),
    ):

        lesson = service.generate_lesson(user.id)

        return lesson

    return router