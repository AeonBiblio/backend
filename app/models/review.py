import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, SmallInteger, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class ReviewSentiment(str, enum.Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("book_id", "user_id", name="uq_review_book_user"),
        Index("ix_reviews_book_id", "book_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sentiment: Mapped[ReviewSentiment] = mapped_column(
        Enum(ReviewSentiment, name="review_sentiment"),
        nullable=False,
        default=ReviewSentiment.neutral,
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    book: Mapped["app.models.book.Book"] = relationship("Book", foreign_keys=[book_id])
    user: Mapped["app.models.user.User"] = relationship("User", foreign_keys=[user_id])
