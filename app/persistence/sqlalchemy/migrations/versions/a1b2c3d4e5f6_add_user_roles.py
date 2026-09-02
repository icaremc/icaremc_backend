"""add users.roles for multi-role accounts

Revision ID: a1b2c3d4e5f6
Revises: f60922ea36cf
Create Date: 2026-09-02
"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f60922ea36cf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS roles TEXT[] NOT NULL DEFAULT '{}'")
    op.execute(
        "UPDATE users SET roles = ARRAY[role] WHERE roles = '{}' OR roles IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS roles")
