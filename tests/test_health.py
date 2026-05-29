"""Health endpoint tests."""

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "checks": None}


async def test_ready_checks_database(client: AsyncClient) -> None:
    resp = await client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["database"] == "ok"


async def test_request_id_echoed_in_response(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"X-Request-ID": "test-correlation"})
    assert resp.headers["X-Request-ID"] == "test-correlation"


async def test_request_id_generated_when_missing(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) == 32  # uuid hex
