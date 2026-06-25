from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.factories import (
    auth_headers,
    create_author,
    create_book,
    create_promo_code,
    create_review,
    create_user,
)

CARD = {
    "card_number": "4111111111111111",
    "cardholder_name": "TEST USER",
    "expiry_month": 12,
    "expiry_year": 2030,
    "cvv": "123",
}


async def test_author_issues_promo_for_review(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=reader)

    response = await client.post(
        f"/reviews/{review.id}/promo-code",
        headers=auth_headers(author),
        json={"discount_percent": 20},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["discount_percent"] == "20.00"
    assert data["recipient_user_id"] == str(reader.id)
    assert data["author_id"] == str(author.id)
    assert data["code"]
    assert data["used_at"] is None


async def test_non_author_cannot_issue_promo(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    other = await create_user(db_session, email="other@example.com", username="other")
    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=reader)

    response = await client.post(
        f"/reviews/{review.id}/promo-code",
        headers=auth_headers(other),
        json={"discount_percent": 10},
    )

    assert response.status_code == 403


async def test_duplicate_promo_per_review(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=reader)

    first = await client.post(
        f"/reviews/{review.id}/promo-code",
        headers=auth_headers(author),
        json={"discount_percent": 15},
    )
    assert first.status_code == 201

    duplicate = await client.post(
        f"/reviews/{review.id}/promo-code",
        headers=auth_headers(author),
        json={"discount_percent": 25},
    )
    assert duplicate.status_code == 409


async def test_author_cannot_issue_promo_to_self(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=author)

    response = await client.post(
        f"/reviews/{review.id}/promo-code",
        headers=auth_headers(author),
        json={"discount_percent": 10},
    )

    assert response.status_code == 400


async def test_purchase_with_promo_on_another_author_book(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book_a = await create_book(db_session, author=author, title="Book A", sale_price=Decimal("100.00"))
    book_b = await create_book(db_session, author=author, title="Book B", sale_price=Decimal("200.00"))
    review = await create_review(db_session, book=book_a, user=reader)

    issued = await client.post(
        f"/reviews/{review.id}/promo-code",
        headers=auth_headers(author),
        json={"discount_percent": 20},
    )
    promo_code = issued.json()["code"]

    purchase = await client.post(
        f"/earnings/purchases/{book_b.id}",
        headers=auth_headers(reader),
        json={**CARD, "promo_code": promo_code},
    )

    assert purchase.status_code == 201
    assert purchase.json()["price_paid"] == "160.00"
    assert purchase.json()["author_earning"] == "112.00"


async def test_purchase_with_promo_wrong_recipient(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    other = await create_user(db_session, email="other@example.com", username="other")
    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=reader)
    promo = await create_promo_code(db_session, review=review, author=author, recipient=reader)

    response = await client.post(
        f"/earnings/purchases/{book.id}",
        headers=auth_headers(other),
        json={**CARD, "promo_code": promo.code},
    )

    assert response.status_code == 403


async def test_purchase_with_used_promo(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=reader)
    promo = await create_promo_code(
        db_session,
        review=review,
        author=author,
        recipient=reader,
        used_at=datetime.now(timezone.utc),
    )

    response = await client.post(
        f"/earnings/purchases/{book.id}",
        headers=auth_headers(reader),
        json={**CARD, "promo_code": promo.code},
    )

    assert response.status_code == 400


async def test_purchase_with_expired_promo(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=reader)
    promo = await create_promo_code(
        db_session,
        review=review,
        author=author,
        recipient=reader,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    response = await client.post(
        f"/earnings/purchases/{book.id}",
        headers=auth_headers(reader),
        json={**CARD, "promo_code": promo.code},
    )

    assert response.status_code == 400


async def test_purchase_without_promo_unchanged(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author, sale_price=Decimal("100.00"))

    purchase = await client.post(
        f"/earnings/purchases/{book.id}",
        headers=auth_headers(reader),
        json=CARD,
    )

    assert purchase.status_code == 201
    assert purchase.json()["price_paid"] == "100.00"
    assert purchase.json()["author_earning"] == "70.00"


async def test_reader_lists_active_promo_codes(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book_a = await create_book(db_session, author=author, title="Book A")
    book_b = await create_book(db_session, author=author, title="Book B")
    review_a = await create_review(db_session, book=book_a, user=reader)
    review_b = await create_review(db_session, book=book_b, user=reader)
    await create_promo_code(
        db_session, review=review_a, author=author, recipient=reader, code="ACTIVE1"
    )
    await create_promo_code(
        db_session,
        review=review_b,
        author=author,
        recipient=reader,
        code="EXPIRED1",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    response = await client.get("/users/me/promo-codes", headers=auth_headers(reader))

    assert response.status_code == 200
    codes = [item["code"] for item in response.json()]
    assert codes == ["ACTIVE1"]


async def test_author_lists_issued_promo_codes(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)
    review = await create_review(db_session, book=book, user=reader)
    await create_promo_code(db_session, review=review, author=author, recipient=reader, code="AUTHLIST1")

    response = await client.get("/earnings/promo-codes", headers=auth_headers(author))

    assert response.status_code == 200
    assert response.json()[0]["code"] == "AUTHLIST1"
