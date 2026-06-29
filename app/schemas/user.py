import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.payments import normalize_card_number

from app.models.user import UserRole


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    role: UserRole = UserRole.reader


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    username: str
    display_tag: str | None
    avatar_key: str | None
    role: UserRole
    is_email_verified: bool
    created_at: datetime


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=50)
    display_tag: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class PaymentProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    payout_requisites_encrypted: str | None
    payment_method_token: str | None
    card_last_digits: str | None = None
    card_last4: str | None = None
    updated_at: datetime


class PaymentProfileUpdate(BaseModel):
    payout_requisites_encrypted: str | None = None
    payment_method_token: str | None = None
    card_number: str | None = None
    cardholder_name: str | None = None
    expiry_month: int | None = Field(default=None, ge=1, le=12)
    expiry_year: int | None = Field(default=None, ge=2026)
    cvv: str | None = Field(default=None, min_length=3, max_length=4)

    @field_validator("card_number")
    @classmethod
    def validate_card_number(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return normalize_card_number(value)


class PublicUserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    display_tag: str | None
    avatar_key: str | None
    role: UserRole
