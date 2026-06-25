import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.book_rating import period_bounds
from app.models.book import Book
from app.models.earnings import EarningSource, EarningTransaction, Purchase, SubscriptionRead
from app.models.subscription import PaymentStatus


async def get_author_stats(
    db: AsyncSession,
    author_id: uuid.UUID,
    *,
    year: int | None = None,
    month: int | None = None,
) -> dict:
    start, end = period_bounds(year, month)

    reads_stmt = (
        select(func.count(SubscriptionRead.id))
        .join(Book, Book.id == SubscriptionRead.book_id)
        .where(Book.author_id == author_id)
    )
    if start and end:
        reads_stmt = reads_stmt.where(
            SubscriptionRead.opened_at >= start,
            SubscriptionRead.opened_at < end,
        )
    total_reads = (await db.execute(reads_stmt)).scalar() or 0

    sales_stmt = (
        select(func.count(Purchase.id))
        .join(Book, Book.id == Purchase.book_id)
        .where(Book.author_id == author_id, Purchase.status == PaymentStatus.succeeded)
    )
    if start and end:
        sales_stmt = sales_stmt.where(
            Purchase.purchased_at >= start,
            Purchase.purchased_at < end,
        )
    total_sales = (await db.execute(sales_stmt)).scalar() or 0

    income_stmt = select(func.coalesce(func.sum(EarningTransaction.amount), 0)).where(
        EarningTransaction.author_id == author_id
    )
    if start and end:
        income_stmt = income_stmt.where(
            EarningTransaction.created_at >= start,
            EarningTransaction.created_at < end,
        )
    period_earned = (await db.execute(income_stmt)).scalar() or Decimal("0")

    from app.models.earnings import AuthorBalance

    balance_result = await db.execute(
        select(AuthorBalance).where(AuthorBalance.author_id == author_id)
    )
    balance = balance_result.scalar_one_or_none()

    period = None
    if year is not None:
        period = {"year": year, "month": month}

    return {
        "total_reads": total_reads,
        "total_sales": total_sales,
        "total_earned": period_earned if (start and end) else (balance.total_earned if balance else Decimal("0")),
        "period_earned": period_earned,
        "available_amount": balance.available_amount if balance else Decimal("0"),
        "pending_amount": balance.pending_amount if balance else Decimal("0"),
        "period": period,
    }


async def get_author_book_stats(
    db: AsyncSession,
    author_id: uuid.UUID,
    *,
    q: str | None = None,
    year: int | None = None,
    month: int | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[dict]:
    start, end = period_bounds(year, month)

    books_stmt = select(Book).where(Book.author_id == author_id)
    if q:
        books_stmt = books_stmt.where(Book.title.ilike(f"%{q}%"))
    books_stmt = books_stmt.order_by(Book.created_at.desc()).offset(offset).limit(limit)
    books = list((await db.execute(books_stmt)).scalars().all())
    if not books:
        return []

    book_ids = [b.id for b in books]
    results = []

    for book in books:
        reads_stmt = select(func.count(SubscriptionRead.id)).where(SubscriptionRead.book_id == book.id)
        if start and end:
            reads_stmt = reads_stmt.where(
                SubscriptionRead.opened_at >= start,
                SubscriptionRead.opened_at < end,
            )
        reads = (await db.execute(reads_stmt)).scalar() or 0

        sales_stmt = select(func.count(Purchase.id)).where(
            Purchase.book_id == book.id,
            Purchase.status == PaymentStatus.succeeded,
        )
        if start and end:
            sales_stmt = sales_stmt.where(
                Purchase.purchased_at >= start,
                Purchase.purchased_at < end,
            )
        sales = (await db.execute(sales_stmt)).scalar() or 0

        purchase_income_stmt = select(func.coalesce(func.sum(EarningTransaction.amount), 0)).where(
            EarningTransaction.author_id == author_id,
            EarningTransaction.source_type == EarningSource.purchase,
            EarningTransaction.source_id.in_(
                select(Purchase.id).where(Purchase.book_id == book.id)
            ),
        )
        read_income_stmt = select(func.coalesce(func.sum(EarningTransaction.amount), 0)).where(
            EarningTransaction.author_id == author_id,
            EarningTransaction.source_type == EarningSource.subscription_read,
            EarningTransaction.source_id.in_(
                select(SubscriptionRead.id).where(SubscriptionRead.book_id == book.id)
            ),
        )
        if start and end:
            purchase_income_stmt = purchase_income_stmt.where(
                EarningTransaction.created_at >= start,
                EarningTransaction.created_at < end,
            )
            read_income_stmt = read_income_stmt.where(
                EarningTransaction.created_at >= start,
                EarningTransaction.created_at < end,
            )
        purchase_income = (await db.execute(purchase_income_stmt)).scalar() or Decimal("0")
        read_income = (await db.execute(read_income_stmt)).scalar() or Decimal("0")
        income = purchase_income + read_income

        results.append(
            {
                "book_id": book.id,
                "title": book.title,
                "cover_key": book.cover_key,
                "reads": reads,
                "sales": sales,
                "income": income,
            }
        )

    return results
