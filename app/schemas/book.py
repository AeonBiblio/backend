import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.book import BookStatus, ReaderProcessingStatus


class GenreTagOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str


class UserTagOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    is_in_subscription: bool = False
    subscription_payout_amount: Decimal | None = None
    is_for_sale: bool = False
    sale_price: Decimal | None = None


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    is_in_subscription: bool | None = None
    subscription_payout_amount: Decimal | None = None
    is_for_sale: bool | None = None
    sale_price: Decimal | None = None


class BookOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    author_id: uuid.UUID
    title: str
    description: str | None
    cover_key: str | None
    file_key: str | None
    file_format: str | None
    file_size_bytes: int | None
    status: BookStatus
    is_in_subscription: bool
    subscription_payout_amount: Decimal | None
    is_for_sale: bool
    sale_price: Decimal | None
    rejection_reason: str | None
    published_at: datetime | None
    reader_processing_status: ReaderProcessingStatus
    reader_processing_error: str | None
    reader_manifest_version: int
    created_at: datetime
    updated_at: datetime
    average_rating: Decimal | None = None
    ratings_count: int = 0
    reviews_count: int = 0
    my_rating: int | None = None


class BookListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    author_id: uuid.UUID
    title: str
    cover_key: str | None
    status: BookStatus
    is_in_subscription: bool
    is_for_sale: bool
    sale_price: Decimal | None
    published_at: datetime | None
    average_rating: Decimal | None = None
    ratings_count: int = 0
    reviews_count: int = 0


class UploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str


class GenreTagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class BookGenreTagsUpdate(BaseModel):
    genre_tag_ids: list[uuid.UUID]


class UserTagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class BookAccessOut(BaseModel):
    can_read: bool
    reason: str
    file_size_bytes: int | None = None
    file_format: str | None = None
    reader_processing_status: ReaderProcessingStatus | None = None
    reader_manifest_version: int | None = None


class BookRecommendationsOut(BaseModel):
    new: list[BookListItem]
    popular: list[BookListItem]


class ReaderManifestChapterOut(BaseModel):
    id: uuid.UUID
    index: int
    title: str | None
    size_bytes: int
    href: str
    asset_ids: list[str]


class ReaderManifestAssetOut(BaseModel):
    id: str
    href: str


class ReaderManifestOut(BaseModel):
    book_id: uuid.UUID
    format: str
    version: int
    title: str
    processing_status: ReaderProcessingStatus
    chapters: list[ReaderManifestChapterOut]
    assets: list[ReaderManifestAssetOut]


class ReaderChapterOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    index: int
    title: str | None
    content_type: str
    html: str
    asset_ids: list[str]
