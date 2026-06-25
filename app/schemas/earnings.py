import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.earnings import EarningSource, PayoutStatus
from app.models.subscription import PaymentStatus


class AuthorBalanceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    author_id: uuid.UUID
    available_amount: Decimal
    pending_amount: Decimal
    total_earned: Decimal
    updated_at: datetime


class EarningTransactionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    author_id: uuid.UUID
    source_type: EarningSource
    source_id: uuid.UUID
    amount: Decimal
    created_at: datetime


class PayoutRequestCreate(BaseModel):
    amount: Decimal = Field(gt=0)


class PayoutRequestOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    author_id: uuid.UUID
    amount: Decimal
    status: PayoutStatus
    requested_at: datetime
    processed_at: datetime | None
    failure_reason: str | None


class PurchaseOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    price_paid: Decimal
    author_earning: Decimal
    status: PaymentStatus
    external_payment_id: str | None
    purchased_at: datetime | None


class AuthorStatsOut(BaseModel):
    total_reads: int
    total_sales: int
    total_earned: Decimal
    available_amount: Decimal
    pending_amount: Decimal
    period: dict | None = None


class BookStatsItem(BaseModel):
    book_id: uuid.UUID
    title: str
    cover_key: str | None
    reads: int
    sales: int
    income: Decimal
