import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.subscription import PaymentStatus, SubscriptionStatus


class SubscriptionPlanOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    price: Decimal
    duration_days: int
    is_active: bool


class SubscribeRequest(BaseModel):
    plan_id: uuid.UUID
    auto_renew: bool = True


class UserSubscriptionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    plan_id: uuid.UUID
    status: SubscriptionStatus
    started_at: datetime
    expires_at: datetime
    cancelled_at: datetime | None
    auto_renew: bool


class SubscriptionPaymentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_subscription_id: uuid.UUID
    amount: Decimal
    status: PaymentStatus
    external_payment_id: str | None
    paid_at: datetime | None
    created_at: datetime
