"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("display_tag", sa.String(), nullable=True),
        sa.Column("avatar_key", sa.String(), nullable=True),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # --- payment_profiles ---
    op.create_table(
        "payment_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("payout_requisites_encrypted", sa.Text(), nullable=True),
        sa.Column("payment_method_token", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- books ---
    book_status = postgresql.ENUM("draft", "pending", "published", "rejected", name="book_status")
    book_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "books",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_key", sa.String(), nullable=True),
        sa.Column("file_key", sa.String(), nullable=True),
        sa.Column("file_format", sa.String(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("status", postgresql.ENUM("draft", "pending", "published", "rejected", name="book_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("is_in_subscription", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("subscription_payout_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_for_sale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sale_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_books_author_id", "books", ["author_id"])
    op.create_index("ix_books_status", "books", ["status"])
    op.create_index("ix_books_is_in_subscription", "books", ["is_in_subscription"])
    op.create_index("ix_books_is_for_sale", "books", ["is_for_sale"])

    # --- genre_tags ---
    op.create_table(
        "genre_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- book_genre_tags ---
    op.create_table(
        "book_genre_tags",
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), primary_key=True),
        sa.Column("genre_tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("genre_tags.id"), primary_key=True),
    )

    # --- user_tags ---
    op.create_table(
        "user_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- book_user_tags ---
    op.create_table(
        "book_user_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("user_tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_tags.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("book_id", "user_tag_id", "user_id", name="uq_book_user_tag_vote"),
    )
    op.create_index("ix_book_user_tags_book_id", "book_user_tags", ["book_id"])

    # --- reviews ---
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("book_id", "user_id", name="uq_review_book_user"),
    )
    op.create_index("ix_reviews_book_id", "reviews", ["book_id"])

    # --- user_book_status ---
    reading_status = postgresql.ENUM("reading", "finished", "wishlist", name="reading_status")
    reading_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "user_book_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("status", postgresql.ENUM("reading", "finished", "wishlist", name="reading_status", create_type=False), nullable=False),
        sa.Column("progress_percent", sa.SmallInteger(), nullable=True, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "book_id", name="uq_user_book_status"),
    )
    op.create_index("ix_user_book_status_user_id", "user_book_status", ["user_id"])

    # --- readlists ---
    op.create_table(
        "readlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_readlists_user_id", "readlists", ["user_id"])

    # --- readlist_items ---
    op.create_table(
        "readlist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("readlist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("readlists.id"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("readlist_id", "book_id", name="uq_readlist_item"),
    )

    # --- subscription_plans ---
    op.create_table(
        "subscription_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- user_subscriptions ---
    sub_status = postgresql.ENUM("active", "cancelled", "expired", name="subscription_status")
    sub_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "user_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id"), nullable=False),
        sa.Column("status", postgresql.ENUM("active", "cancelled", "expired", name="subscription_status", create_type=False), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"])
    op.create_index("ix_user_subscriptions_status", "user_subscriptions", ["status"])

    # --- subscription_payments ---
    pay_status = postgresql.ENUM("pending", "succeeded", "failed", "refunded", name="payment_status")
    pay_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "subscription_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_subscriptions.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "succeeded", "failed", "refunded", name="payment_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("external_payment_id", sa.String(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- subscription_reads ---
    op.create_table(
        "subscription_reads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("payout_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "book_id", name="uq_subscription_read"),
    )
    op.create_index("ix_subscription_reads_book_id", "subscription_reads", ["book_id"])

    # --- purchases ---
    op.create_table(
        "purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("price_paid", sa.Numeric(10, 2), nullable=False),
        sa.Column("author_earning", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "succeeded", "failed", "refunded", name="payment_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("external_payment_id", sa.String(), nullable=True),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "book_id", name="uq_purchase"),
    )
    op.create_index("ix_purchases_book_id", "purchases", ["book_id"])

    # --- author_balances ---
    op.create_table(
        "author_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("available_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("pending_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_earned", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # --- earning_transactions ---
    earning_source = postgresql.ENUM("purchase", "subscription_read", name="earning_source")
    earning_source.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "earning_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_type", postgresql.ENUM("purchase", "subscription_read", name="earning_source", create_type=False), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_earning_transactions_author_id", "earning_transactions", ["author_id"])
    op.create_index("ix_earning_transactions_source", "earning_transactions", ["source_type", "source_id"])

    # --- payout_requests ---
    payout_status = postgresql.ENUM("pending", "processing", "completed", "failed", name="payout_status")
    payout_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "payout_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "processing", "completed", "failed", name="payout_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_payout_requests_author_id", "payout_requests", ["author_id"])
    op.create_index("ix_payout_requests_status", "payout_requests", ["status"])


def downgrade() -> None:
    op.drop_table("payout_requests")
    op.execute("DROP TYPE IF EXISTS payout_status")

    op.drop_table("earning_transactions")
    op.execute("DROP TYPE IF EXISTS earning_source")

    op.drop_table("author_balances")
    op.drop_table("purchases")
    op.drop_table("subscription_reads")
    op.drop_table("subscription_payments")
    op.execute("DROP TYPE IF EXISTS payment_status")

    op.drop_table("user_subscriptions")
    op.execute("DROP TYPE IF EXISTS subscription_status")

    op.drop_table("subscription_plans")
    op.drop_table("readlist_items")
    op.drop_table("readlists")
    op.drop_table("user_book_status")
    op.execute("DROP TYPE IF EXISTS reading_status")

    op.drop_table("reviews")
    op.drop_table("book_user_tags")
    op.drop_table("user_tags")
    op.drop_table("book_genre_tags")
    op.drop_table("genre_tags")
    op.drop_table("books")
    op.execute("DROP TYPE IF EXISTS book_status")

    op.drop_table("payment_profiles")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
