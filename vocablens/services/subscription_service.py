from dataclasses import dataclass

from vocablens.infrastructure.unit_of_work import UnitOfWork
from vocablens.services.experiment_service import ExperimentService


@dataclass(frozen=True)
class SubscriptionFeatures:
    tier: str
    request_limit: int
    token_limit: int
    tutor_depth: str
    explanation_quality: str
    personalization_level: str
    paywall_variant: str | None = None


TIER_FEATURES = {
    "free": SubscriptionFeatures(
        tier="free",
        request_limit=100,
        token_limit=50000,
        tutor_depth="basic",
        explanation_quality="basic",
        personalization_level="basic",
    ),
    "pro": SubscriptionFeatures(
        tier="pro",
        request_limit=1000,
        token_limit=300000,
        tutor_depth="standard",
        explanation_quality="standard",
        personalization_level="standard",
    ),
    "premium": SubscriptionFeatures(
        tier="premium",
        request_limit=10000,
        token_limit=1000000,
        tutor_depth="deep",
        explanation_quality="premium",
        personalization_level="premium",
    ),
}


class SubscriptionService:
    def __init__(
        self,
        uow_factory: type[UnitOfWork],
        experiment_service: ExperimentService | None = None,
    ):
        self._uow_factory = uow_factory
        self._experiments = experiment_service

    async def get_features(self, user_id: int) -> SubscriptionFeatures:
        async with self._uow_factory() as uow:
            subscription = await uow.subscriptions.get_by_user(user_id)
            await uow.commit()

        tier = (subscription.tier if subscription else "free").lower()
        base = TIER_FEATURES.get(tier, TIER_FEATURES["free"])
        paywall_variant = await self._paywall_variant(user_id, tier)
        if not subscription:
            return self._apply_paywall_variant(base, paywall_variant)
        adjusted_limits = self._apply_variant_limits(
            request_limit=subscription.request_limit,
            token_limit=subscription.token_limit,
            variant=paywall_variant,
            tier=tier,
        )
        return SubscriptionFeatures(
            tier=base.tier,
            request_limit=adjusted_limits["request_limit"],
            token_limit=adjusted_limits["token_limit"],
            tutor_depth=base.tutor_depth,
            explanation_quality=base.explanation_quality,
            personalization_level=base.personalization_level,
            paywall_variant=paywall_variant,
        )

    async def require_feature(self, user_id: int, feature_name: str, minimum_tier: str) -> SubscriptionFeatures:
        features = await self.get_features(user_id)
        if self._tier_rank(features.tier) < self._tier_rank(minimum_tier):
            await self.record_feature_gate(
                user_id=user_id,
                feature_name=feature_name,
                allowed=False,
                current_tier=features.tier,
                required_tier=minimum_tier,
            )
        return features

    async def record_feature_gate(
        self,
        *,
        user_id: int,
        feature_name: str,
        allowed: bool,
        current_tier: str,
        required_tier: str,
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.subscription_events.record(
                user_id=user_id,
                event_type="feature_gate_allowed" if allowed else "feature_gate_blocked",
                from_tier=current_tier,
                to_tier=required_tier,
                feature_name=feature_name,
                metadata={"allowed": allowed},
            )
            await uow.commit()

    async def upgrade_tier(self, user_id: int, tier: str) -> SubscriptionFeatures:
        target = TIER_FEATURES[tier]
        async with self._uow_factory() as uow:
            current = await uow.subscriptions.get_by_user(user_id)
            from_tier = current.tier if current else "free"
            await uow.subscriptions.upsert(
                user_id=user_id,
                tier=tier,
                request_limit=target.request_limit,
                token_limit=target.token_limit,
            )
            await uow.subscription_events.record(
                user_id=user_id,
                event_type="tier_upgraded",
                from_tier=from_tier,
                to_tier=tier,
                metadata={"request_limit": target.request_limit, "token_limit": target.token_limit},
            )
            await uow.commit()
        return target

    async def conversion_metrics(self) -> dict:
        async with self._uow_factory() as uow:
            counts = await uow.subscription_events.counts_by_event()
            await uow.commit()
        return counts

    def _tier_rank(self, tier: str) -> int:
        return {"free": 0, "pro": 1, "premium": 2}.get(tier, 0)

    async def _paywall_variant(self, user_id: int, tier: str) -> str | None:
        if tier != "free":
            return None
        if not self._experiments or not self._experiments.has_experiment("paywall_offer"):
            return None
        return await self._experiments.assign(user_id, "paywall_offer")

    def _apply_paywall_variant(self, base: SubscriptionFeatures, variant: str | None) -> SubscriptionFeatures:
        adjusted_limits = self._apply_variant_limits(
            request_limit=base.request_limit,
            token_limit=base.token_limit,
            variant=variant,
            tier=base.tier,
        )
        return SubscriptionFeatures(
            tier=base.tier,
            request_limit=adjusted_limits["request_limit"],
            token_limit=adjusted_limits["token_limit"],
            tutor_depth=base.tutor_depth,
            explanation_quality=base.explanation_quality,
            personalization_level=base.personalization_level,
            paywall_variant=variant,
        )

    def _apply_variant_limits(
        self,
        *,
        request_limit: int,
        token_limit: int,
        variant: str | None,
        tier: str,
    ) -> dict[str, int]:
        if tier != "free":
            return {"request_limit": request_limit, "token_limit": token_limit}
        if variant == "soft_paywall":
            return {
                "request_limit": int(request_limit * 1.2),
                "token_limit": int(token_limit * 1.2),
            }
        if variant == "hard_paywall":
            return {
                "request_limit": max(1, int(request_limit * 0.8)),
                "token_limit": max(1, int(token_limit * 0.8)),
            }
        return {"request_limit": request_limit, "token_limit": token_limit}
