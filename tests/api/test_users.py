from tests.factories import auth_headers, create_user


async def test_get_me_returns_authenticated_profile(client, db_session):
    user = await create_user(db_session, email="me@example.com", username="meuser")

    response = await client.get("/users/me", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


async def test_get_me_requires_authentication(client):
    response = await client.get("/users/me")

    assert response.status_code in {401, 403}


async def test_update_me_changes_username_and_display_tag(client, db_session):
    user = await create_user(db_session, email="me@example.com", username="meuser")

    response = await client.patch(
        "/users/me",
        headers=auth_headers(user),
        json={"username": "updated", "display_tag": "Aeon Author"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "updated"
    assert data["display_tag"] == "Aeon Author"


async def test_update_me_rejects_duplicate_username(client, db_session):
    user = await create_user(db_session, email="me@example.com", username="meuser")
    await create_user(db_session, email="taken@example.com", username="taken")

    response = await client.patch(
        "/users/me",
        headers=auth_headers(user),
        json={"username": "taken"},
    )

    assert response.status_code == 409


async def test_change_password_allows_login_with_new_password(client, db_session):
    user = await create_user(
        db_session,
        email="me@example.com",
        username="meuser",
        password="old-password",
    )

    response = await client.patch(
        "/users/me/password",
        headers=auth_headers(user),
        json={"current_password": "old-password", "new_password": "new-password"},
    )

    assert response.status_code == 204
    login = await client.post(
        "/auth/login",
        json={"email": "me@example.com", "password": "new-password"},
    )
    assert login.status_code == 200


async def test_change_password_rejects_wrong_current_password(client, db_session):
    user = await create_user(db_session, email="me@example.com", username="meuser")

    response = await client.patch(
        "/users/me/password",
        headers=auth_headers(user),
        json={"current_password": "wrong-password", "new_password": "new-password"},
    )

    assert response.status_code == 400


async def test_avatar_presigned_flow_updates_avatar_key(client, db_session):
    user = await create_user(db_session, email="me@example.com", username="meuser")

    upload = await client.post("/users/me/avatar", headers=auth_headers(user))

    assert upload.status_code == 200
    assert upload.json()["upload_url"].startswith("https://storage.test/upload/avatars/")

    confirm = await client.patch(
        "/users/me/avatar-key",
        headers=auth_headers(user),
        params={"object_key": upload.json()["object_key"]},
    )

    assert confirm.status_code == 200
    assert confirm.json()["avatar_key"] == upload.json()["object_key"]

    media = await client.get(f"/media/{upload.json()['object_key']}", follow_redirects=False)
    assert media.status_code == 307
    assert media.headers["location"].startswith("https://storage.test/get/avatars/")


async def test_media_rejects_private_book_objects(client):
    response = await client.get("/media/books/private.epub", follow_redirects=False)

    assert response.status_code == 404


async def test_payment_profile_can_be_created_and_read(client, db_session):
    user = await create_user(db_session, email="me@example.com", username="meuser")

    missing = await client.get("/users/me/payment-profile", headers=auth_headers(user))
    assert missing.status_code == 404

    updated = await client.patch(
        "/users/me/payment-profile",
        headers=auth_headers(user),
        json={
            "card_number": "4111111111111111",
            "cardholder_name": "TEST USER",
            "expiry_month": 12,
            "expiry_year": 2030,
            "cvv": "123",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["card_last_digits"] == "1111"
    assert updated.json()["card_last4"] == "1111"

    response = await client.get("/users/me/payment-profile", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["card_last_digits"] == "1111"
    assert response.json()["card_last4"] == "1111"


async def test_public_profile_by_username(client, db_session):
    user = await create_user(
        db_session,
        email="public@example.com",
        username="publicuser",
    )
    user.display_tag = "Public Author"
    await db_session.commit()

    response = await client.get("/users/by-username/publicuser")

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "publicuser"
    assert data["display_tag"] == "Public Author"
    assert "email" not in data


async def test_public_profile_returns_404_for_unknown_username(client):
    response = await client.get("/users/by-username/nobody")

    assert response.status_code == 404
