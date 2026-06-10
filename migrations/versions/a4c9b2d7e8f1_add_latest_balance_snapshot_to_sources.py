"""add latest balance snapshot to sources

Revision ID: a4c9b2d7e8f1
Revises: e3d4b2a19f66
Create Date: 2026-06-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4c9b2d7e8f1"
down_revision: Union[str, Sequence[str], None] = "e3d4b2a19f66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE_NAME = "api_key_source"
_RECORD_TABLE_NAME = "balance_record"
_LATEST_RECORD_INDEX_NAME = "ix_balance_record_source_checked_id"
_COLUMNS = (
    ("latest_success", sa.Boolean(), {"nullable": True}),
    ("latest_limit_amount", sa.Numeric(precision=20, scale=2), {"nullable": True}),
    ("latest_usage_amount", sa.Numeric(precision=20, scale=2), {"nullable": True}),
    ("latest_balance", sa.Numeric(precision=20, scale=2), {"nullable": True}),
    ("latest_currency", sa.String(length=20), {"nullable": True}),
    ("latest_checked_at", sa.DateTime(timezone=True), {"nullable": True}),
    ("latest_http_status", sa.Integer(), {"nullable": True}),
    ("latest_latency_ms", sa.Integer(), {"nullable": True}),
    ("latest_error_message", sa.String(length=500), {"nullable": True}),
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE_NAME):
        return

    existing_columns = {item["name"] for item in inspector.get_columns(_TABLE_NAME)}
    for name, column_type, kwargs in _COLUMNS:
        if name not in existing_columns:
            op.add_column(_TABLE_NAME, sa.Column(name, column_type, **kwargs))

    if inspector.has_table(_RECORD_TABLE_NAME):
        existing_indexes = {item["name"] for item in inspector.get_indexes(_RECORD_TABLE_NAME)}
        if _LATEST_RECORD_INDEX_NAME not in existing_indexes:
            op.create_index(
                _LATEST_RECORD_INDEX_NAME,
                _RECORD_TABLE_NAME,
                ["source_id", "checked_at", "id"],
                unique=False,
            )
        _backfill_latest_snapshot()


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE_NAME):
        return

    if inspector.has_table(_RECORD_TABLE_NAME):
        existing_indexes = {item["name"] for item in inspector.get_indexes(_RECORD_TABLE_NAME)}
        if _LATEST_RECORD_INDEX_NAME in existing_indexes:
            op.drop_index(_LATEST_RECORD_INDEX_NAME, table_name=_RECORD_TABLE_NAME)

    existing_columns = {item["name"] for item in inspector.get_columns(_TABLE_NAME)}
    for name, _column_type, _kwargs in reversed(_COLUMNS):
        if name in existing_columns:
            op.drop_column(_TABLE_NAME, name)


def _backfill_latest_snapshot() -> None:
    op.execute(
        sa.text(
            """
            UPDATE api_key_source
            SET
                latest_success = (
                    SELECT br.success
                    FROM balance_record AS br
                    WHERE br.source_id = api_key_source.id
                    ORDER BY br.checked_at DESC, br.id DESC
                    LIMIT 1
                ),
                latest_limit_amount = (
                    SELECT br.limit_amount
                    FROM balance_record AS br
                    WHERE br.source_id = api_key_source.id
                    ORDER BY br.checked_at DESC, br.id DESC
                    LIMIT 1
                ),
                latest_usage_amount = (
                    SELECT br.usage_amount
                    FROM balance_record AS br
                    WHERE br.source_id = api_key_source.id
                    ORDER BY br.checked_at DESC, br.id DESC
                    LIMIT 1
                ),
                latest_balance = (
                    SELECT br.balance
                    FROM balance_record AS br
                    WHERE br.source_id = api_key_source.id
                    ORDER BY br.checked_at DESC, br.id DESC
                    LIMIT 1
                ),
                latest_currency = (
                    SELECT br.currency
                    FROM balance_record AS br
                    WHERE br.source_id = api_key_source.id
                    ORDER BY br.checked_at DESC, br.id DESC
                    LIMIT 1
                ),
                latest_checked_at = (
                    SELECT br.checked_at
                    FROM balance_record AS br
                    WHERE br.source_id = api_key_source.id
                    ORDER BY br.checked_at DESC, br.id DESC
                    LIMIT 1
                ),
                latest_http_status = (
                    SELECT br.http_status
                    FROM balance_record AS br
                    WHERE br.source_id = api_key_source.id
                    ORDER BY br.checked_at DESC, br.id DESC
                    LIMIT 1
                ),
                latest_latency_ms = (
                    SELECT br.latency_ms
                    FROM balance_record AS br
                    WHERE br.source_id = api_key_source.id
                    ORDER BY br.checked_at DESC, br.id DESC
                    LIMIT 1
                ),
                latest_error_message = (
                    SELECT br.error_message
                    FROM balance_record AS br
                    WHERE br.source_id = api_key_source.id
                    ORDER BY br.checked_at DESC, br.id DESC
                    LIMIT 1
                )
            WHERE EXISTS (
                SELECT 1
                FROM balance_record AS br
                WHERE br.source_id = api_key_source.id
            )
            """
        )
    )
