"""Add is_seen and seen_at to chat_messages

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-15 12:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'chat_messages',
        sa.Column('is_seen', sa.Boolean(), server_default=sa.text('false'), nullable=False)
    )
    op.add_column(
        'chat_messages',
        sa.Column('seen_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('chat_messages', 'seen_at')
    op.drop_column('chat_messages', 'is_seen')
