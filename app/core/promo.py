import secrets
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status

from app.models.book import Book, BookStatus
from app.models.promo import PromoCode
from app.models.user import User


def generate_code() -> str:
    return secrets.token_urlsafe(8).upper().replace("-", "X")[:12]


def apply_discount(price: Decimal, discount_percent: Decimal) -> Decimal:
    factor = Decimal("1") - (discount_percent / Decimal("100"))
    return (price * factor).quantize(Decimal("0.01"))


def validate_promo_for_purchase(promo: PromoCode, user: User, book: Book) -> None:
    if promo.recipient_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Промокод выдан другому пользователю",
        )
    if book.author_id != promo.author_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Промокод действует только на книги этого автора",
        )
    if book.status != BookStatus.published or not book.is_for_sale:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Книга недоступна для покупки",
        )
    if promo.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Промокод уже использован",
        )
    if promo.expires_at is not None and promo.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Срок действия промокода истёк",
        )
