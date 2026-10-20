"""Add child payment tracking columns and child_payments table

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-10-20 19:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add payment tracking columns to children
    op.add_column(
        'children',
        sa.Column('payment_status', sa.String(length=16), server_default=sa.text("'unpaid'"), nullable=False),
    )
    op.add_column(
        'children',
        sa.Column('amount_paid', sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        'children',
        sa.Column('currency', sa.String(length=8), server_default=sa.text("'ETB'"), nullable=False),
    )
    op.add_column(
        'children',
        sa.Column('payment_method', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'children',
        sa.Column('payment_tx_ref', sa.Text(), nullable=True),
    )
    op.add_column(
        'children',
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        'uq_children_payment_tx_ref',
        'children',
        ['payment_tx_ref'],
    )

    # 2. Create child_payments table
    op.create_table(
        'child_payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('child_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('children.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=8), server_default=sa.text("'ETB'"), nullable=False),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('tx_ref', sa.Text(), nullable=False),
        sa.Column('chapa_reference', sa.Text(), nullable=True),
        sa.Column('payment_method', sa.String(length=32), server_default=sa.text("'chapa'"), nullable=False),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_child_payments_user_id',
        'child_payments',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        'ix_child_payments_child_id',
        'child_payments',
        ['child_id'],
        unique=False,
    )
    op.create_index(
        'ix_child_payments_tx_ref',
        'child_payments',
        ['tx_ref'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_child_payments_tx_ref', table_name='child_payments')
    op.drop_index('ix_child_payments_child_id', table_name='child_payments')
    op.drop_index('ix_child_payments_user_id', table_name='child_payments')
    op.drop_table('child_payments')

    op.drop_constraint('uq_children_payment_tx_ref', 'children', type_='unique')
    op.drop_column('children', 'paid_at')
    op.drop_column('children', 'payment_tx_ref')
    op.drop_column('children', 'payment_method')
    op.drop_column('children', 'currency')
    op.drop_column('children', 'amount_paid')
    op.drop_column('children', 'payment_status')
