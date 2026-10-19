"""Add patient payout methods and Chapa transfer references

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-19 12:58:39.891221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create patient_payout_methods table
    op.create_table(
        'patient_payout_methods',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('holder_name', sa.Text(), nullable=False),
        sa.Column('account_number', sa.Text(), nullable=False),
        sa.Column('bank_name', sa.Text(), nullable=False),
        sa.Column('bank_code', sa.Text(), nullable=True),
        sa.Column('swift_code', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('currency', sa.String(length=8), server_default=sa.text("'ETB'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(
        'ix_patient_payout_methods_patient_id',
        'patient_payout_methods',
        ['patient_id'],
        unique=False,
    )

    # 2. Add chapa_transfer_reference to doctor_payout_requests
    op.add_column(
        'doctor_payout_requests',
        sa.Column('chapa_transfer_reference', sa.Text(), nullable=True),
    )

    # 3. Add payout_method_id, admin_note, payment_date, chapa_transfer_reference to patient_wallet_withdrawal_requests
    op.add_column(
        'patient_wallet_withdrawal_requests',
        sa.Column('payout_method_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        'patient_wallet_withdrawal_requests',
        sa.Column('admin_note', sa.Text(), nullable=True),
    )
    op.add_column(
        'patient_wallet_withdrawal_requests',
        sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'patient_wallet_withdrawal_requests',
        sa.Column('chapa_transfer_reference', sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        'fk_patient_wallet_withdrawal_requests_payout_method_id',
        'patient_wallet_withdrawal_requests',
        'patient_payout_methods',
        ['payout_method_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_patient_wallet_withdrawal_requests_payout_method_id',
        'patient_wallet_withdrawal_requests',
        type_='foreignkey',
    )
    op.drop_column('patient_wallet_withdrawal_requests', 'chapa_transfer_reference')
    op.drop_column('patient_wallet_withdrawal_requests', 'payment_date')
    op.drop_column('patient_wallet_withdrawal_requests', 'admin_note')
    op.drop_column('patient_wallet_withdrawal_requests', 'payout_method_id')

    op.drop_column('doctor_payout_requests', 'chapa_transfer_reference')

    op.drop_index('ix_patient_payout_methods_patient_id', table_name='patient_payout_methods')
    op.drop_table('patient_payout_methods')
