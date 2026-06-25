import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, BookStatus
from app.models.earnings import Purchase
from app.models.subscription import SubscriptionStatus, UserSubscription
from app.models.user import User


async def _has_active_subscription(user_id: uuid.UUID, db: AsyncSession) -> bool:
    result = await db.execute(
        select(UserSubscription).where(
            UserSubscription.user_id == user_id,
            UserSubscription.status == SubscriptionStatus.active,
            UserSubscription.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none() is not None


async def _has_purchase(user_id: uuid.UUID, book_id: uuid.UUID, db: AsyncSession) -> bool:
    result = await db.execute(
        select(Purchase).where(Purchase.user_id == user_id, Purchase.book_id == book_id)
    )
    return result.scalar_one_or_none() is not None


async def check_book_access(user: User, book: Book, db: AsyncSession) -> tuple[bool, str]:
    """Проверка права читать книгу через API (не скачивание файла)."""
    if not book.file_key:
        return False, "no_file"

    if book.author_id == user.id:
        return True, "author"

    if book.status != BookStatus.published:
        return False, "not_published"

    has_purchase = await _has_purchase(user.id, book.id, db) if book.is_for_sale else False
    has_subscription = await _has_active_subscription(user.id, db) if book.is_in_subscription else False

    if has_purchase:
        return True, "purchased"

    if has_subscription and book.is_in_subscription:
        return True, "subscription"

    if book.is_for_sale and book.is_in_subscription:
        return False, "purchase_or_subscription_required"

    if book.is_for_sale:
        return False, "purchase_required"

    if book.is_in_subscription:
        return False, "subscription_required"

    return True, "ok"
