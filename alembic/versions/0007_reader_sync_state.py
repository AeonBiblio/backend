"""reader sync state

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


reader_annotation_type = postgresql.ENUM(
    "bookmark",
    "highlight",
    "note",
    name="reader_annotation_type",
)


def upgrade() -> None:
    reader_annotation_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "reader_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=False),
        sa.Column("chapter_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("percentage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cfi", sa.Text(), nullable=True),
        sa.Column("settings_hash", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "book_id", name="uq_reader_progress_user_book"),
    )
    op.create_index("ix_reader_progress_user_id", "reader_progress", ["user_id"])
    op.create_index("ix_reader_progress_book_id", "reader_progress", ["book_id"])

    op.create_table(
        "reader_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("theme", sa.String(), nullable=False),
        sa.Column("font_family", sa.String(), nullable=False),
        sa.Column("font_size", sa.Integer(), nullable=False),
        sa.Column("line_height", sa.Float(), nullable=False),
        sa.Column("page_mode", sa.String(), nullable=False),
        sa.Column("text_align", sa.String(), nullable=False),
        sa.Column("margin", sa.Integer(), nullable=False),
        sa.Column("column_gap", sa.Integer(), nullable=False),
        sa.Column("columns_per_page", sa.Integer(), nullable=False),
        sa.Column("enable_keyboard_arrows", sa.Boolean(), nullable=False),
        sa.Column("enable_keyboard_letters", sa.Boolean(), nullable=False),
        sa.Column("enable_reader_arrows", sa.Boolean(), nullable=False),
        sa.Column("enable_wheel_navigation", sa.Boolean(), nullable=False),
        sa.Column("limit_wheel_to_one_page", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "book_id", name="uq_reader_settings_user_book"),
    )
    op.create_index("ix_reader_settings_user_id", "reader_settings", ["user_id"])
    op.create_index("ix_reader_settings_book_id", "reader_settings", ["book_id"])

    op.create_table(
        "reader_annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=False),
        sa.Column("type", postgresql.ENUM("bookmark", "highlight", "note", name="reader_annotation_type", create_type=False), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("percentage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("settings_hash", sa.String(), nullable=False),
        sa.Column("range", sa.JSON(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "book_id", "client_id", name="uq_reader_annotation_client_id"),
    )
    op.create_index("ix_reader_annotations_user_book", "reader_annotations", ["user_id", "book_id"])
    op.create_index("ix_reader_annotations_deleted_at", "reader_annotations", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_reader_annotations_deleted_at", table_name="reader_annotations")
    op.drop_index("ix_reader_annotations_user_book", table_name="reader_annotations")
    op.drop_table("reader_annotations")
    op.drop_index("ix_reader_settings_book_id", table_name="reader_settings")
    op.drop_index("ix_reader_settings_user_id", table_name="reader_settings")
    op.drop_table("reader_settings")
    op.drop_index("ix_reader_progress_book_id", table_name="reader_progress")
    op.drop_index("ix_reader_progress_user_id", table_name="reader_progress")
    op.drop_table("reader_progress")
    reader_annotation_type.drop(op.get_bind(), checkfirst=True)
