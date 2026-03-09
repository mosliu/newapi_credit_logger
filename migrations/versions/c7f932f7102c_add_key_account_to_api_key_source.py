"""add key_account to api_key_source

Revision ID: c7f932f7102c
Revises: 8b9d5e21c0ab
Create Date: 2026-03-09 15:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7f932f7102c"
down_revision: Union[str, Sequence[str], None] = "8b9d5e21c0ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("api_key_source", sa.Column("key_account", sa.String(length=120), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("api_key_source", "key_account")
