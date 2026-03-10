from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiKeySource(Base):
    __tablename__ = "api_key_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    provider_type: Mapped[str] = mapped_column(String(30), nullable=False, default="newapi")
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    key_owner: Mapped[str] = mapped_column(String(100), nullable=False)
    key_account: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    key_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(precision=20, scale=2), nullable=True)
    fee_currency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
