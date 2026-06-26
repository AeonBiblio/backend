from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.subscription import (
    PaymentStatus,
    SubscriptionPayment,
    SubscriptionPlan,
    SubscriptionStatus,
    UserSubscription,
)
from app.models.user import User
from app.schemas.payment import MockCardIn
from app.schemas.subscription import (
    SubscribeRequest,
    SubscriptionPaymentOut,
    SubscriptionPlanOut,
    UserSubscriptionOut,
)

router = APIRouter()


@router.get("/plans", response_model=list[SubscriptionPlanOut])
async def list_plans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.is_active == True))
    return result.scalars().all()


class SubscribeWithCard(SubscribeRequest):
    card: MockCardIn


@router.post("/subscribe", response_model=UserSubscriptionOut, status_code=status.HTTP_201_CREATED)
async def subscribe(
    body: SubscribeWithCard,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Оформить подписку. Принимает данные карты — оплата всегда проходит (mock)."""
    plan_result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == body.plan_id, SubscriptionPlan.is_active == True)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тарифный план не найден")

    active_result = await db.execute(
        select(UserSubscription).where(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == SubscriptionStatus.active,
        )
    )
    if active_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="У вас уже есть активная подписка")

    now = datetime.now(timezone.utc)
    subscription = UserSubscription(
        user_id=current_user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.active,
        started_at=now,
        expires_at=now + timedelta(days=plan.duration_days),
        auto_renew=body.auto_renew,
    )
    db.add(subscription)
    await db.flush()

    mock_payment_id = f"mock_{body.card.card_number[-4:]}"
    payment = SubscriptionPayment(
        user_subscription_id=subscription.id,
        amount=plan.price,
        status=PaymentStatus.succeeded,
        external_payment_id=mock_payment_id,
        paid_at=now,
        created_at=now,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.get("/me", response_model=UserSubscriptionOut | None)
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSubscription)
        .where(UserSubscription.user_id == current_user.id)
        .order_by(UserSubscription.started_at.desc())
    )
    return result.scalars().first()


@router.post("/me/cancel", response_model=UserSubscriptionOut)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSubscription).where(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == SubscriptionStatus.active,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Активная подписка не найдена")

    sub.status = SubscriptionStatus.cancelled
    sub.cancelled_at = datetime.now(timezone.utc)
    sub.auto_renew = False
    await db.commit()
    await db.refresh(sub)
    return sub


@router.get("/me/payments", response_model=list[SubscriptionPaymentOut])
async def list_subscription_payments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SubscriptionPayment)
        .join(UserSubscription, UserSubscription.id == SubscriptionPayment.user_subscription_id)
        .where(UserSubscription.user_id == current_user.id)
        .order_by(SubscriptionPayment.created_at.desc())
    )
    return result.scalars().all()
