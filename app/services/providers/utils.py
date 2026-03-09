from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

DEFAULT_USER_AGENT = (
    "codex_vscode/0.108.0-alpha.12 "
    "(Windows 10.0.22631; x86_64) unknown "
    "(VS Code; 26.304.20706)"
)
AMOUNT_PRECISION = Decimal("0.01")


def build_request_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": DEFAULT_USER_AGENT,
    }


def as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def quantize_amount(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(AMOUNT_PRECISION, rounding=ROUND_HALF_UP)


def extract_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    payload = data.get("data", data)
    return payload if isinstance(payload, dict) else {}


def extract_amount_breakdown(
    data: dict[str, Any],
) -> tuple[Decimal | None, Decimal | None, Decimal | None, str | None]:
    currency = data.get("currency") or "USD"

    for limit_key, usage_key in (
        ("quota", "used_quota"),
        ("total_granted", "total_used"),
        ("grant_amount", "used_amount"),
    ):
        limit_candidate = as_decimal(data.get(limit_key))
        usage_candidate = as_decimal(data.get(usage_key))
        if limit_candidate is not None and usage_candidate is not None:
            return (
                quantize_amount(limit_candidate),
                quantize_amount(usage_candidate),
                quantize_amount(limit_candidate - usage_candidate),
                currency,
            )

    for remaining_key in ("balance", "credit", "total_available", "remain_quota", "available_quota"):
        remaining_candidate = as_decimal(data.get(remaining_key))
        if remaining_candidate is not None:
            return None, None, quantize_amount(remaining_candidate), currency

    return None, None, None, data.get("currency")


def extract_subscription_limit(data: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    currency = data.get("currency") or "USD"

    for key in ("hard_limit_usd", "system_hard_limit_usd", "soft_limit_usd", "total_granted", "grant_amount"):
        value = as_decimal(data.get(key))
        if value is not None:
            return quantize_amount(value), currency

    return None, data.get("currency")


def extract_usage_total(data: dict[str, Any]) -> Decimal | None:
    for key in ("total_usage", "used_amount", "total_used"):
        value = as_decimal(data.get(key))
        if value is not None:
            return value
    return None
