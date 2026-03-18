from fastapi.testclient import TestClient

from vocablens.api.dependencies import get_user_repo
from vocablens.auth.jwt import decode_token
from vocablens.domain.errors import PersistenceError
from vocablens.main import create_app


class InMemoryUserRepo:
    def __init__(self):
        self._users_by_email = {}
        self._next_id = 1

    async def create(self, email: str, password_hash: str):
        if email in self._users_by_email:
            raise PersistenceError("duplicate")
        user = type(
            "UserRecord",
            (),
            {"id": self._next_id, "email": email, "password_hash": password_hash},
        )()
        self._users_by_email[email] = user
        self._next_id += 1
        return user

    async def get_by_email(self, email: str):
        return self._users_by_email.get(email)

    async def get_by_id(self, user_id: int):
        for user in self._users_by_email.values():
            if user.id == user_id:
                return user
        return None


def test_register_and_login_round_trip():
    app = create_app()
    repo = InMemoryUserRepo()
    app.dependency_overrides[get_user_repo] = lambda: repo
    client = TestClient(app)

    register = client.post(
        "/register",
        json={"email": "test@test.com", "password": "password123"},
    )
    assert register.status_code == 200
    register_payload = register.json()
    assert "access_token" in register_payload
    assert decode_token(register_payload["access_token"]) == 1

    login = client.post(
        "/login",
        json={"email": "test@test.com", "password": "password123"},
    )
    assert login.status_code == 200
    login_payload = login.json()
    assert "access_token" in login_payload
    assert decode_token(login_payload["access_token"]) == 1
