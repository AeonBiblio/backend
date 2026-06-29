"""epub reader chapters

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


reader_processing_status = postgresql.ENUM(
    "none",
    "processing",
    "ready",
    "failed",
    name="reader_processing_status",
)


def upgrade() -> None:
    reader_processing_status.create(op.get_bind())
    op.add_column(
        "books",
        sa.Column(
            "reader_processing_status",
            reader_processing_status,
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column("books", sa.Column("reader_processing_error", sa.Text(), nullable=True))
    op.add_column(
        "books",
        sa.Column("reader_manifest_version", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "epub_chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("source_href", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False, server_default="html"),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("asset_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("book_id", "chapter_index", name="uq_epub_chapter_index"),
    )
    op.create_index("ix_epub_chapters_book_id", "epub_chapters", ["book_id"])

    op.alter_column("books", "reader_processing_status", server_default=None)
    op.alter_column("books", "reader_manifest_version", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_epub_chapters_book_id", table_name="epub_chapters")
    op.drop_table("epub_chapters")
    op.drop_column("books", "reader_manifest_version")
    op.drop_column("books", "reader_processing_error")
    op.drop_column("books", "reader_processing_status")
    reader_processing_status.drop(op.get_bind())
