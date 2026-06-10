"""create token_sync_run table

Revision ID: e3d4b2a19f66
Revises: c7f932f7102c
Create Date: 2026-03-15 18:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3d4b2a19f66"
down_revision: Union[str, Sequence[str], None] = "c7f932f7102c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("token_sync_run"):
        return

    op.create_table(
        "token_sync_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_sync_run_id"), "token_sync_run", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_token_sync_run_id"), table_name="token_sync_run")
    op.drop_table("token_sync_run")
