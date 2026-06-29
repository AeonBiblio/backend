from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.payments import make_mock_payment_token, payment_profile_last4
from app.core.security import hash_password, verify_password
from app.core.storage import presigned_put_url
from app.models.promo import PromoCode
from app.models.user import PaymentProfile, User
from app.schemas.promo import PromoCodeOut
from app.schemas.user import (
    PasswordChange,
    PaymentProfileOut,
    PaymentProfileUpdate,
    PublicUserOut,
    UserOut,
    UserUpdate,
)

router = APIRouter()


def _payment_profile_out(profile: PaymentProfile) -> PaymentProfileOut:
    last4 = payment_profile_last4(profile)
    return PaymentProfileOut(
        id=profile.id,
        user_id=profile.user_id,
        payout_requisites_encrypted=profile.payout_requisites_encrypted,
        payment_method_token=profile.payment_method_token,
        card_last_digits=last4,
        card_last4=last4,
        updated_at=profile.updated_at,
    )


@router.get("/by-username/{username}", response_model=PublicUserOut)
async def get_public_profile(username: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.username is not None:
        from sqlalchemy import select as sa_select
        result = await db.execute(
            sa_select(User).where(User.username == body.username, User.id != current_user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username уже занят")
        current_user.username = body.username

    if body.display_tag is not None:
        current_user.display_tag = body.display_tag

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный текущий пароль")
    current_user.password_hash = hash_password(body.new_password)
    await db.commit()


@router.post("/me/avatar", response_model=dict)
async def get_avatar_upload_url(current_user: User = Depends(get_current_user)):
    object_key = f"avatars/{current_user.id}.jpg"
    url = presigned_put_url(object_key)
    return {"upload_url": url, "object_key": object_key}


@router.patch("/me/avatar-key", response_model=UserOut)
async def confirm_avatar(
    object_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.avatar_key = object_key
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/me/promo-codes", response_model=list[PromoCodeOut])
async def list_my_promo_codes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Активные промокоды текущего пользователя (не использованы, не истекли)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PromoCode).where(
            PromoCode.recipient_user_id == current_user.id,
            PromoCode.used_at.is_(None),
            or_(PromoCode.expires_at.is_(None), PromoCode.expires_at > now),
        )
    )
    return result.scalars().all()


@router.get("/me/payment-profile", response_model=PaymentProfileOut)
async def get_payment_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PaymentProfile).where(PaymentProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платёжный профиль не найден")
    return _payment_profile_out(profile)


@router.patch("/me/payment-profile", response_model=PaymentProfileOut)
async def upsert_payment_profile(
    body: PaymentProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    result = await db.execute(select(PaymentProfile).where(PaymentProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()

    if not profile:
        profile = PaymentProfile(user_id=current_user.id)
        db.add(profile)

    if body.payout_requisites_encrypted is not None:
        profile.payout_requisites_encrypted = body.payout_requisites_encrypted
    if body.card_number is not None:
        profile.payment_method_token = make_mock_payment_token(body.card_number)
    if body.payment_method_token is not None:
        profile.payment_method_token = body.payment_method_token

    await db.commit()
    await db.refresh(profile)
    return _payment_profile_out(profile)
