from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.book import Book, BookStatus, GenreTag
from app.models.earnings import AuthorBalance, Purchase
from app.models.library import Readlist
from app.models.promo import PromoCode
from app.models.review import Review, ReviewSentiment
from app.models.subscription import PaymentStatus, SubscriptionPlan, SubscriptionStatus, UserSubscription
from app.models.user import PaymentProfile, User, UserRole


def auth_headers(user: User) -> dict[str, str]:
    return {"Cookie": f"aeon_access_token={create_access_token(str(user.id))}"}


async def create_user(
    db: AsyncSession,
    *,
    email: str = "user@example.com",
    username: str = "user",
    password: str = "password123",
    is_blocked: bool = False,
    role: UserRole = UserRole.reader,
) -> User:
    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        is_blocked=is_blocked,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_author(
    db: AsyncSession,
    *,
    email: str = "author@example.com",
    username: str = "author",
    password: str = "password123",
    is_blocked: bool = False,
) -> User:
    return await create_user(
        db,
        email=email,
        username=username,
        password=password,
        is_blocked=is_blocked,
        role=UserRole.author,
    )


async def create_book(
    db: AsyncSession,
    *,
    author: User,
    title: str = "Test Book",
    status: BookStatus = BookStatus.published,
    is_for_sale: bool = True,
    sale_price: Decimal = Decimal("100.00"),
    is_in_subscription: bool = True,
    subscription_payout_amount: Decimal = Decimal("10.00"),
    file_key: str | None = "books/test.epub",
) -> Book:
    book = Book(
        author_id=author.id,
        title=title,
        description="A test book",
        status=status,
        is_for_sale=is_for_sale,
        sale_price=sale_price,
        is_in_subscription=is_in_subscription,
        subscription_payout_amount=subscription_payout_amount,
        file_key=file_key,
        file_format="epub" if file_key else None,
        file_size_bytes=1024 if file_key else None,
        published_at=datetime.now(timezone.utc) if status == BookStatus.published else None,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def create_genre_tag(db: AsyncSession, *, name: str = "Fantasy") -> GenreTag:
    tag = GenreTag(name=name, created_at=datetime.now(timezone.utc))
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def create_subscription_plan(
    db: AsyncSession,
    *,
    name: str = "Monthly",
    price: Decimal = Decimal("499.00"),
    duration_days: int = 30,
    is_active: bool = True,
) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        name=name,
        price=price,
        duration_days=duration_days,
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def create_active_subscription(
    db: AsyncSession,
    *,
    user: User,
    plan: SubscriptionPlan,
    expires_delta: timedelta = timedelta(days=30),
) -> UserSubscription:
    now = datetime.now(timezone.utc)
    subscription = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.active,
        started_at=now,
        expires_at=now + expires_delta,
        auto_renew=True,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def create_payment_profile(
    db: AsyncSession,
    *,
    user: User,
    payment_method_token: str = "pm_mock_1111",
) -> PaymentProfile:
    profile = PaymentProfile(user_id=user.id, payment_method_token=payment_method_token)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def create_author_balance(
    db: AsyncSession,
    *,
    author: User,
    available_amount: Decimal = Decimal("100.00"),
) -> AuthorBalance:
    balance = AuthorBalance(
        author_id=author.id,
        available_amount=available_amount,
        pending_amount=Decimal("0"),
        total_earned=available_amount,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(balance)
    await db.commit()
    await db.refresh(balance)
    return balance


async def create_readlist(
    db: AsyncSession,
    *,
    user: User,
    title: str = "Reading list",
    is_public: bool = True,
) -> Readlist:
    readlist = Readlist(
        user_id=user.id,
        title=title,
        description="Test readlist",
        is_public=is_public,
    )
    db.add(readlist)
    await db.commit()
    await db.refresh(readlist)
    return readlist


async def create_purchase(
    db: AsyncSession,
    *,
    user: User,
    book: Book,
    price_paid: Decimal | None = None,
) -> Purchase:
    now = datetime.now(timezone.utc)
    paid = price_paid or book.sale_price or Decimal("100.00")
    purchase = Purchase(
        user_id=user.id,
        book_id=book.id,
        price_paid=paid,
        author_earning=(paid * Decimal("0.7")).quantize(Decimal("0.01")),
        status=PaymentStatus.succeeded,
        purchased_at=now,
    )
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)
    return purchase


async def create_review(
    db: AsyncSession,
    *,
    book: Book,
    user: User,
    rating: int = 5,
    sentiment: ReviewSentiment = ReviewSentiment.neutral,
    text: str = "Great book",
) -> Review:
    review = Review(
        book_id=book.id,
        user_id=user.id,
        rating=rating,
        sentiment=sentiment,
        text=text,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


async def create_promo_code(
    db: AsyncSession,
    *,
    review: Review,
    author: User,
    recipient: User,
    code: str = "PROMO20OFF",
    discount_percent: Decimal = Decimal("20"),
    expires_at: datetime | None = None,
    used_at: datetime | None = None,
    purchase_id=None,
) -> PromoCode:
    now = datetime.now(timezone.utc)
    if expires_at is None:
        expires_at = now + timedelta(days=30)
    promo = PromoCode(
        code=code,
        review_id=review.id,
        author_id=author.id,
        recipient_user_id=recipient.id,
        discount_percent=discount_percent,
        expires_at=expires_at,
        used_at=used_at,
        purchase_id=purchase_id,
        created_at=now,
    )
    db.add(promo)
    await db.commit()
    await db.refresh(promo)
    return promo
