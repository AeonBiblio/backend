import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class ReadingStatus(str, enum.Enum):
    reading = "reading"
    finished = "finished"
    wishlist = "wishlist"


class UserBookStatus(Base):
    __tablename__ = "user_book_status"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_user_book_status"),
        Index("ix_user_book_status_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False)
    status: Mapped[ReadingStatus] = mapped_column(Enum(ReadingStatus), nullable=False)
    progress_percent: Mapped[int | None] = mapped_column(SmallInteger, default=0, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["app.models.user.User"] = relationship("User", foreign_keys=[user_id])
    book: Mapped["app.models.book.Book"] = relationship("Book", foreign_keys=[book_id])


class Readlist(Base, TimestampMixin):
    __tablename__ = "readlists"
    __table_args__ = (
        Index("ix_readlists_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped["app.models.user.User"] = relationship("User", foreign_keys=[user_id])
    items: Mapped[list["ReadlistItem"]] = relationship(back_populates="readlist", cascade="all, delete-orphan")


class ReadlistItem(Base):
    __tablename__ = "readlist_items"
    __table_args__ = (
        UniqueConstraint("readlist_id", "book_id", name="uq_readlist_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    readlist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("readlists.id"), nullable=False)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    readlist: Mapped["Readlist"] = relationship(back_populates="items")
    book: Mapped["app.models.book.Book"] = relationship("Book", foreign_keys=[book_id])
