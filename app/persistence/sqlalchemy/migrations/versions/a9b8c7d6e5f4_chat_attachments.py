"""chat message attachments (image / voice)

Revision ID: a9b8c7d6e5f4
Revises: b3c4d5e6f7a8
Create Date: 2026-10-27 12:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("message_type", sa.String(length=16), server_default="text", nullable=False),
    )
    op.add_column("chat_messages", sa.Column("file_path", sa.Text(), nullable=True))
    op.add_column("chat_messages", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "chat_messages_message_type_check",
        "chat_messages",
        "message_type in ('text', 'image', 'voice')",
    )
    op.create_check_constraint(
        "chat_messages_duration_ms_check",
        "chat_messages",
        "duration_ms is null or duration_ms >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("chat_messages_duration_ms_check", "chat_messages", type_="check")
    op.drop_constraint("chat_messages_message_type_check", "chat_messages", type_="check")
    op.drop_column("chat_messages", "duration_ms")
    op.drop_column("chat_messages", "file_path")
    op.drop_column("chat_messages", "message_type")
