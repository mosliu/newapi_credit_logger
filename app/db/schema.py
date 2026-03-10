from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import engine

logger = get_logger("app")


_REQUIRED_TABLE_COLUMNS: dict[str, set[str]] = {
    "api_key_source": {
        "id",
        "name",
        "provider_type",
        "base_url",
        "api_key_encrypted",
        "key_owner",
        "key_account",
        "customer_info",
        "key_created_at",
        "fee_amount",
        "fee_currency",
        "remark",
        "interval_seconds",
        "timeout_seconds",
        "enabled",
        "created_at",
        "updated_at",
    },
    "balance_record": {
        "id",
        "source_id",
        "checked_at",
        "success",
        "limit_amount",
        "usage_amount",
        "balance",
        "currency",
        "http_status",
        "latency_ms",
        "error_message",
        "response_excerpt",
    },
}


def _build_alembic_config(database_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _get_head_revision(config: Config) -> str:
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if not heads:
        raise RuntimeError("alembic heads not found")
    if len(heads) > 1:
        raise RuntimeError(f"multiple alembic heads detected: {heads}")
    return heads[0]


def _validate_required_columns() -> None:
    inspector = inspect(engine)
    for table_name, expected_columns in _REQUIRED_TABLE_COLUMNS.items():
        columns = {item["name"] for item in inspector.get_columns(table_name)}
        missing = expected_columns - columns
        if missing:
            raise RuntimeError(
                f"table {table_name} missing columns: {sorted(missing)}"
            )


def ensure_database_schema() -> None:
    """Ensure required tables exist and schema is upgraded to alembic head.

    Strategy:
    - If required tables are missing: run `alembic upgrade head`.
    - If tables exist but `alembic_version` is missing: validate columns then stamp head.
    - If `alembic_version` exists but not at head: run `alembic upgrade head`.
    """
    settings = get_settings()
    config = _build_alembic_config(settings.database_url)
    head = _get_head_revision(config)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    required_tables = set(_REQUIRED_TABLE_COLUMNS.keys())
    missing_tables = required_tables - table_names
    if missing_tables:
        logger.warning(
            "database missing tables={} -> running alembic upgrade head",
            sorted(missing_tables),
        )
        command.upgrade(config, "head")
        _validate_required_columns()
        return

    if "alembic_version" not in table_names:
        _validate_required_columns()
        logger.warning(
            "alembic_version missing but tables exist -> stamping head={}",
            head,
        )
        command.stamp(config, "head")
        return

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current = context.get_current_revision()

    if current != head:
        logger.warning(
            "database revision mismatch current={} head={} -> upgrading",
            current,
            head,
        )
        command.upgrade(config, "head")
        _validate_required_columns()
        return

    _validate_required_columns()
    logger.info("database schema ok revision={}", head)
