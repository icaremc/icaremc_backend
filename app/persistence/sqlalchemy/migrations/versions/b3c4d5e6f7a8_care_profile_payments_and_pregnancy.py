"""Rename child_payments to care_profile_payments, add pregnancy payment support

Revision ID: b3c4d5e6f7a8
Revises: f7a8b9c0d1e2
Create Date: 2026-10-21 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename child_payments table to care_profile_payments
    op.rename_table('child_payments', 'care_profile_payments')

    # Drop old index names if they exist and create new indexes
    op.drop_index('ix_child_payments_user_id', table_name='care_profile_payments')
    op.drop_index('ix_child_payments_child_id', table_name='care_profile_payments')
    op.drop_index('ix_child_payments_tx_ref', table_name='care_profile_payments')

    # 2. Modify columns in care_profile_payments
    op.alter_column(
        'care_profile_payments',
        'child_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        'care_profile_payments',
        sa.Column('pregnancy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pregnancies.id', ondelete='CASCADE'), nullable=True),
    )
    op.add_column(
        'care_profile_payments',
        sa.Column('payment_type', sa.String(length=32), server_default=sa.text("'child'"), nullable=False),
    )

    op.create_index(
        'ix_care_profile_payments_user_id',
        'care_profile_payments',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        'ix_care_profile_payments_child_id',
        'care_profile_payments',
        ['child_id'],
        unique=False,
    )
    op.create_index(
        'ix_care_profile_payments_pregnancy_id',
        'care_profile_payments',
        ['pregnancy_id'],
        unique=False,
    )
    op.create_index(
        'ix_care_profile_payments_payment_type',
        'care_profile_payments',
        ['payment_type'],
        unique=False,
    )
    op.create_index(
        'ix_care_profile_payments_tx_ref',
        'care_profile_payments',
        ['tx_ref'],
        unique=True,
    )

    # 3. Add payment tracking columns to pregnancies
    # Set server_default='paid' so all existing pregnancies are automatically marked 'paid'
    op.add_column(
        'pregnancies',
        sa.Column('payment_status', sa.String(length=16), server_default=sa.text("'paid'"), nullable=False),
    )
    # Switch server_default for new pregnancy rows to 'unpaid'
    op.alter_column(
        'pregnancies',
        'payment_status',
        server_default=sa.text("'unpaid'"),
    )
    op.add_column(
        'pregnancies',
        sa.Column('amount_paid', sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        'pregnancies',
        sa.Column('currency', sa.String(length=8), server_default=sa.text("'ETB'"), nullable=False),
    )
    op.add_column(
        'pregnancies',
        sa.Column('payment_method', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'pregnancies',
        sa.Column('payment_tx_ref', sa.Text(), nullable=True),
    )
    op.add_column(
        'pregnancies',
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        'uq_pregnancies_payment_tx_ref',
        'pregnancies',
        ['payment_tx_ref'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_pregnancies_payment_tx_ref', 'pregnancies', type_='unique')
    op.drop_column('pregnancies', 'paid_at')
    op.drop_column('pregnancies', 'payment_tx_ref')
    op.drop_column('pregnancies', 'payment_method')
    op.drop_column('pregnancies', 'currency')
    op.drop_column('pregnancies', 'amount_paid')
    op.drop_column('pregnancies', 'payment_status')

    op.drop_index('ix_care_profile_payments_tx_ref', table_name='care_profile_payments')
    op.drop_index('ix_care_profile_payments_payment_type', table_name='care_profile_payments')
    op.drop_index('ix_care_profile_payments_pregnancy_id', table_name='care_profile_payments')
    op.drop_index('ix_care_profile_payments_child_id', table_name='care_profile_payments')
    op.drop_index('ix_care_profile_payments_user_id', table_name='care_profile_payments')

    op.drop_column('care_profile_payments', 'payment_type')
    op.drop_column('care_profile_payments', 'pregnancy_id')
    op.alter_column(
        'care_profile_payments',
        'child_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    op.rename_table('care_profile_payments', 'child_payments')
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
