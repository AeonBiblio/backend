import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.author_stats import get_author_book_stats, get_author_stats
from app.core.dependencies import get_current_user, get_db, require_active_subscription, require_author
from app.models.book import Book, BookStatus
from app.models.earnings import (
    AuthorBalance,
    EarningSource,
    EarningTransaction,
    PayoutRequest,
    PayoutStatus,
    Purchase,
    SubscriptionRead,
)
from app.models.promo import PromoCode
from app.models.subscription import PaymentStatus
from app.models.user import User
from app.core.promo import apply_discount, validate_promo_for_purchase
from app.schemas.earnings import (
    AuthorBalanceOut,
    AuthorStatsOut,
    BookStatsItem,
    EarningTransactionOut,
    PayoutRequestCreate,
    PayoutRequestOut,
    PurchaseOut,
)
from app.schemas.payment import PurchaseWithPromo
from app.schemas.promo import PromoCodeOut

router = APIRouter()


# ---------- Author balance & stats ----------

@router.get("/balance", response_model=AuthorBalanceOut)
async def get_balance(
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuthorBalance).where(AuthorBalance.author_id == current_user.id)
    )
    balance = result.scalar_one_or_none()
    if not balance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Баланс не найден")
    return balance


@router.get("/stats", response_model=AuthorStatsOut)
async def get_author_stats_endpoint(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    stats = await get_author_stats(db, current_user.id, year=year, month=month)
    return AuthorStatsOut(**stats)


@router.get("/stats/books", response_model=list[BookStatsItem])
async def get_author_book_stats_endpoint(
    q: str | None = Query(default=None),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    items = await get_author_book_stats(
        db,
        current_user.id,
        q=q,
        year=year,
        month=month,
        offset=offset,
        limit=limit,
    )
    return [BookStatsItem(**item) for item in items]


@router.get("/transactions", response_model=list[EarningTransactionOut])
async def list_transactions(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EarningTransaction)
        .where(EarningTransaction.author_id == current_user.id)
        .order_by(EarningTransaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


# ---------- Payouts ----------

@router.post("/payouts", response_model=PayoutRequestOut, status_code=status.HTTP_201_CREATED)
async def request_payout(
    body: PayoutRequestCreate,
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    balance_result = await db.execute(
        select(AuthorBalance).where(AuthorBalance.author_id == current_user.id)
    )
    balance = balance_result.scalar_one_or_none()
    if not balance or balance.available_amount < body.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно средств для вывода",
        )

    balance.available_amount -= body.amount

    payout = PayoutRequest(
        author_id=current_user.id,
        amount=body.amount,
        status=PayoutStatus.pending,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(payout)
    await db.commit()
    await db.refresh(payout)
    return payout


@router.get("/payouts", response_model=list[PayoutRequestOut])
async def list_payouts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PayoutRequest)
        .where(PayoutRequest.author_id == current_user.id)
        .order_by(PayoutRequest.requested_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


# ---------- Purchases ----------

@router.get("/promo-codes", response_model=list[PromoCodeOut])
async def list_author_promo_codes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    """Все промокоды, выданные автором."""
    result = await db.execute(
        select(PromoCode)
        .where(PromoCode.author_id == current_user.id)
        .order_by(PromoCode.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/purchases/{book_id}", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
async def purchase_book(
    book_id: uuid.UUID,
    body: PurchaseWithPromo,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Купить книгу. Принимает данные карты — оплата всегда проходит (mock)."""
    book_result = await db.execute(
        select(Book).where(
            Book.id == book_id,
            Book.status == BookStatus.published,
            Book.is_for_sale == True,
        )
    )
    book = book_result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга не найдена или не продаётся")

    existing = await db.execute(
        select(Purchase).where(Purchase.user_id == current_user.id, Purchase.book_id == book_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Книга уже куплена")

    promo: PromoCode | None = None
    if body.promo_code:
        promo_result = await db.execute(
            select(PromoCode).where(PromoCode.code == body.promo_code.strip().upper())
        )
        promo = promo_result.scalar_one_or_none()
        if not promo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")
        validate_promo_for_purchase(promo, current_user, book)

    now = datetime.now(timezone.utc)
    price_paid = book.sale_price
    if promo:
        price_paid = apply_discount(book.sale_price, promo.discount_percent)

    author_cut = (price_paid * Decimal("0.7")).quantize(Decimal("0.01"))
    mock_payment_id = f"mock_{body.card_number[-4:]}"

    purchase = Purchase(
        user_id=current_user.id,
        book_id=book_id,
        price_paid=price_paid,
        author_earning=author_cut,
        status=PaymentStatus.succeeded,
        external_payment_id=mock_payment_id,
        purchased_at=now,
    )
    db.add(purchase)
    await db.flush()

    if promo:
        promo.used_at = now
        promo.purchase_id = purchase.id

    await _credit_author(db, book.author_id, author_cut, EarningSource.purchase, purchase.id, now)

    await db.commit()
    await db.refresh(purchase)
    return purchase


@router.get("/purchases", response_model=list[PurchaseOut])
async def list_my_purchases(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Purchase).where(Purchase.user_id == current_user.id)
    )
    return result.scalars().all()


# ---------- Subscription reads (открытие книги по подписке) ----------

@router.post("/reads/{book_id}", response_model=dict)
async def open_book_via_subscription(
    book_id: uuid.UUID,
    current_user: User = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
):
    book_result = await db.execute(
        select(Book).where(
            Book.id == book_id,
            Book.status == BookStatus.published,
            Book.is_in_subscription == True,
        )
    )
    book = book_result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Книга недоступна по подписке")

    existing = await db.execute(
        select(SubscriptionRead).where(
            SubscriptionRead.user_id == current_user.id,
            SubscriptionRead.book_id == book_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"status": "already_opened"}

    payout_amount = book.subscription_payout_amount or Decimal("0")
    now = datetime.now(timezone.utc)

    sub_read = SubscriptionRead(
        user_id=current_user.id,
        book_id=book_id,
        payout_amount=payout_amount,
        opened_at=now,
    )
    db.add(sub_read)
    await db.flush()

    await _credit_author(db, book.author_id, payout_amount, EarningSource.subscription_read, sub_read.id, now)

    await db.commit()
    return {"status": "opened", "payout_amount": str(payout_amount)}


# ---------- Helpers ----------

async def _credit_author(
    db: AsyncSession,
    author_id: uuid.UUID,
    amount: Decimal,
    source_type: EarningSource,
    source_id: uuid.UUID,
    now: datetime,
) -> None:
    """Начислить сумму на баланс автора и записать транзакцию."""
    balance_result = await db.execute(
        select(AuthorBalance).where(AuthorBalance.author_id == author_id)
    )
    balance = balance_result.scalar_one_or_none()

    if balance:
        balance.available_amount += amount
        balance.total_earned += amount
        balance.updated_at = now
    else:
        db.add(AuthorBalance(
            author_id=author_id,
            available_amount=amount,
            pending_amount=Decimal("0"),
            total_earned=amount,
            updated_at=now,
        ))

    db.add(EarningTransaction(
        author_id=author_id,
        source_type=source_type,
        source_id=source_id,
        amount=amount,
        created_at=now,
    ))
