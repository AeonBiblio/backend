"""figma_features: sentiment, book_ratings

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    review_sentiment = postgresql.ENUM("positive", "negative", "neutral", name="review_sentiment")
    review_sentiment.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "reviews",
        sa.Column(
            "sentiment",
            postgresql.ENUM("positive", "negative", "neutral", name="review_sentiment", create_type=False),
            nullable=False,
            server_default="neutral",
        ),
    )

    op.create_table(
        "book_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("book_id", "user_id", name="uq_book_rating"),
    )
    op.create_index("ix_book_ratings_book_id", "book_ratings", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_book_ratings_book_id", table_name="book_ratings")
    op.drop_table("book_ratings")
    op.drop_column("reviews", "sentiment")
    postgresql.ENUM(name="review_sentiment").drop(op.get_bind(), checkfirst=True)
