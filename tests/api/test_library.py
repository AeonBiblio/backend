from tests.factories import auth_headers, create_author, create_book, create_readlist, create_user


async def test_book_status_can_be_set_listed_updated_and_removed(client, db_session):
    user = await create_user(db_session, email="reader@example.com", username="reader")
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author)

    created = await client.put(
        f"/library/status/{book.id}",
        headers=auth_headers(user),
        json={"status": "reading", "progress_percent": 25},
    )
    assert created.status_code == 200
    assert created.json()["progress_percent"] == 25

    updated = await client.put(
        f"/library/status/{book.id}",
        headers=auth_headers(user),
        json={"status": "finished", "progress_percent": 100},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "finished"

    listed = await client.get("/library/status", headers=auth_headers(user))
    assert listed.status_code == 200
    assert listed.json()[0]["book_id"] == str(book.id)

    removed = await client.delete(f"/library/status/{book.id}", headers=auth_headers(user))
    assert removed.status_code == 204


async def test_book_status_returns_404_for_unknown_book(client, db_session):
    user = await create_user(db_session, email="reader@example.com", username="reader")

    response = await client.put(
        "/library/status/00000000-0000-0000-0000-000000000001",
        headers=auth_headers(user),
        json={"status": "wishlist"},
    )

    assert response.status_code == 404


async def test_readlist_lifecycle_and_items(client, db_session):
    owner = await create_user(db_session, email="owner@example.com", username="owner")
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author)

    created = await client.post(
        "/library/readlists",
        headers=auth_headers(owner),
        json={"title": "Favorites", "description": "Top books", "is_public": True},
    )
    assert created.status_code == 201
    readlist_id = created.json()["id"]

    listed = await client.get("/library/readlists", headers=auth_headers(owner))
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Favorites"

    updated = await client.patch(
        f"/library/readlists/{readlist_id}",
        headers=auth_headers(owner),
        json={"title": "Updated favorites", "is_public": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_public"] is False

    item = await client.post(
        f"/library/readlists/{readlist_id}/books",
        headers=auth_headers(owner),
        json={"book_id": str(book.id)},
    )
    assert item.status_code == 201

    duplicate = await client.post(
        f"/library/readlists/{readlist_id}/books",
        headers=auth_headers(owner),
        json={"book_id": str(book.id)},
    )
    assert duplicate.status_code == 409

    items = await client.get(f"/library/readlists/{readlist_id}/books", headers=auth_headers(owner))
    assert items.status_code == 200
    assert items.json()[0]["book_id"] == str(book.id)

    removed = await client.delete(
        f"/library/readlists/{readlist_id}/books/{book.id}",
        headers=auth_headers(owner),
    )
    assert removed.status_code == 204

    deleted = await client.delete(f"/library/readlists/{readlist_id}", headers=auth_headers(owner))
    assert deleted.status_code == 204


async def test_public_readlist_is_accessible_to_other_user_but_private_is_not(client, db_session):
    owner = await create_user(db_session, email="owner@example.com", username="owner")
    other = await create_user(db_session, email="other@example.com", username="other")
    public_readlist = await create_readlist(db_session, user=owner, is_public=True)
    private_readlist = await create_readlist(db_session, user=owner, title="Private", is_public=False)

    public_response = await client.get(
        f"/library/readlists/{public_readlist.id}",
        headers=auth_headers(other),
    )
    private_response = await client.get(
        f"/library/readlists/{private_readlist.id}",
        headers=auth_headers(other),
    )

    assert public_response.status_code == 200
    assert private_response.status_code == 403
