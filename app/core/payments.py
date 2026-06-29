import re

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import PaymentProfile, User


def normalize_card_number(card_number: str) -> str:
    digits = re.sub(r"\D", "", card_number)
    if len(digits) < 13 or len(digits) > 19:
        raise ValueError("Номер карты должен содержать от 13 до 19 цифр")
    return digits


def make_mock_payment_token(card_number: str) -> str:
    return f"pm_mock_{normalize_card_number(card_number)[-4:]}"


def payment_profile_last4(profile: PaymentProfile) -> str | None:
    token = profile.payment_method_token
    if not token:
        return None

    match = re.search(r"(\d{4})$", token)
    return match.group(1) if match else None


async def require_saved_payment_profile(db: AsyncSession, user: User) -> PaymentProfile:
    result = await db.execute(select(PaymentProfile).where(PaymentProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile or not payment_profile_last4(profile):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сначала сохраните карту в платёжном профиле",
        )
    return profile
