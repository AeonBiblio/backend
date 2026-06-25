"""review_votes and user active_mode

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_mode = postgresql.ENUM("reader", "writer", name="user_mode")
    user_mode.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "active_mode",
            postgresql.ENUM("reader", "writer", name="user_mode", create_type=False),
            nullable=False,
            server_default="reader",
        ),
    )

    review_vote_type = postgresql.ENUM("like", "dislike", name="review_vote_type")
    review_vote_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "review_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "vote",
            postgresql.ENUM("like", "dislike", name="review_vote_type", create_type=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("review_id", "user_id", name="uq_review_vote"),
    )


def downgrade() -> None:
    op.drop_table("review_votes")
    op.drop_column("users", "active_mode")
    postgresql.ENUM(name="review_vote_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="user_mode").drop(op.get_bind(), checkfirst=True)
