from fastapi import APIRouter, Depends

from vocablens.api.dependencies import get_current_user
from vocablens.domain.user import User
from vocablens.services.scenario_service import ScenarioService


def create_scenario_router(service: ScenarioService) -> APIRouter:

    router = APIRouter(
        prefix="/scenario",
        tags=["Immersion"],
    )

    @router.post("/start")
    def start_scenario(
        scenario: str,
        language: str,
        user: User = Depends(get_current_user),
    ):

        result = service.start_scenario(
            scenario,
            language,
        )

        return {"scenario": result}

    return router