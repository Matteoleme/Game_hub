from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import initialize_database
from app.main import api


@pytest.fixture(autouse=True)
async def database() -> None:
    await initialize_database()


@pytest.mark.asyncio
async def test_register_login_me_and_logout() -> None:
    email = f"{uuid4()}@example.com"
    password = "correct horse battery staple"

    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as client:
        register_response = await client.post(
            "/api/auth/register",
            json={"email": email, "password": password},
        )
        login_response = await client.post(
            "/api/auth/login",
            json={"email": email.upper(), "password": password},
        )
        me_response = await client.get("/api/auth/me")
        logout_response = await client.post("/api/auth/logout")
        after_logout_response = await client.get("/api/auth/me")

    assert register_response.status_code == 201
    assert login_response.status_code == 200
    assert login_response.json()["user"]["email"] == email
    assert me_response.status_code == 200
    assert logout_response.status_code == 204
    assert after_logout_response.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_email_and_invalid_password_are_rejected() -> None:
    email = f"{uuid4()}@example.com"

    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as client:
        first_response = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "password-123"},
        )
        duplicate_response = await client.post(
            "/api/auth/register",
            json={"email": email.upper(), "password": "password-456"},
        )
        invalid_response = await client.post(
            "/api/auth/register",
            json={"email": f"other-{uuid4()}@example.com", "password": "short"},
        )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"]["code"] == "EMAIL_ALREADY_EXISTS"
    assert invalid_response.status_code == 422
