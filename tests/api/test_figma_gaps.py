from datetime import datetime, timezone
from decimal import Decimal

from app.models.book import BookStatus
from tests.factories import auth_headers, create_author, create_book, create_payment_profile, create_review, create_user


async def test_book_includes_reviews_count(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    await create_payment_profile(db_session, user=reader)
    book = await create_book(db_session, author=author)
    await create_review(db_session, book=book, user=reader)

    await client.put(
        f"/books/{book.id}/rating",
        headers=auth_headers(reader),
        json={"score": 8},
    )

    detail = await client.get(f"/books/{book.id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["reviews_count"] == 1
    assert data["ratings_count"] == 1
    assert data["average_rating"] == "8.0"


async def test_review_vote_like_dislike_and_toggle(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    voter = await create_user(db_session, email="voter@example.com", username="voter")
    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=reader)

    liked = await client.put(
        f"/reviews/{review.id}/vote",
        headers=auth_headers(voter),
        json={"vote": "like"},
    )
    assert liked.status_code == 200
    assert liked.json()["likes_count"] == 1
    assert liked.json()["my_vote"] == "like"

    disliked = await client.put(
        f"/reviews/{review.id}/vote",
        headers=auth_headers(voter),
        json={"vote": "dislike"},
    )
    assert disliked.status_code == 200
    assert disliked.json()["likes_count"] == 0
    assert disliked.json()["dislikes_count"] == 1

    removed = await client.delete(
        f"/reviews/{review.id}/vote",
        headers=auth_headers(voter),
    )
    assert removed.status_code == 200
    assert removed.json()["dislikes_count"] == 0
    assert removed.json()["my_vote"] is None


async def test_review_list_includes_username_and_votes(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(
        db_session,
        email="slavik@example.com",
        username="slavik",
    )
    reader.display_tag = "#13"
    await db_session.commit()
    await db_session.refresh(reader)

    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=reader, text="Nice read")

    listed = await client.get(f"/books/{book.id}/reviews")
    assert listed.status_code == 200
    item = listed.json()[0]
    assert item["username"] == "slavik"
    assert item["display_tag"] == "#13"
    assert item["text"] == "Nice read"


async def test_author_stats_filtered_by_month(client, db_session):
    from tests.factories import create_active_subscription, create_subscription_plan

    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    plan = await create_subscription_plan(db_session)
    await create_active_subscription(db_session, user=reader, plan=plan)
    book = await create_book(db_session, author=author, subscription_payout_amount=Decimal("10.00"))

    await client.post(f"/earnings/reads/{book.id}", headers=auth_headers(reader))

    now = datetime.now(timezone.utc)
    all_time = await client.get("/earnings/stats", headers=auth_headers(author))
    assert all_time.status_code == 200
    assert all_time.json()["total_reads"] == 1

    filtered = await client.get(
        "/earnings/stats",
        headers=auth_headers(author),
        params={"year": now.year, "month": now.month},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total_reads"] == 1
    assert filtered.json()["period"] == {"year": now.year, "month": now.month}


async def test_author_stats_books_with_search(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book_a = await create_book(db_session, author=author, title="Alpha Book", sale_price=Decimal("100.00"))
    await create_book(db_session, author=author, title="Beta Book", sale_price=Decimal("50.00"))

    await client.post(
        f"/earnings/purchases/{book_a.id}",
        headers=auth_headers(reader),
        json={},
    )

    stats = await client.get(
        "/earnings/stats/books",
        headers=auth_headers(author),
        params={"q": "Alpha"},
    )
    assert stats.status_code == 200
    assert len(stats.json()) == 1
    assert stats.json()[0]["title"] == "Alpha Book"
    assert stats.json()[0]["sales"] == 1
    assert Decimal(stats.json()[0]["income"]) > 0


async def test_user_role_from_registration(client, db_session):
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    author = await create_author(db_session, email="author@example.com", username="author")

    me_reader = await client.get("/users/me", headers=auth_headers(reader))
    assert me_reader.status_code == 200
    assert me_reader.json()["role"] == "reader"

    me_author = await client.get("/users/me", headers=auth_headers(author))
    assert me_author.status_code == 200
    assert me_author.json()["role"] == "author"


async def test_reader_forbidden_on_author_endpoints(client, db_session):
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    headers = auth_headers(reader)

    create_resp = await client.post(
        "/books",
        headers=headers,
        json={"title": "Forbidden", "description": "Nope"},
    )
    assert create_resp.status_code == 403
    assert create_resp.json()["detail"] == "Доступно только авторам"

    stats_resp = await client.get("/earnings/stats", headers=headers)
    assert stats_resp.status_code == 403
