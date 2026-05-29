"""Auth integration tests — hit the running app + database."""

from httpx import AsyncClient

from app.db.models.user import User


async def test_login_success(client: AsyncClient, regular_user: User) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": regular_user.email, "password": "correct-horse-battery-staple"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert data["expires_in"] > 0


async def test_login_wrong_password(client: AsyncClient, regular_user: User) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": regular_user.email, "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_login_nonexistent_user(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401


async def test_me_returns_authenticated_user(client: AsyncClient, regular_user: User) -> None:
    login = await client.post(
        "/auth/login",
        json={"email": regular_user.email, "password": "correct-horse-battery-staple"},
    )
    token = login.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == regular_user.email


async def test_me_rejects_missing_token(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_rejects_invalid_token(client: AsyncClient) -> None:
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert resp.status_code == 401
