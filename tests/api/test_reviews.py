from tests.factories import auth_headers, create_author, create_book, create_user


async def test_review_lifecycle(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)

    created = await client.post(
        f"/books/{book.id}/reviews",
        headers=auth_headers(reader),
        json={"rating": 5, "text": "Great book"},
    )
    assert created.status_code == 201
    review_id = created.json()["id"]

    listed = await client.get(f"/books/{book.id}/reviews")
    assert listed.status_code == 200
    assert listed.json()[0]["text"] == "Great book"

    updated = await client.patch(
        f"/reviews/{review_id}",
        headers=auth_headers(reader),
        json={"rating": 4, "text": "Still good"},
    )
    assert updated.status_code == 200
    assert updated.json()["rating"] == 4

    deleted = await client.delete(f"/reviews/{review_id}", headers=auth_headers(reader))
    assert deleted.status_code == 204


async def test_review_rejects_duplicate_for_same_user_and_book(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)
    payload = {"rating": 5, "text": "Great book"}

    assert (
        await client.post(
            f"/books/{book.id}/reviews",
            headers=auth_headers(reader),
            json=payload,
        )
    ).status_code == 201
    duplicate = await client.post(
        f"/books/{book.id}/reviews",
        headers=auth_headers(reader),
        json=payload,
    )

    assert duplicate.status_code == 409


async def test_review_owner_guard_rejects_other_users(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    other = await create_user(db_session, email="other@example.com", username="other")
    book = await create_book(db_session, author=author)
    created = await client.post(
        f"/books/{book.id}/reviews",
        headers=auth_headers(reader),
        json={"rating": 5, "text": "Great book"},
    )

    response = await client.patch(
        f"/reviews/{created.json()['id']}",
        headers=auth_headers(other),
        json={"rating": 1},
    )

    assert response.status_code == 403


async def test_create_review_returns_404_for_unknown_book(client, db_session):
    reader = await create_user(db_session, email="reader@example.com", username="reader")

    response = await client.post(
        "/books/00000000-0000-0000-0000-000000000001/reviews",
        headers=auth_headers(reader),
        json={"rating": 5},
    )

    assert response.status_code == 404
