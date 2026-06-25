from decimal import Decimal

from app.models.book import BookStatus
from tests.factories import (
    auth_headers,
    create_author,
    create_book,
    create_genre_tag,
    create_review,
    create_user,
)


async def test_book_rating_aggregate_and_my_rating(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader1 = await create_user(db_session, email="r1@example.com", username="reader1")
    reader2 = await create_user(db_session, email="r2@example.com", username="reader2")
    book = await create_book(db_session, author=author)

    assert (await client.put(f"/books/{book.id}/rating", headers=auth_headers(reader1), json={"score": 8})).status_code == 200
    assert (await client.put(f"/books/{book.id}/rating", headers=auth_headers(reader2), json={"score": 10})).status_code == 200

    public = await client.get(f"/books/{book.id}/rating")
    assert public.status_code == 200
    assert public.json()["average_rating"] == "9.0"
    assert public.json()["ratings_count"] == 2
    assert public.json()["my_rating"] is None

    mine = await client.get(f"/books/{book.id}/rating", headers=auth_headers(reader1))
    assert mine.json()["my_rating"] == 8

    detail = await client.get(f"/books/{book.id}", headers=auth_headers(reader1))
    assert detail.json()["average_rating"] == "9.0"
    assert detail.json()["my_rating"] == 8


async def test_review_sentiment_and_promo_issued_flag(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)

    created = await client.post(
        f"/books/{book.id}/reviews",
        headers=auth_headers(reader),
        json={"rating": 5, "sentiment": "positive", "text": "Loved it"},
    )
    assert created.status_code == 201
    assert created.json()["sentiment"] == "positive"
    assert created.json()["promo_issued"] is False
    review_id = created.json()["id"]

    issued = await client.post(
        f"/reviews/{review_id}/promo-code",
        headers=auth_headers(author),
        json={"discount_percent": 15},
    )
    assert issued.status_code == 201

    listed = await client.get(f"/books/{book.id}/reviews")
    assert listed.status_code == 200
    assert listed.json()[0]["promo_issued"] is True
    assert listed.json()[0]["sentiment"] == "positive"


async def test_filter_books_by_genre_tag(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    tag_fantasy = await create_genre_tag(db_session, name="Fantasy")
    tag_romance = await create_genre_tag(db_session, name="Romance")
    book_a = await create_book(db_session, author=author, title="Fantasy Book")
    book_b = await create_book(db_session, author=author, title="Romance Book")

    assert (
        await client.put(
            f"/books/{book_a.id}/genre-tags",
            headers=auth_headers(author),
            json={"genre_tag_ids": [str(tag_fantasy.id)]},
        )
    ).status_code == 200
    assert (
        await client.put(
            f"/books/{book_b.id}/genre-tags",
            headers=auth_headers(author),
            json={"genre_tag_ids": [str(tag_romance.id)]},
        )
    ).status_code == 200

    filtered = await client.get("/books", params={"genre_tag_id": str(tag_fantasy.id)})
    assert filtered.status_code == 200
    ids = [item["id"] for item in filtered.json()]
    assert ids == [str(book_a.id)]


async def test_publish_book_from_draft_and_pending(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")

    draft = await create_book(db_session, author=author, status=BookStatus.draft, title="Draft")
    published = await client.post(f"/books/{draft.id}/publish", headers=auth_headers(author))
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None

    pending_book = await create_book(db_session, author=author, status=BookStatus.pending, title="Pending")
    published_pending = await client.post(f"/books/{pending_book.id}/publish", headers=auth_headers(author))
    assert published_pending.status_code == 200
    assert published_pending.json()["status"] == "published"


async def test_publish_rejects_already_published(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)

    response = await client.post(f"/books/{book.id}/publish", headers=auth_headers(author))
    assert response.status_code == 400


async def test_library_recent_returns_most_recently_updated(client, db_session):
    user = await create_user(db_session, email="reader@example.com", username="reader")
    author = await create_author(db_session, email="author@example.com", username="author")
    book_old = await create_book(db_session, author=author, title="Old")
    book_new = await create_book(db_session, author=author, title="New")

    await client.put(
        f"/library/status/{book_old.id}",
        headers=auth_headers(user),
        json={"status": "reading", "progress_percent": 10},
    )
    await client.put(
        f"/library/status/{book_new.id}",
        headers=auth_headers(user),
        json={"status": "reading", "progress_percent": 5},
    )

    recent = await client.get("/library/recent", headers=auth_headers(user))
    assert recent.status_code == 200
    assert recent.json()[0]["title"] == "New"
    assert recent.json()[0]["book_id"] == str(book_new.id)


async def test_seed_includes_yearly_plan(client, db_session):
    from scripts.seed import seed

    await seed()
    plans = await client.get("/subscriptions/plans")
    assert plans.status_code == 200
    names = {p["name"] for p in plans.json()}
    prices = {p["name"]: p["price"] for p in plans.json()}
    assert "Годовая" in names
    assert prices["Годовая"] == "1800.00"
