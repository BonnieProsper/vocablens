from fastapi.testclient import TestClient

from tests.conftest import make_user
from vocablens.api.dependencies import (
    get_admin_token,
    get_current_user,
    get_frontend_service,
    get_subscription_service,
)
from vocablens.main import create_app


class FakeFrontendService:
    async def dashboard(self, user_id: int):
        return {
            "progress": {"vocabulary_total": 12, "due_reviews": 3, "streak": 4, "session_frequency": 2.5, "retention_state": "active"},
            "subscription": {"tier": "pro", "tutor_depth": "standard", "explanation_quality": "standard", "personalization_level": "standard"},
            "skills": {"grammar": 0.7, "vocabulary": 0.6},
            "next_action": {"action": "review_word", "target": "hola", "reason": "Due review", "difficulty": "medium", "content_type": "vocab"},
            "retention": {"state": "active", "drop_off_risk": 0.2, "actions": []},
            "weak_areas": {"clusters": [], "mistakes": []},
            "roadmap": {"review_words": 3},
        }

    async def recommendations(self, user_id: int):
        return {
            "next_action": {"action": "learn_new_word", "target": "travel", "reason": "Weak cluster", "difficulty": "medium", "content_type": "vocab"},
            "retention_actions": [{"kind": "review_reminder", "reason": "3 reviews waiting", "target": "hola"}],
        }

    async def weak_areas(self, user_id: int):
        return {
            "weak_skills": [{"skill": "vocabulary", "score": 0.55}],
            "weak_clusters": [{"cluster": "travel", "weakness": 1.1, "words": ["hola", "adios"]}],
            "mistake_patterns": [{"category": "grammar", "pattern": "verb tense", "count": 2}],
        }

    def meta(self, *, source: str, difficulty: str | None = None, next_action: str | None = None):
        meta = {"source": source}
        if difficulty:
            meta["difficulty"] = difficulty
        if next_action:
            meta["next_action"] = next_action
        return meta


class FakeSubscriptionService:
    async def conversion_metrics(self):
        return {"tier_upgraded": 4, "feature_gate_blocked": 9}


def test_frontend_dashboard_and_related_endpoints_return_standardized_envelopes():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: make_user()
    app.dependency_overrides[get_frontend_service] = lambda: FakeFrontendService()
    client = TestClient(app)

    dashboard = client.get("/frontend/dashboard", headers={"Authorization": "Bearer ignored"})
    recommendations = client.get("/frontend/recommendations", headers={"Authorization": "Bearer ignored"})
    weak_areas = client.get("/frontend/weak-areas", headers={"Authorization": "Bearer ignored"})

    assert dashboard.status_code == 200
    assert dashboard.json()["meta"]["source"] == "frontend.dashboard"
    assert dashboard.json()["data"]["next_action"]["action"] == "review_word"

    assert recommendations.status_code == 200
    assert recommendations.json()["meta"]["next_action"] == "learn_new_word"
    assert recommendations.json()["data"]["retention_actions"][0]["kind"] == "review_reminder"

    assert weak_areas.status_code == 200
    assert weak_areas.json()["meta"]["source"] == "frontend.weak_areas"
    assert weak_areas.json()["data"]["weak_clusters"][0]["cluster"] == "travel"


def test_admin_conversion_report_is_protected_and_standardized():
    app = create_app()
    app.dependency_overrides[get_admin_token] = lambda: "ok"
    app.dependency_overrides[get_subscription_service] = lambda: FakeSubscriptionService()
    client = TestClient(app)

    response = client.get("/admin/reports/conversions", headers={"X-Admin-Token": "secret"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["source"] == "admin.conversions"
    assert payload["data"]["conversion_metrics"]["tier_upgraded"] == 4
