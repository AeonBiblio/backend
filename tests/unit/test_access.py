from decimal import Decimal

from app.core.access import check_book_access
from app.models.book import Book, BookStatus
from tests.factories import create_active_subscription, create_author, create_book, create_purchase, create_subscription_plan, create_user


async def test_author_can_access_own_draft(db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.draft)

    can_read, reason = await check_book_access(author, book, db_session)

    assert can_read is True
    assert reason == "author"


async def test_reader_needs_purchase_for_sale_only_book(db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(
        db_session,
        author=author,
        status=BookStatus.published,
        is_for_sale=True,
        is_in_subscription=False,
        sale_price=Decimal("50.00"),
    )

    can_read, reason = await check_book_access(reader, book, db_session)

    assert can_read is False
    assert reason == "purchase_required"


async def test_reader_with_purchase_can_access(db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author, is_for_sale=True, is_in_subscription=False)
    await create_purchase(db_session, user=reader, book=book)

    can_read, reason = await check_book_access(reader, book, db_session)

    assert can_read is True
    assert reason == "purchased"


async def test_reader_with_subscription_can_access_subscription_book(db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    plan = await create_subscription_plan(db_session)
    await create_active_subscription(db_session, user=reader, plan=plan)
    book = await create_book(
        db_session,
        author=author,
        is_for_sale=False,
        is_in_subscription=True,
    )

    can_read, reason = await check_book_access(reader, book, db_session)

    assert can_read is True
    assert reason == "subscription"


async def test_book_without_file_is_not_readable(db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = Book(
        author_id=author.id,
        title="No file",
        status=BookStatus.published,
        file_key=None,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)

    can_read, reason = await check_book_access(author, book, db_session)

    assert can_read is False
    assert reason == "no_file"
