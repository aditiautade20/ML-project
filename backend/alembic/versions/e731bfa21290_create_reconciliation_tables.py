"""create_reconciliation_tables

Revision ID: e731bfa21290
Revises: 124ce3d66d98
Create Date: 2026-10-25 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e731bfa21290'
down_revision: Union[str, Sequence[str], None] = '124ce3d66d98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create reconciliation_batches table
    op.create_table(
        'reconciliation_batches',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('batch_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='COMPLETED'),
        sa.Column('ledger_filename', sa.String(length=255), nullable=True),
        sa.Column('ledger_hash', sa.String(length=64), nullable=True),
        sa.Column('bank_filename', sa.String(length=255), nullable=True),
        sa.Column('bank_hash', sa.String(length=64), nullable=True),
        sa.Column('total_records', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('exact_matches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('mismatches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unmatched_records', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('amount_tolerance', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.05'),
        sa.Column('summary_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('reconciliation_batches', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reconciliation_batches_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reconciliation_batches_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reconciliation_batches_ledger_hash'), ['ledger_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_reconciliation_batches_bank_hash'), ['bank_hash'], unique=False)

    # 2. Create reconciliation_items table
    op.create_table(
        'reconciliation_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('item_type', sa.String(length=50), nullable=False),
        sa.Column('match_status', sa.String(length=50), nullable=False),
        sa.Column('record_identifier', sa.String(length=100), nullable=False),
        sa.Column('vendor_or_counterparty', sa.String(length=255), nullable=True),
        sa.Column('transaction_date', sa.String(length=50), nullable=True),
        sa.Column('expected_value', sa.String(length=100), nullable=True),
        sa.Column('actual_value', sa.String(length=100), nullable=True),
        sa.Column('discrepancy_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
        sa.Column('evidence_text', sa.Text(), nullable=True),
        sa.Column('action_recommendation', sa.Text(), nullable=True),
        sa.Column('review_status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('raw_record_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['reconciliation_batches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('reconciliation_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reconciliation_items_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reconciliation_items_batch_id'), ['batch_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reconciliation_items_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reconciliation_items_invoice_id'), ['invoice_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reconciliation_items_payment_id'), ['payment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reconciliation_items_match_status'), ['match_status'], unique=False)


def downgrade() -> None:
    op.drop_table('reconciliation_items')
    op.drop_table('reconciliation_batches')
