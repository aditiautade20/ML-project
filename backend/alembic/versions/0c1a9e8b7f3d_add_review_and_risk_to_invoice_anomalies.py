"""add_review_and_risk_to_invoice_anomalies

Revision ID: 0c1a9e8b7f3d
Revises: 0b2d6b5613e1
Create Date: 2026-10-26 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c1a9e8b7f3d'
down_revision: Union[str, Sequence[str], None] = '0b2d6b5613e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add review tracking and risk classification to invoice_anomalies."""
    with op.batch_alter_table('invoice_anomalies', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_reviewed', sa.Boolean(), nullable=False, server_default=sa.text('0'))
        )
        batch_op.add_column(
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column('review_notes', sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('risk_level', sa.String(length=50), nullable=False, server_default='LOW')
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('invoice_anomalies', schema=None) as batch_op:
        batch_op.drop_column('risk_level')
        batch_op.drop_column('review_notes')
        batch_op.drop_column('reviewed_at')
        batch_op.drop_column('is_reviewed')
