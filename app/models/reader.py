import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ReaderAnnotationType(str, enum.Enum):
    bookmark = "bookmark"
    highlight = "highlight"
    note = "note"


class ReaderProgress(Base):
    __tablename__ = "reader_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_reader_progress_user_book"),
        Index("ix_reader_progress_user_id", "user_id"),
        Index("ix_reader_progress_book_id", "book_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, nullable=False)
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    cfi: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_hash: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["app.models.user.User"] = relationship("User", foreign_keys=[user_id])
    book: Mapped["app.models.book.Book"] = relationship("Book", foreign_keys=[book_id])


class ReaderSettings(Base):
    __tablename__ = "reader_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_reader_settings_user_book"),
        Index("ix_reader_settings_user_id", "user_id"),
        Index("ix_reader_settings_book_id", "book_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False)
    theme: Mapped[str] = mapped_column(String, nullable=False)
    font_family: Mapped[str] = mapped_column(String, nullable=False)
    font_size: Mapped[int] = mapped_column(Integer, nullable=False)
    line_height: Mapped[float] = mapped_column(Float, nullable=False)
    page_mode: Mapped[str] = mapped_column(String, nullable=False)
    text_align: Mapped[str] = mapped_column(String, nullable=False)
    margin: Mapped[int] = mapped_column(Integer, nullable=False)
    column_gap: Mapped[int] = mapped_column(Integer, nullable=False)
    columns_per_page: Mapped[int] = mapped_column(Integer, nullable=False)
    enable_keyboard_arrows: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enable_keyboard_letters: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enable_reader_arrows: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enable_wheel_navigation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    limit_wheel_to_one_page: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["app.models.user.User"] = relationship("User", foreign_keys=[user_id])
    book: Mapped["app.models.book.Book"] = relationship("Book", foreign_keys=[book_id])


class ReaderAnnotation(Base):
    __tablename__ = "reader_annotations"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", "client_id", name="uq_reader_annotation_client_id"),
        Index("ix_reader_annotations_user_book", "user_id", "book_id"),
        Index("ix_reader_annotations_deleted_at", "deleted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False)
    client_id: Mapped[str] = mapped_column(String, nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, nullable=False)
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[ReaderAnnotationType] = mapped_column(
        Enum(ReaderAnnotationType, name="reader_annotation_type"),
        nullable=False,
    )
    page_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    settings_hash: Mapped[str] = mapped_column(String, nullable=False)
    range: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["app.models.user.User"] = relationship("User", foreign_keys=[user_id])
    book: Mapped["app.models.book.Book"] = relationship("Book", foreign_keys=[book_id])
