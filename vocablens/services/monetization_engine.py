from __future__ import annotations

from dataclasses import asdict, dataclass

from vocablens.infrastructure.unit_of_work import UnitOfWork
from vocablens.services.adaptive_paywall_service import AdaptivePaywallDecision, AdaptivePaywallService
from vocablens.services.business_metrics_service import BusinessMetricsService, TIER_MONTHLY_PRICES
from vocablens.services.lifecycle_service import LifecyclePlan, LifecycleService
from vocablens.services.onboarding_flow_service import OnboardingFlowService


GEOGRAPHY_MULTIPLIERS = {
    "global": 1.0,
    "us": 1.0,
    "ca": 1.0,
    "uk": 1.0,
    "au": 1.0,
    "nz": 1.0,
    "eu": 1.05,
    "latam": 0.7,
    "in": 0.45,
    "india": 0.45,
    "sea": 0.65,
}


@dataclass(frozen=True)
class MonetizationDecision:
    show_paywall: bool
    paywall_type: str | None
    offer_type: str
    pricing: dict
    trigger: dict
    value_display: dict
    strategy: str
    lifecycle_stage: str
    onboarding_step: str | None
    user_segment: str
    trial_days: int | None

    def as_dict(self) -> dict:
        return asdict(self)


class MonetizationEngine:
    def __init__(
        self,
        uow_factory: type[UnitOfWork],
        paywall_service: AdaptivePaywallService,
        business_metrics_service: BusinessMetricsService,
        onboarding_flow_service: OnboardingFlowService,
        lifecycle_service: LifecycleService,
    ):
        self._uow_factory = uow_factory
        self._paywall = paywall_service
        self._business_metrics = business_metrics_service
        self._onboarding_flow = onboarding_flow_service
        self._lifecycle = lifecycle_service

    async def evaluate(
        self,
        user_id: int,
        *,
        geography: str | None = None,
        wow_score: float | None = None,
    ) -> MonetizationDecision:
        paywall = await self._paywall.evaluate(user_id, wow_score=wow_score)
        lifecycle = await self._lifecycle.evaluate(user_id)
        onboarding_state = await self._onboarding_flow.current_state(user_id)
        _ = await self._business_metrics.dashboard()
        learning_state, engagement_state, progress_state = await self._state_snapshot(user_id)

        onboarding_step = onboarding_state.get("current_step") if onboarding_state else None
        geography_code = self._normalize_geography(geography)
        pricing = self._build_pricing(
            paywall=paywall,
            lifecycle=lifecycle,
            onboarding_state=onboarding_state,
            engagement_state=engagement_state,
            geography=geography_code,
        )
        offer_type = self._offer_type(paywall=paywall, lifecycle=lifecycle, onboarding_state=onboarding_state)
        show_paywall = self._should_show_paywall(
            paywall=paywall,
            lifecycle=lifecycle,
            onboarding_step=onboarding_step,
        )
        if not show_paywall and offer_type == "annual_anchor":
            offer_type = "none"

        strategy = f"{paywall.strategy}:{offer_type}:{geography_code}"
        return MonetizationDecision(
            show_paywall=show_paywall,
            paywall_type=paywall.paywall_type if show_paywall else None,
            offer_type=offer_type,
            pricing=pricing,
            trigger=self._trigger_payload(
                paywall=paywall,
                lifecycle=lifecycle,
                onboarding_step=onboarding_step,
                show_paywall=show_paywall,
            ),
            value_display=self._value_display(
                paywall=paywall,
                lifecycle=lifecycle,
                onboarding_state=onboarding_state,
                learning_state=learning_state,
                progress_state=progress_state,
                offer_type=offer_type,
            ),
            strategy=strategy,
            lifecycle_stage=lifecycle.stage,
            onboarding_step=onboarding_step,
            user_segment=paywall.user_segment,
            trial_days=paywall.trial_days if offer_type == "trial" else None,
        )

    async def _state_snapshot(self, user_id: int):
        async with self._uow_factory() as uow:
            learning_state = await uow.learning_states.get_or_create(user_id)
            engagement_state = await uow.engagement_states.get_or_create(user_id)
            progress_state = await uow.progress_states.get_or_create(user_id)
            await uow.commit()
        return learning_state, engagement_state, progress_state

    def _normalize_geography(self, geography: str | None) -> str:
        if not geography:
            return "global"
        normalized = geography.strip().lower()
        return normalized if normalized in GEOGRAPHY_MULTIPLIERS else "global"

    def _build_pricing(
        self,
        *,
        paywall: AdaptivePaywallDecision,
        lifecycle: LifecyclePlan,
        onboarding_state: dict | None,
        engagement_state,
        geography: str,
    ) -> dict:
        base_monthly = float(TIER_MONTHLY_PRICES["pro"])
        geography_multiplier = GEOGRAPHY_MULTIPLIERS.get(geography, 1.0)
        engagement_multiplier = self._engagement_multiplier(
            lifecycle.stage,
            paywall.user_segment,
            engagement_state=engagement_state,
        )
        pricing_multiplier = self._pricing_variant_multiplier(paywall.pricing_variant)
        monthly_price = round(base_monthly * geography_multiplier * engagement_multiplier * pricing_multiplier, 2)

        discount_percent = self._discount_percent(
            lifecycle_stage=lifecycle.stage,
            user_segment=paywall.user_segment,
            onboarding_state=onboarding_state,
        )
        discounted_monthly = round(monthly_price * (1 - discount_percent / 100), 2)

        annual_savings_percent = 20 if float(getattr(engagement_state, "momentum_score", 0.0) or 0.0) >= 0.6 else 25
        annual_price = round(monthly_price * 12 * (1 - annual_savings_percent / 100), 2)
        annual_monthly_equivalent = round(annual_price / 12, 2)

        return {
            "geography": geography,
            "monthly_price": monthly_price,
            "discounted_monthly_price": discounted_monthly,
            "discount_percent": discount_percent,
            "annual_price": annual_price,
            "annual_monthly_equivalent": annual_monthly_equivalent,
            "annual_savings_percent": annual_savings_percent,
            "pricing_variant": paywall.pricing_variant,
            "annual_anchor_message": self._annual_anchor_message(monthly_price, annual_monthly_equivalent),
        }

    def _engagement_multiplier(self, lifecycle_stage: str, user_segment: str, *, engagement_state) -> float:
        momentum = float(getattr(engagement_state, "momentum_score", 0.0) or 0.0)
        if lifecycle_stage in {"at_risk", "churned"} or user_segment == "low_engagement":
            return 0.9 if momentum >= 0.4 else 0.85
        if lifecycle_stage == "engaged" or user_segment == "high_intent":
            return 1.02 if momentum >= 0.7 else 1.0
        if lifecycle_stage == "new_user":
            return 0.95
        return 0.97

    def _pricing_variant_multiplier(self, pricing_variant: str) -> float:
        return {
            "standard": 1.0,
            "value_anchor": 1.0,
            "premium_anchor": 1.08,
            "discount_focus": 0.9,
        }.get(pricing_variant, 1.0)

    def _discount_percent(self, *, lifecycle_stage: str, user_segment: str, onboarding_state: dict | None) -> int:
        onboarding_step = onboarding_state.get("current_step") if onboarding_state else None
        if lifecycle_stage in {"at_risk", "churned"} or user_segment == "low_engagement":
            return 20
        if onboarding_step == "soft_paywall":
            return 10
        if lifecycle_stage == "new_user":
            return 5
        return 0

    def _annual_anchor_message(self, monthly_price: float, annual_monthly_equivalent: float) -> str:
        return f"Pro is {monthly_price:.2f}/mo, or {annual_monthly_equivalent:.2f}/mo on annual."

    def _offer_type(
        self,
        *,
        paywall: AdaptivePaywallDecision,
        lifecycle: LifecyclePlan,
        onboarding_state: dict | None,
    ) -> str:
        if paywall.trial_active:
            return "none"
        onboarding_paywall = (onboarding_state or {}).get("paywall", {})
        if onboarding_paywall.get("trial_recommended") or paywall.trial_recommended:
            return "trial"
        if lifecycle.stage in {"at_risk", "churned"} or paywall.user_segment == "low_engagement":
            return "discount"
        if lifecycle.stage == "engaged" or paywall.user_segment == "high_intent":
            return "annual_anchor"
        return "none"

    def _should_show_paywall(
        self,
        *,
        paywall: AdaptivePaywallDecision,
        lifecycle: LifecyclePlan,
        onboarding_step: str | None,
    ) -> bool:
        if not paywall.show_paywall:
            return False
        if onboarding_step in {"identity_selection", "personalization", "instant_wow_moment", "progress_illusion"}:
            return False
        if lifecycle.stage == "new_user" and onboarding_step not in {"soft_paywall", "habit_lock_in", "completed"}:
            return False
        return True

    def _trigger_payload(
        self,
        *,
        paywall: AdaptivePaywallDecision,
        lifecycle: LifecyclePlan,
        onboarding_step: str | None,
        show_paywall: bool,
    ) -> dict:
        return {
            "show_now": show_paywall,
            "trigger_variant": paywall.trigger_variant,
            "trigger_reason": paywall.reason,
            "lifecycle_stage": lifecycle.stage,
            "onboarding_step": onboarding_step,
            "timing_policy": "deferred_for_activation"
            if paywall.show_paywall and not show_paywall
            else "adaptive_paywall",
        }

    def _value_display(
        self,
        *,
        paywall: AdaptivePaywallDecision,
        lifecycle: LifecyclePlan,
        onboarding_state: dict | None,
        learning_state,
        progress_state,
        offer_type: str,
    ) -> dict:
        progress_illusion = (onboarding_state or {}).get("progress_illusion", {})
        mastery = float(getattr(learning_state, "mastery_percent", 0.0) or 0.0)
        xp = int(getattr(progress_state, "xp", 0) or 0)
        level = int(getattr(progress_state, "level", 1) or 1)
        locked_progress_percent = max(
            int(mastery),
            int(paywall.usage_percent or 0),
            20 if offer_type != "none" else 0,
        )
        highlight = "Keep your early progress unlocked."
        if lifecycle.stage == "engaged":
            highlight = "Unlock the full adaptive system behind your current momentum."
        elif lifecycle.stage in {"at_risk", "churned"}:
            highlight = "Keep your streak and saved progress from stalling."

        locked_features = [
            "Unlimited tutor rounds",
            "Full adaptive review queue",
            "Detailed progress insights",
            f"Keep your {xp} XP and level {level} momentum compounding",
        ]
        if progress_illusion:
            locked_features.append("Keep your onboarding streak and fast XP gains")

        return {
            "show_locked_progress": offer_type != "none" or paywall.show_paywall,
            "locked_progress_percent": min(99, locked_progress_percent),
            "locked_features": locked_features,
            "highlight": highlight,
            "usage_percent": paywall.usage_percent,
        }
