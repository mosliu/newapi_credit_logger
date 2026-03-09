"""add customer and fee fields to api_key_source

Revision ID: 8b9d5e21c0ab
Revises: 1a94810e8cff
Create Date: 2026-03-09 14:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8b9d5e21c0ab"
down_revision: Union[str, Sequence[str], None] = "1a94810e8cff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("api_key_source", sa.Column("customer_info", sa.String(length=255), nullable=True))
    op.add_column("api_key_source", sa.Column("key_created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("api_key_source", sa.Column("fee_amount", sa.Numeric(precision=20, scale=2), nullable=True))
    op.add_column("api_key_source", sa.Column("fee_currency", sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("api_key_source", "fee_currency")
    op.drop_column("api_key_source", "fee_amount")
    op.drop_column("api_key_source", "key_created_at")
    op.drop_column("api_key_source", "customer_info")
