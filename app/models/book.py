import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class BookStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    published = "published"
    rejected = "rejected"


class Book(Base, TimestampMixin):
    __tablename__ = "books"
    __table_args__ = (
        Index("ix_books_author_id", "author_id"),
        Index("ix_books_status", "status"),
        Index("ix_books_is_in_subscription", "is_in_subscription"),
        Index("ix_books_is_for_sale", "is_for_sale"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_key: Mapped[str | None] = mapped_column(String, nullable=True)
    file_key: Mapped[str | None] = mapped_column(String, nullable=True)
    file_format: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[BookStatus] = mapped_column(
        Enum(BookStatus, name="book_status"),
        nullable=False,
        default=BookStatus.draft,
    )
    is_in_subscription: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subscription_payout_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_for_sale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped["app.models.user.User"] = relationship("User", foreign_keys=[author_id])
    genre_tags: Mapped[list["BookGenreTag"]] = relationship(back_populates="book", cascade="all, delete-orphan")
    user_tags: Mapped[list["BookUserTag"]] = relationship(back_populates="book", cascade="all, delete-orphan")


class GenreTag(Base):
    __tablename__ = "genre_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    book_links: Mapped[list["BookGenreTag"]] = relationship(back_populates="genre_tag")


class BookGenreTag(Base):
    __tablename__ = "book_genre_tags"
    __table_args__ = (
        UniqueConstraint("book_id", "genre_tag_id", name="uq_book_genre_tag"),
    )

    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id"), primary_key=True)
    genre_tag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("genre_tags.id"), primary_key=True)

    book: Mapped["Book"] = relationship(back_populates="genre_tags")
    genre_tag: Mapped["GenreTag"] = relationship(back_populates="book_links")


class UserTag(Base):
    __tablename__ = "user_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    book_links: Mapped[list["BookUserTag"]] = relationship(back_populates="user_tag")


class BookUserTag(Base):
    __tablename__ = "book_user_tags"
    __table_args__ = (
        UniqueConstraint("book_id", "user_tag_id", "user_id", name="uq_book_user_tag_vote"),
        Index("ix_book_user_tags_book_id", "book_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False)
    user_tag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_tags.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    book: Mapped["Book"] = relationship(back_populates="user_tags")
    user_tag: Mapped["UserTag"] = relationship(back_populates="book_links")
