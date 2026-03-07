from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass
class BalanceFetchResult:
    success: bool
    balance: Decimal | None
    currency: str | None
    http_status: int | None
    latency_ms: int | None
    error_message: str | None
    response_excerpt: str | None


class BalanceProvider(Protocol):
    def fetch_balance(self, base_url: str, api_key: str, timeout_seconds: int) -> BalanceFetchResult:
        ...
