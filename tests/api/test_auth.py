from sqlalchemy import select

from app.models.user import RefreshToken


async def test_register_default_role_is_reader(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "reader@example.com",
            "username": "reader",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "reader"


async def test_register_with_author_role(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "author@example.com",
            "username": "author",
            "password": "password123",
            "role": "author",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "author"


async def test_register_creates_user(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "reader@example.com",
            "username": "reader",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "reader@example.com"
    assert data["username"] == "reader"
    assert data["role"] == "reader"
    assert "password" not in data


async def test_register_rejects_duplicate_email_or_username(client):
    payload = {
        "email": "reader@example.com",
        "username": "reader",
        "password": "password123",
    }
    assert (await client.post("/auth/register", json=payload)).status_code == 201

    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 409


async def test_login_returns_access_and_refresh_tokens(client):
    await client.post(
        "/auth/register",
        json={
            "email": "reader@example.com",
            "username": "reader",
            "password": "password123",
        },
    )

    response = await client.post(
        "/auth/login",
        json={"email": "reader@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]


async def test_login_rejects_wrong_password(client):
    await client.post(
        "/auth/register",
        json={
            "email": "reader@example.com",
            "username": "reader",
            "password": "password123",
        },
    )

    response = await client.post(
        "/auth/login",
        json={"email": "reader@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_refresh_rotates_refresh_token(client, db_session):
    await client.post(
        "/auth/register",
        json={
            "email": "reader@example.com",
            "username": "reader",
            "password": "password123",
        },
    )
    login = await client.post(
        "/auth/login",
        json={"email": "reader@example.com", "password": "password123"},
    )
    old_refresh_token = login.json()["refresh_token"]

    response = await client.post("/auth/refresh", json={"refresh_token": old_refresh_token})

    assert response.status_code == 200
    assert response.json()["refresh_token"] != old_refresh_token
    result = await db_session.execute(select(RefreshToken).where(RefreshToken.revoked_at.is_not(None)))
    assert result.scalar_one_or_none() is not None


async def test_logout_revokes_refresh_token(client, db_session):
    await client.post(
        "/auth/register",
        json={
            "email": "reader@example.com",
            "username": "reader",
            "password": "password123",
        },
    )
    login = await client.post(
        "/auth/login",
        json={"email": "reader@example.com", "password": "password123"},
    )

    response = await client.post(
        "/auth/logout",
        json={"refresh_token": login.json()["refresh_token"]},
    )

    assert response.status_code == 204
    result = await db_session.execute(select(RefreshToken).where(RefreshToken.revoked_at.is_not(None)))
    assert result.scalar_one_or_none() is not None
