"""Seed начальных данных: тарифы подписки и жанровые теги."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models import book, book_rating, earnings, library, promo, review, review_vote, subscription, user  # noqa: F401
from app.models.book import GenreTag
from app.models.subscription import SubscriptionPlan


GENRE_TAGS = ["Фэнтези", "Роман", "Детектив", "Научная фантастика", "Поэзия"]
SUBSCRIPTION_PLANS = [
    {"name": "Месячная", "price": Decimal("499.00"), "duration_days": 30},
    {"name": "Годовая", "price": Decimal("1800.00"), "duration_days": 365},
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        for plan_data in SUBSCRIPTION_PLANS:
            existing = await db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.name == plan_data["name"])
            )
            if existing.scalar_one_or_none() is None:
                db.add(
                    SubscriptionPlan(
                        name=plan_data["name"],
                        price=plan_data["price"],
                        duration_days=plan_data["duration_days"],
                        is_active=True,
                        created_at=datetime.now(timezone.utc),
                    )
                )

        for name in GENRE_TAGS:
            existing = await db.execute(select(GenreTag).where(GenreTag.name == name))
            if existing.scalar_one_or_none() is None:
                db.add(GenreTag(name=name, created_at=datetime.now(timezone.utc)))

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
