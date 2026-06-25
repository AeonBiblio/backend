import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

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
    updated_at: datetime


class PaymentProfileUpdate(BaseModel):
    payout_requisites_encrypted: str | None = None
    payment_method_token: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PublicUserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    display_tag: str | None
    avatar_key: str | None
    role: UserRole
