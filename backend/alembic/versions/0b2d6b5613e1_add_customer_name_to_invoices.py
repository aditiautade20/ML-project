"""add_customer_name_to_invoices

Revision ID: 0b2d6b5613e1
Revises: e731bfa21290
Create Date: 2026-10-26 19:15:48.224723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b2d6b5613e1'
down_revision: Union[str, Sequence[str], None] = 'e731bfa21290'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('customer_name')
