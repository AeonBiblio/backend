import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PromoCodeIssue(BaseModel):
    discount_percent: int = Field(ge=1, le=100)
    expires_in_days: int = Field(default=30, ge=1, le=365)


class PromoCodeOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    code: str
    review_id: uuid.UUID
    author_id: uuid.UUID
    recipient_user_id: uuid.UUID
    discount_percent: Decimal
    expires_at: datetime | None
    used_at: datetime | None
    purchase_id: uuid.UUID | None
    created_at: datetime
