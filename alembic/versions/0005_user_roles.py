"""user roles: replace active_mode with role (reader/author)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_mode RENAME VALUE 'writer' TO 'author'")
    op.execute("ALTER TYPE user_mode RENAME TO user_role")
    op.alter_column("users", "active_mode", new_column_name="role")


def downgrade() -> None:
    op.alter_column("users", "role", new_column_name="active_mode")
    op.execute("ALTER TYPE user_role RENAME TO user_mode")
    op.execute("ALTER TYPE user_mode RENAME VALUE 'author' TO 'writer'")
