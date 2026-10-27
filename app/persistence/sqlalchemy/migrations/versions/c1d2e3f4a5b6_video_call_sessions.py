"""video call sessions (Agora, 15 min)

Revision ID: c1d2e3f4a5b6
Revises: a9b8c7d6e5f4
Create Date: 2026-10-27 14:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "video_call_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ringing", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctor_profiles.id"]),
        sa.ForeignKeyConstraint(["ended_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status in ('ringing', 'active', 'ended', 'expired')",
            name="video_call_sessions_status_check",
        ),
    )
    op.create_index(
        "ix_video_call_sessions_doctor_status",
        "video_call_sessions",
        ["doctor_id", "status"],
    )
    op.create_index(
        "ix_video_call_sessions_conversation",
        "video_call_sessions",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_video_call_sessions_conversation", table_name="video_call_sessions")
    op.drop_index("ix_video_call_sessions_doctor_status", table_name="video_call_sessions")
    op.drop_constraint("video_call_sessions_status_check", "video_call_sessions", type_="check")
    op.drop_table("video_call_sessions")
