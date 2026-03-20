from fastapi import APIRouter, Depends

from vocablens.api.dependencies import get_admin_token, get_analytics_service, get_subscription_service
from vocablens.api.schemas import APIResponse
from vocablens.services.analytics_service import AnalyticsService
from vocablens.services.subscription_service import SubscriptionService


def create_admin_router() -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["Admin"])

    @router.get("/reports/conversions", response_model=APIResponse)
    async def conversion_metrics(
        _: str = Depends(get_admin_token),
        service: SubscriptionService = Depends(get_subscription_service),
    ):
        metrics = await service.conversion_metrics()
        return APIResponse(
            data={"conversion_metrics": metrics},
            meta={"source": "admin.conversions"},
        )

    @router.get("/analytics/retention", response_model=APIResponse)
    async def retention_analytics(
        _: str = Depends(get_admin_token),
        service: AnalyticsService = Depends(get_analytics_service),
    ):
        metrics = await service.retention_report()
        return APIResponse(
            data={"retention": metrics},
            meta={"source": "admin.analytics.retention"},
        )

    @router.get("/analytics/usage", response_model=APIResponse)
    async def usage_analytics(
        _: str = Depends(get_admin_token),
        service: AnalyticsService = Depends(get_analytics_service),
    ):
        metrics = await service.usage_report()
        return APIResponse(
            data={"usage": metrics},
            meta={"source": "admin.analytics.usage"},
        )

    return router
