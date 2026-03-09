from time import perf_counter

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.providers.base import BalanceFetchResult
from app.services.providers.utils import build_request_headers, extract_amount_breakdown, extract_payload

logger = get_logger("upstream")


class NewApiProvider:
    def fetch_balance(self, base_url: str, api_key: str, timeout_seconds: int) -> BalanceFetchResult:
        settings = get_settings()
        retries = max(1, settings.default_request_retries)
        last_error: str | None = None
        url = f"{base_url.rstrip('/')}/api/user/self"
        headers = build_request_headers(api_key)

        for attempt in range(1, retries + 1):
            started = perf_counter()
            try:
                logger.debug(
                    "provider=newapi request_start url={} attempt={}/{} timeout_seconds={} user_agent={}",
                    url,
                    attempt,
                    retries,
                    timeout_seconds,
                    headers.get("User-Agent"),
                )
                with httpx.Client(timeout=timeout_seconds) as client:
                    response = client.get(url, headers=headers)
                latency_ms = int((perf_counter() - started) * 1000)
                logger.debug(
                    "provider=newapi request_done url={} status={} latency_ms={} content_type={} response_excerpt={}",
                    url,
                    response.status_code,
                    latency_ms,
                    response.headers.get("content-type", ""),
                    response.text[:300],
                )

                if response.status_code >= 400:
                    return BalanceFetchResult(
                        success=False,
                        limit_amount=None,
                        usage_amount=None,
                        balance=None,
                        currency=None,
                        http_status=response.status_code,
                        latency_ms=latency_ms,
                        error_message=f"upstream http status {response.status_code}",
                        response_excerpt=response.text[:1000],
                    )

                try:
                    payload = extract_payload(response.json())
                except ValueError as exc:
                    logger.warning(
                        "provider=newapi invalid_json url={} status={} content_type={} error={} response_excerpt={}",
                        url,
                        response.status_code,
                        response.headers.get("content-type", ""),
                        str(exc),
                        response.text[:300],
                    )
                    return BalanceFetchResult(
                        success=False,
                        limit_amount=None,
                        usage_amount=None,
                        balance=None,
                        currency=None,
                        http_status=response.status_code,
                        latency_ms=latency_ms,
                        error_message=f"invalid json response: {exc}",
                        response_excerpt=response.text[:1000],
                    )

                limit_amount, usage_amount, balance, currency = extract_amount_breakdown(payload)
                logger.debug(
                    "provider=newapi response_parsed url={} attempt={}/{} limit_amount={} usage_amount={} balance={} currency={} payload_keys={}",
                    url,
                    attempt,
                    retries,
                    limit_amount,
                    usage_amount,
                    balance,
                    currency,
                    sorted(payload.keys()),
                )
                if balance is None:
                    return BalanceFetchResult(
                        success=False,
                        limit_amount=limit_amount,
                        usage_amount=usage_amount,
                        balance=None,
                        currency=currency,
                        http_status=response.status_code,
                        latency_ms=latency_ms,
                        error_message="unable to extract balance from response",
                        response_excerpt=response.text[:1000],
                    )

                return BalanceFetchResult(
                    success=True,
                    limit_amount=limit_amount,
                    usage_amount=usage_amount,
                    balance=balance,
                    currency=currency,
                    http_status=response.status_code,
                    latency_ms=latency_ms,
                    error_message=None,
                    response_excerpt=response.text[:1000],
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                logger.debug(
                    "provider=newapi request_exception url={} attempt={}/{} error={}",
                    url,
                    attempt,
                    retries,
                    last_error,
                )
                if attempt == retries:
                    latency_ms = int((perf_counter() - started) * 1000)
                    return BalanceFetchResult(
                        success=False,
                        limit_amount=None,
                        usage_amount=None,
                        balance=None,
                        currency=None,
                        http_status=None,
                        latency_ms=latency_ms,
                        error_message=last_error,
                        response_excerpt=None,
                    )

        return BalanceFetchResult(
            success=False,
            limit_amount=None,
            usage_amount=None,
            balance=None,
            currency=None,
            http_status=None,
            latency_ms=None,
            error_message=last_error or "unknown provider error",
            response_excerpt=None,
        )
