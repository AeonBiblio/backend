from datetime import datetime, timezone
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book_rating import BookRating
from app.models.review import Review


class BookRatingStats(NamedTuple):
    average_rating: Decimal | None
    ratings_count: int
    my_rating: int | None
    reviews_count: int


async def get_book_rating_stats(
    db: AsyncSession, book_id, user_id=None
) -> BookRatingStats:
    stats = await db.execute(
        select(func.avg(BookRating.score), func.count(BookRating.id)).where(BookRating.book_id == book_id)
    )
    avg_raw, count = stats.one()
    average = Decimal(str(round(float(avg_raw), 1))) if avg_raw is not None else None
    ratings_count = int(count or 0)

    reviews_result = await db.execute(
        select(func.count(Review.id)).where(Review.book_id == book_id)
    )
    reviews_count = int(reviews_result.scalar() or 0)

    my_score = None
    if user_id is not None:
        mine = await db.execute(
            select(BookRating.score).where(
                BookRating.book_id == book_id,
                BookRating.user_id == user_id,
            )
        )
        my_score = mine.scalar_one_or_none()

    return BookRatingStats(average, ratings_count, my_score, reviews_count)


async def batch_reviews_count(db: AsyncSession, book_ids: list) -> dict:
    if not book_ids:
        return {}
    result = await db.execute(
        select(Review.book_id, func.count(Review.id))
        .where(Review.book_id.in_(book_ids))
        .group_by(Review.book_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


def period_bounds(year: int | None, month: int | None) -> tuple[datetime | None, datetime | None]:
    """Return (start, end) UTC for filtering. None bounds = no filter."""
    if year is None:
        return None, None
    if month is not None:
        if month == 12:
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        return start, end
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return start, end
