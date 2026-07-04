from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.reader import ReaderAnnotationType


class ReaderProgressSet(BaseModel):
    chapter_id: str = Field(min_length=1, max_length=500)
    chapter_index: int = Field(ge=0)
    chapter_offset: int = Field(ge=0)
    page_index: int = Field(ge=0)
    page_count: int = Field(ge=0)
    percentage: float = Field(ge=0, le=100)
    cfi: str | None = None
    settings_hash: str = Field(min_length=1, max_length=500)
    updated_at: datetime


class ReaderProgressOut(ReaderProgressSet):
    model_config = {"from_attributes": True}


class ReaderSettingsSet(BaseModel):
    theme: Literal["light", "sepia", "dark"]
    font_family: str = Field(min_length=1, max_length=500)
    font_size: int = Field(ge=8, le=96)
    line_height: float = Field(ge=1, le=3)
    page_mode: Literal["paginated", "scroll"]
    text_align: Literal["left", "justify"]
    margin: int = Field(ge=0, le=200)
    column_gap: int = Field(ge=0, le=200)
    columns_per_page: int = Field(ge=1, le=4)
    enable_keyboard_arrows: bool
    enable_keyboard_letters: bool
    enable_reader_arrows: bool
    enable_wheel_navigation: bool
    limit_wheel_to_one_page: bool
    updated_at: datetime


class ReaderSettingsOut(ReaderSettingsSet):
    model_config = {"from_attributes": True}


class ReaderAnnotationSet(BaseModel):
    id: str = Field(min_length=1, max_length=500)
    chapter_id: str = Field(min_length=1, max_length=500)
    chapter_index: int = Field(ge=0)
    type: ReaderAnnotationType
    page_index: int = Field(ge=0)
    page_number: int | None = Field(default=None, ge=0)
    page_count: int = Field(ge=0)
    percentage: float = Field(ge=0, le=100)
    settings_hash: str = Field(min_length=1, max_length=500)
    range: dict[str, Any] | list[Any] | None = None
    quote: str | None = None
    color: str | None = Field(default=None, max_length=100)
    text: str | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class ReaderAnnotationOut(ReaderAnnotationSet):
    pass
