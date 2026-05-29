"""User CRUD endpoint tests."""

from httpx import AsyncClient

from app.db.models.user import User


async def _auth_headers(client: AsyncClient, user: User) -> dict[str, str]:
    resp = await client.post(
        "/auth/login",
        json={"email": user.email, "password": "correct-horse-battery-staple"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_list_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/users")
    assert resp.status_code == 401


async def test_list_returns_users(client: AsyncClient, regular_user: User) -> None:
    headers = await _auth_headers(client, regular_user)
    resp = await client.get("/users", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(u["email"] == regular_user.email for u in data["items"])


async def test_create_requires_superuser(client: AsyncClient, regular_user: User) -> None:
    headers = await _auth_headers(client, regular_user)
    resp = await client.post(
        "/users",
        json={"email": "new@example.com", "password": "long-enough-password"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_create_as_superuser(client: AsyncClient, super_user: User) -> None:
    headers = await _auth_headers(client, super_user)
    resp = await client.post(
        "/users",
        json={
            "email": "new@example.com",
            "password": "long-enough-password",
            "full_name": "New User",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "new@example.com"


async def test_create_duplicate_email_conflicts(client: AsyncClient, super_user: User) -> None:
    headers = await _auth_headers(client, super_user)
    payload = {"email": "dupe@example.com", "password": "long-enough-password"}
    first = await client.post("/users", json=payload, headers=headers)
    assert first.status_code == 201
    second = await client.post("/users", json=payload, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_get_nonexistent_user_404(client: AsyncClient, regular_user: User) -> None:
    headers = await _auth_headers(client, regular_user)
    resp = await client.get("/users/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_validation_error_returns_422(client: AsyncClient, super_user: User) -> None:
    headers = await _auth_headers(client, super_user)
    resp = await client.post(
        "/users",
        json={"email": "not-an-email", "password": "short"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
