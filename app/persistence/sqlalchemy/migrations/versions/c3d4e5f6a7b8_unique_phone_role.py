"""Make user (phone, role) unique where not deleted

Revision ID: c3d4e5f6a7b8
Revises: 4483510091f6
Create Date: 2026-10-12 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = '4483510091f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_users_phone_unique', table_name='users', postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index(
        'ix_users_phone_role_unique',
        'users',
        ['phone', 'role'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL')
    )


def downgrade() -> None:
    op.drop_index('ix_users_phone_role_unique', table_name='users', postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index(
        'ix_users_phone_unique',
        'users',
        ['phone'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL')
    )
