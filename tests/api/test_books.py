from decimal import Decimal

from app.models.book import BookStatus
from tests.factories import (
    auth_headers,
    create_active_subscription,
    create_author,
    create_book,
    create_genre_tag,
    create_purchase,
    create_subscription_plan,
    create_user,
)


async def test_create_list_update_submit_and_delete_book(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")

    created = await client.post(
        "/books",
        headers=auth_headers(author),
        json={
            "title": "Draft Book",
            "description": "Draft description",
            "is_for_sale": True,
            "sale_price": "199.00",
        },
    )
    assert created.status_code == 201
    book_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    listed = await client.get("/books", params={"status": "draft", "q": "Draft"})
    assert listed.status_code == 200
    assert [book["id"] for book in listed.json()] == [book_id]

    updated = await client.patch(
        f"/books/{book_id}",
        headers=auth_headers(author),
        json={"title": "Updated Book"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated Book"

    submitted = await client.post(f"/books/{book_id}/submit", headers=auth_headers(author))
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending"

    deleted = await client.delete(f"/books/{book_id}", headers=auth_headers(author))
    assert deleted.status_code == 204


async def test_book_owner_guards_reject_other_users(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author, status=BookStatus.draft)

    response = await client.patch(
        f"/books/{book.id}",
        headers=auth_headers(reader),
        json={"title": "Stolen title"},
    )

    assert response.status_code == 403


async def test_book_upload_and_author_can_read_content(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)

    cover = await client.post(f"/books/{book.id}/cover", headers=auth_headers(author))
    assert cover.status_code == 200
    assert cover.json()["object_key"] == f"covers/{book.id}.jpg"

    confirm_cover = await client.patch(
        f"/books/{book.id}/cover-key",
        headers=auth_headers(author),
        params={"object_key": cover.json()["object_key"]},
    )
    assert confirm_cover.status_code == 200
    assert confirm_cover.json()["cover_key"] == cover.json()["object_key"]

    upload = await client.post(
        f"/books/{book.id}/file",
        headers=auth_headers(author),
        params={"file_format": "epub"},
    )
    assert upload.status_code == 200
    assert upload.json()["object_key"] == f"books/{book.id}.epub"

    confirm_file = await client.patch(
        f"/books/{book.id}/file-key",
        headers=auth_headers(author),
        params={
            "object_key": upload.json()["object_key"],
            "file_format": "epub",
            "file_size_bytes": 2048,
        },
    )
    assert confirm_file.status_code == 200

    access = await client.get(f"/books/{book.id}/access", headers=auth_headers(author))
    assert access.status_code == 200
    assert access.json()["can_read"] is True
    assert access.json()["reason"] == "author"

    content = await client.get(f"/books/{book.id}/content", headers=auth_headers(author))
    assert content.status_code == 200
    assert content.headers["content-disposition"] == "inline"
    assert len(content.content) > 0


async def test_content_rejects_reader_without_purchase_or_subscription(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(
        db_session,
        author=author,
        status=BookStatus.published,
        is_for_sale=True,
        is_in_subscription=False,
        sale_price=Decimal("100.00"),
    )

    access = await client.get(f"/books/{book.id}/access", headers=auth_headers(reader))
    assert access.status_code == 200
    assert access.json()["can_read"] is False
    assert access.json()["reason"] == "purchase_required"

    response = await client.get(f"/books/{book.id}/content", headers=auth_headers(reader))
    assert response.status_code == 403


async def test_content_allows_reader_with_purchase(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(
        db_session,
        author=author,
        status=BookStatus.published,
        is_for_sale=True,
        is_in_subscription=False,
    )
    await create_purchase(db_session, user=reader, book=book)

    access = await client.get(f"/books/{book.id}/access", headers=auth_headers(reader))
    assert access.json()["can_read"] is True
    assert access.json()["reason"] == "purchased"

    content = await client.get(f"/books/{book.id}/content", headers=auth_headers(reader))
    assert content.status_code == 200


async def test_content_chunk_returns_range(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)

    chunk = await client.get(
        f"/books/{book.id}/content/chunk",
        headers=auth_headers(author),
        params={"offset": 0, "size": 1024},
    )
    assert chunk.status_code == 200
    assert chunk.headers["content-range"].startswith("bytes 0-")
    assert len(chunk.content) == 1024


async def test_content_rejects_unpublished_book_for_non_author(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author, status=BookStatus.draft)

    response = await client.get(f"/books/{book.id}/content", headers=auth_headers(reader))
    assert response.status_code == 403


async def test_subscription_reader_can_read_in_subscription_book(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    plan = await create_subscription_plan(db_session)
    await create_active_subscription(db_session, user=reader, plan=plan)
    book = await create_book(
        db_session,
        author=author,
        status=BookStatus.published,
        is_for_sale=False,
        is_in_subscription=True,
    )

    access = await client.get(f"/books/{book.id}/access", headers=auth_headers(reader))
    assert access.json()["can_read"] is True
    assert access.json()["reason"] == "subscription"


async def test_recommendations_returns_new_and_popular(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    await create_book(db_session, author=author, title="Book A")
    await create_book(db_session, author=author, title="Book B")

    response = await client.get("/books/recommendations", params={"limit": 5})
    assert response.status_code == 200
    data = response.json()
    assert "new" in data and "popular" in data
    assert len(data["new"]) >= 1


async def test_genre_tags_can_be_created_listed_and_attached(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.draft)

    created = await client.post(
        "/books/genre-tags",
        headers=auth_headers(author),
        json={"name": "Fantasy"},
    )
    assert created.status_code == 201
    tag_id = created.json()["id"]

    duplicate = await client.post(
        "/books/genre-tags",
        headers=auth_headers(author),
        json={"name": "Fantasy"},
    )
    assert duplicate.status_code == 409

    listed = await client.get("/books/genre-tags/all")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Fantasy"

    attached = await client.put(
        f"/books/{book.id}/genre-tags",
        headers=auth_headers(author),
        json={"genre_tag_ids": [tag_id]},
    )
    assert attached.status_code == 200
    assert attached.json()[0]["id"] == tag_id

    book_tags = await client.get(f"/books/{book.id}/genre-tags")
    assert book_tags.status_code == 200
    assert book_tags.json()[0]["name"] == "Fantasy"


async def test_book_user_tags_are_unique_per_user(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)

    added = await client.post(
        f"/books/{book.id}/user-tags",
        headers=auth_headers(reader),
        json={"name": "Cozy"},
    )
    assert added.status_code == 201
    tag_id = added.json()["id"]

    duplicate = await client.post(
        f"/books/{book.id}/user-tags",
        headers=auth_headers(reader),
        json={"name": "Cozy"},
    )
    assert duplicate.status_code == 409

    listed = await client.get(f"/books/{book.id}/user-tags")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Cozy"

    removed = await client.delete(
        f"/books/{book.id}/user-tags/{tag_id}",
        headers=auth_headers(reader),
    )
    assert removed.status_code == 204


async def test_set_book_genre_tags_returns_404_for_unknown_tag(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author)
    tag = await create_genre_tag(db_session, name="Unused")
    await db_session.delete(tag)
    await db_session.commit()

    response = await client.put(
        f"/books/{book.id}/genre-tags",
        headers=auth_headers(author),
        json={"genre_tag_ids": [str(tag.id)]},
    )

    assert response.status_code == 404
