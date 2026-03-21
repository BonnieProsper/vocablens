from types import SimpleNamespace

from tests.conftest import run_async
from vocablens.services.monetization_engine import MonetizationEngine


class FakeAdaptivePaywallService:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    async def evaluate(self, user_id: int, *, wow_score: float | None = None):
        self.calls.append({"user_id": user_id, "wow_score": wow_score})
        return self.decision


class FakeBusinessMetricsService:
    def __init__(self, *, ltv: float = 240.0):
        self.ltv = ltv

    async def dashboard(self):
        return {
            "revenue": {
                "mrr": 1200.0,
                "arpu": 24.0,
                "arpu_all_users": 6.0,
                "ltv": self.ltv,
                "paying_users": 50,
            }
        }


class FakeOnboardingFlowService:
    def __init__(self, state=None):
        self.state = state
        self.calls = []

    async def current_state(self, user_id: int):
        self.calls.append(user_id)
        return self.state


class FakeLifecycleService:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    async def evaluate(self, user_id: int):
        self.calls.append(user_id)
        return self.plan


def _paywall_decision(
    *,
    show_paywall: bool = True,
    paywall_type: str | None = "soft_paywall",
    reason: str | None = "adaptive session trigger reached",
    usage_percent: int = 72,
    user_segment: str = "high_intent",
    strategy: str = "high_intent:early:value_anchor",
    trigger_variant: str = "early",
    pricing_variant: str = "value_anchor",
    trial_days: int = 5,
    trial_recommended: bool = False,
    trial_active: bool = False,
):
    return SimpleNamespace(
        show_paywall=show_paywall,
        paywall_type=paywall_type,
        reason=reason,
        usage_percent=usage_percent,
        allow_access=True,
        user_segment=user_segment,
        strategy=strategy,
        trigger_variant=trigger_variant,
        pricing_variant=pricing_variant,
        trial_days=trial_days,
        trial_recommended=trial_recommended,
        trial_active=trial_active,
    )


def _lifecycle(stage: str):
    return SimpleNamespace(stage=stage, actions=[], reasons=["test"])


def test_monetization_engine_adjusts_pricing_by_geography_and_engagement():
    engaged_engine = MonetizationEngine(
        FakeAdaptivePaywallService(_paywall_decision(user_segment="high_intent", pricing_variant="premium_anchor")),
        FakeBusinessMetricsService(ltv=420.0),
        FakeOnboardingFlowService({"current_step": "completed", "paywall": {}}),
        FakeLifecycleService(_lifecycle("engaged")),
    )
    low_engagement_engine = MonetizationEngine(
        FakeAdaptivePaywallService(_paywall_decision(user_segment="low_engagement", pricing_variant="discount_focus")),
        FakeBusinessMetricsService(ltv=180.0),
        FakeOnboardingFlowService({"current_step": "completed", "paywall": {}}),
        FakeLifecycleService(_lifecycle("at_risk")),
    )

    engaged = run_async(engaged_engine.evaluate(1, geography="us"))
    low_engagement = run_async(low_engagement_engine.evaluate(2, geography="india"))

    assert engaged.offer_type == "annual_anchor"
    assert engaged.pricing["monthly_price"] == 21.6
    assert engaged.pricing["annual_savings_percent"] == 20
    assert low_engagement.offer_type == "discount"
    assert low_engagement.pricing["monthly_price"] == 7.29
    assert low_engagement.pricing["discounted_monthly_price"] == 5.83
    assert low_engagement.pricing["annual_savings_percent"] == 25


def test_monetization_engine_defers_paywall_during_early_onboarding_even_when_triggered():
    engine = MonetizationEngine(
        FakeAdaptivePaywallService(_paywall_decision(show_paywall=True, trial_recommended=True)),
        FakeBusinessMetricsService(),
        FakeOnboardingFlowService(
            {
                "current_step": "instant_wow_moment",
                "wow": {"understood_percent": 82.0},
                "paywall": {"trial_recommended": True},
            }
        ),
        FakeLifecycleService(_lifecycle("new_user")),
    )

    decision = run_async(engine.evaluate(3, geography="us", wow_score=0.84))

    assert decision.show_paywall is False
    assert decision.offer_type == "trial"
    assert decision.paywall_type is None
    assert decision.trigger["timing_policy"] == "deferred_for_activation"
    assert decision.value_display["locked_progress_percent"] == 82


def test_monetization_engine_surfaces_soft_paywall_once_onboarding_reaches_paywall_step():
    engine = MonetizationEngine(
        FakeAdaptivePaywallService(_paywall_decision(show_paywall=True, trial_recommended=True, usage_percent=64)),
        FakeBusinessMetricsService(),
        FakeOnboardingFlowService(
            {
                "current_step": "soft_paywall",
                "paywall": {"trial_recommended": True},
                "progress_illusion": {"xp_gain": 52},
            }
        ),
        FakeLifecycleService(_lifecycle("activating")),
    )

    decision = run_async(engine.evaluate(4, geography="latam"))

    assert decision.show_paywall is True
    assert decision.paywall_type == "soft_paywall"
    assert decision.offer_type == "trial"
    assert decision.trigger["trigger_variant"] == "early"
    assert decision.strategy == "high_intent:early:value_anchor:trial:latam"
    assert "Keep your onboarding streak" in decision.value_display["locked_features"][-1]
