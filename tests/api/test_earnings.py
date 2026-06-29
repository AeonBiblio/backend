from decimal import Decimal

from tests.factories import (
    auth_headers,
    create_active_subscription,
    create_author_balance,
    create_author,
    create_book,
    create_payment_profile,
    create_subscription_plan,
    create_user,
)


async def test_purchase_book_credits_author_and_lists_purchase(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    await create_payment_profile(db_session, user=reader)
    book = await create_book(db_session, author=author, sale_price=Decimal("100.00"))

    purchase = await client.post(
        f"/earnings/purchases/{book.id}",
        headers=auth_headers(reader),
        json={},
    )
    assert purchase.status_code == 201
    assert purchase.json()["author_earning"] == "70.00"

    duplicate = await client.post(
        f"/earnings/purchases/{book.id}",
        headers=auth_headers(reader),
        json={},
    )
    assert duplicate.status_code == 409

    purchases = await client.get("/earnings/purchases", headers=auth_headers(reader))
    assert purchases.status_code == 200
    assert purchases.json()[0]["book_id"] == str(book.id)

    balance = await client.get("/earnings/balance", headers=auth_headers(author))
    assert balance.status_code == 200
    assert balance.json()["available_amount"] == "70.00"

    stats = await client.get("/earnings/stats", headers=auth_headers(author))
    assert stats.status_code == 200
    assert stats.json()["total_sales"] == 1
    assert stats.json()["total_earned"] == "70.00"

    transactions = await client.get("/earnings/transactions", headers=auth_headers(author))
    assert transactions.status_code == 200
    assert transactions.json()[0]["source_type"] == "purchase"


async def test_purchase_book_returns_404_when_not_for_sale(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    await create_payment_profile(db_session, user=reader)
    book = await create_book(db_session, author=author, is_for_sale=False)

    response = await client.post(
        f"/earnings/purchases/{book.id}",
        headers=auth_headers(reader),
        json={},
    )

    assert response.status_code == 404


async def test_payout_deducts_available_balance_and_can_be_listed(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    await create_author_balance(db_session, author=author, available_amount=Decimal("100.00"))

    payout = await client.post(
        "/earnings/payouts",
        headers=auth_headers(author),
        json={"amount": "40.00"},
    )
    assert payout.status_code == 201
    assert payout.json()["status"] == "pending"

    balance = await client.get("/earnings/balance", headers=auth_headers(author))
    assert balance.json()["available_amount"] == "60.00"

    payouts = await client.get("/earnings/payouts", headers=auth_headers(author))
    assert payouts.status_code == 200
    assert payouts.json()[0]["amount"] == "40.00"


async def test_payout_rejects_insufficient_balance(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")

    response = await client.post(
        "/earnings/payouts",
        headers=auth_headers(author),
        json={"amount": "40.00"},
    )

    assert response.status_code == 400


async def test_subscription_read_credits_author_once(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    plan = await create_subscription_plan(db_session)
    await create_active_subscription(db_session, user=reader, plan=plan)
    book = await create_book(db_session, author=author, subscription_payout_amount=Decimal("12.50"))

    opened = await client.post(f"/earnings/reads/{book.id}", headers=auth_headers(reader))
    assert opened.status_code == 200
    assert opened.json() == {"status": "opened", "payout_amount": "12.50"}

    repeated = await client.post(f"/earnings/reads/{book.id}", headers=auth_headers(reader))
    assert repeated.status_code == 200
    assert repeated.json() == {"status": "already_opened"}

    balance = await client.get("/earnings/balance", headers=auth_headers(author))
    assert balance.json()["available_amount"] == "12.50"


async def test_subscription_read_requires_active_subscription(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)

    response = await client.post(f"/earnings/reads/{book.id}", headers=auth_headers(reader))

    assert response.status_code == 403


async def test_balance_returns_404_before_author_has_earnings(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")

    response = await client.get("/earnings/balance", headers=auth_headers(author))

    assert response.status_code == 404
