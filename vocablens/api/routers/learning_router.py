from fastapi import APIRouter, Depends

from vocablens.api.dependencies import get_current_user
from vocablens.domain.user import User

from vocablens.services.learning_roadmap_service import LearningRoadmapService
from vocablens.services.knowledge_graph_service import KnowledgeGraphService


def create_learning_router(
    roadmap_service: LearningRoadmapService,
    graph_service: KnowledgeGraphService,
) -> APIRouter:

    router = APIRouter(
        prefix="/learning",
        tags=["Learning"],
    )

    @router.get("/roadmap")
    def roadmap(user: User = Depends(get_current_user)):

        return roadmap_service.generate_today_plan(user.id)

    @router.get("/graph")
    def graph(user: User = Depends(get_current_user)):

        return graph_service.build_graph(user.id)

    return router