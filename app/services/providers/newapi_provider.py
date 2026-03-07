from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.providers.base import BalanceFetchResult


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _extract_balance(data: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    balance = _as_decimal(data.get("balance"))
    if balance is not None:
        return balance, data.get("currency") or "USD"

    credit = _as_decimal(data.get("credit"))
    if credit is not None:
        return credit, data.get("currency") or "USD"

    quota = _as_decimal(data.get("quota"))
    used_quota = _as_decimal(data.get("used_quota"))
    if quota is not None and used_quota is not None:
        return quota - used_quota, data.get("currency") or "USD"

    return None, data.get("currency")


class NewApiProvider:
    def fetch_balance(self, base_url: str, api_key: str, timeout_seconds: int) -> BalanceFetchResult:
        settings = get_settings()
        retries = max(1, settings.default_request_retries)
        last_error: str | None = None

        for attempt in range(1, retries + 1):
            started = perf_counter()
            try:
                url = f"{base_url.rstrip('/')}/api/user/self"
                with httpx.Client(timeout=timeout_seconds) as client:
                    response = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                latency_ms = int((perf_counter() - started) * 1000)

                if response.status_code >= 400:
                    return BalanceFetchResult(
                        success=False,
                        balance=None,
                        currency=None,
                        http_status=response.status_code,
                        latency_ms=latency_ms,
                        error_message=f"upstream http status {response.status_code}",
                        response_excerpt=response.text[:1000],
                    )

                data = response.json()
                payload = data.get("data", data) if isinstance(data, dict) else {}
                if not isinstance(payload, dict):
                    payload = {}

                balance, currency = _extract_balance(payload)
                if balance is None:
                    return BalanceFetchResult(
                        success=False,
                        balance=None,
                        currency=currency,
                        http_status=response.status_code,
                        latency_ms=latency_ms,
                        error_message="unable to extract balance from response",
                        response_excerpt=response.text[:1000],
                    )

                return BalanceFetchResult(
                    success=True,
                    balance=balance,
                    currency=currency,
                    http_status=response.status_code,
                    latency_ms=latency_ms,
                    error_message=None,
                    response_excerpt=response.text[:1000],
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt == retries:
                    latency_ms = int((perf_counter() - started) * 1000)
                    return BalanceFetchResult(
                        success=False,
                        balance=None,
                        currency=None,
                        http_status=None,
                        latency_ms=latency_ms,
                        error_message=last_error,
                        response_excerpt=None,
                    )

        return BalanceFetchResult(
            success=False,
            balance=None,
            currency=None,
            http_status=None,
            latency_ms=None,
            error_message=last_error or "unknown provider error",
            response_excerpt=None,
        )
