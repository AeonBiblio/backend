import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.library import ReadingStatus


class UserBookStatusSet(BaseModel):
    status: ReadingStatus
    progress_percent: int | None = Field(default=None, ge=0, le=100)


class UserBookStatusOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    status: ReadingStatus
    progress_percent: int | None
    updated_at: datetime


class RecentBookOut(BaseModel):
    book_id: uuid.UUID
    title: str
    cover_key: str | None
    status: ReadingStatus
    progress_percent: int | None
    updated_at: datetime


class ReadlistCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    is_public: bool = True


class ReadlistUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    is_public: bool | None = None


class ReadlistOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    is_public: bool
    created_at: datetime
    updated_at: datetime


class ReadlistItemAdd(BaseModel):
    book_id: uuid.UUID


class ReadlistItemOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    readlist_id: uuid.UUID
    book_id: uuid.UUID
    added_at: datetime
