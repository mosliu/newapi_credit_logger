from decimal import Decimal
from time import perf_counter

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.providers.base import BalanceFetchResult
from app.services.providers.utils import (
    build_request_headers,
    extract_amount_breakdown,
    extract_payload,
    extract_subscription_limit,
    extract_usage_total,
    quantize_amount,
)

logger = get_logger("upstream")


class CompatibleBillingProvider:
    def __init__(
        self,
        *,
        credit_grants_paths: tuple[str, ...],
        subscription_paths: tuple[str, ...],
        usage_paths: tuple[str, ...] = (),
    ):
        self._credit_grants_paths = credit_grants_paths
        self._subscription_paths = subscription_paths
        self._usage_paths = usage_paths

    def fetch_balance(self, base_url: str, api_key: str, timeout_seconds: int) -> BalanceFetchResult:
        settings = get_settings()
        retries = max(1, settings.default_request_retries)
        last_error: str | None = None
        headers = build_request_headers(api_key)

        for attempt in range(1, retries + 1):
            started = perf_counter()
            try:
                logger.debug(
                    "provider=compatible request_batch_start base_url={} attempt={}/{} timeout_seconds={} credit_grants_paths={} subscription_paths={} usage_paths={} user_agent={}",
                    base_url.rstrip('/'),
                    attempt,
                    retries,
                    timeout_seconds,
                    self._credit_grants_paths,
                    self._subscription_paths,
                    self._usage_paths,
                    headers.get("User-Agent"),
                )
                with httpx.Client(timeout=timeout_seconds) as client:
                    result = self._fetch_from_paths(
                        client=client,
                        base_url=base_url,
                        headers=headers,
                        paths=self._credit_grants_paths,
                    )
                    if result is not None:
                        result.latency_ms = int((perf_counter() - started) * 1000)
                        return result

                    result = self._fetch_remaining_from_usage_and_subscription(
                        client=client,
                        base_url=base_url,
                        headers=headers,
                    )
                    if result is not None:
                        result.latency_ms = int((perf_counter() - started) * 1000)
                        return result

                    result = self._fetch_from_paths(
                        client=client,
                        base_url=base_url,
                        headers=headers,
                        paths=self._subscription_paths,
                    )
                    if result is not None:
                        result.latency_ms = int((perf_counter() - started) * 1000)
                        return result

                return BalanceFetchResult(
                    success=False,
                    limit_amount=None,
                    usage_amount=None,
                    balance=None,
                    currency=None,
                    http_status=404,
                    latency_ms=int((perf_counter() - started) * 1000),
                    error_message="no compatible billing endpoint found",
                    response_excerpt=None,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                logger.debug(
                    "provider=compatible request_batch_exception base_url={} attempt={}/{} error={}",
                    base_url.rstrip('/'),
                    attempt,
                    retries,
                    last_error,
                )
                if attempt == retries:
                    return BalanceFetchResult(
                        success=False,
                        limit_amount=None,
                        usage_amount=None,
                        balance=None,
                        currency=None,
                        http_status=None,
                        latency_ms=int((perf_counter() - started) * 1000),
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

    def _fetch_remaining_from_usage_and_subscription(
        self,
        *,
        client: httpx.Client,
        base_url: str,
        headers: dict[str, str],
    ) -> BalanceFetchResult | None:
        if not self._usage_paths or not self._subscription_paths:
            return None

        subscription_response = self._request_first_supported(
            client=client,
            base_url=base_url,
            headers=headers,
            paths=self._subscription_paths,
        )
        if subscription_response is None:
            return None

        usage_response = self._request_first_supported(
            client=client,
            base_url=base_url,
            headers=headers,
            paths=self._usage_paths,
        )
        if usage_response is None:
            return None

        if subscription_response.status_code >= 400:
            return BalanceFetchResult(
                success=False,
                limit_amount=None,
                usage_amount=None,
                balance=None,
                currency=None,
                http_status=subscription_response.status_code,
                latency_ms=None,
                error_message=f"upstream http status {subscription_response.status_code}",
                response_excerpt=subscription_response.text[:1000],
            )

        if usage_response.status_code >= 400:
            return BalanceFetchResult(
                success=False,
                limit_amount=None,
                usage_amount=None,
                balance=None,
                currency=None,
                http_status=usage_response.status_code,
                latency_ms=None,
                error_message=f"upstream http status {usage_response.status_code}",
                response_excerpt=usage_response.text[:1000],
            )

        try:
            subscription_payload = extract_payload(subscription_response.json())
            usage_payload = extract_payload(usage_response.json())
        except ValueError as exc:
            return BalanceFetchResult(
                success=False,
                limit_amount=None,
                usage_amount=None,
                balance=None,
                currency=None,
                http_status=subscription_response.status_code,
                latency_ms=None,
                error_message=f"invalid json response: {exc}",
                response_excerpt=(subscription_response.text or usage_response.text)[:1000],
            )

        direct_limit_amount, direct_usage_amount, direct_balance, direct_currency = extract_amount_breakdown(
            subscription_payload
        )
        if direct_balance is not None:
            return BalanceFetchResult(
                success=True,
                limit_amount=direct_limit_amount,
                usage_amount=direct_usage_amount,
                balance=direct_balance,
                currency=direct_currency,
                http_status=subscription_response.status_code,
                latency_ms=None,
                error_message=None,
                response_excerpt=subscription_response.text[:1000],
            )

        limit_value, currency = extract_subscription_limit(subscription_payload)
        usage_total_fen = extract_usage_total(usage_payload)
        if limit_value is None or usage_total_fen is None:
            return None

        usage_amount = quantize_amount(usage_total_fen / Decimal("100"))
        balance = quantize_amount(limit_value - usage_amount)
        logger.debug(
            "provider=compatible usage_subscription_balance base_url={} limit_amount={} usage_amount={} balance={} currency={}",
            base_url.rstrip('/'),
            limit_value,
            usage_amount,
            balance,
            currency,
        )
        return BalanceFetchResult(
            success=True,
            limit_amount=limit_value,
            usage_amount=usage_amount,
            balance=balance,
            currency=currency,
            http_status=subscription_response.status_code,
            latency_ms=None,
            error_message=None,
            response_excerpt=subscription_response.text[:1000],
        )

    def _request_first_supported(
        self,
        *,
        client: httpx.Client,
        base_url: str,
        headers: dict[str, str],
        paths: tuple[str, ...],
    ) -> httpx.Response | None:
        for path in paths:
            url = f"{base_url.rstrip('/')}{path}"
            logger.debug("provider=compatible probe_start url={}", url)
            response = client.get(url, headers=headers)
            logger.debug(
                "provider=compatible probe_done url={} status={} content_type={} response_excerpt={}",
                url,
                response.status_code,
                response.headers.get("content-type", ""),
                response.text[:300],
            )
            if response.status_code in {404, 405}:
                continue
            return response
        return None

    def _fetch_from_paths(
        self,
        *,
        client: httpx.Client,
        base_url: str,
        headers: dict[str, str],
        paths: tuple[str, ...],
    ) -> BalanceFetchResult | None:
        for path in paths:
            url = f"{base_url.rstrip('/')}{path}"
            logger.debug("provider=compatible request_start url={}", url)
            response = client.get(url, headers=headers)
            logger.debug(
                "provider=compatible request_done url={} status={} content_type={} response_excerpt={}",
                url,
                response.status_code,
                response.headers.get("content-type", ""),
                response.text[:300],
            )

            if response.status_code in {404, 405}:
                logger.debug("provider=compatible endpoint_skip url={} status={}", url, response.status_code)
                continue

            if response.status_code >= 400:
                return BalanceFetchResult(
                    success=False,
                    limit_amount=None,
                    usage_amount=None,
                    balance=None,
                    currency=None,
                    http_status=response.status_code,
                    latency_ms=None,
                    error_message=f"upstream http status {response.status_code}",
                    response_excerpt=response.text[:1000],
                )

            try:
                payload = extract_payload(response.json())
            except ValueError as exc:
                logger.warning(
                    "provider=compatible invalid_json url={} status={} content_type={} error={} response_excerpt={}",
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
                    latency_ms=None,
                    error_message=f"invalid json response: {exc}",
                    response_excerpt=response.text[:1000],
                )

            limit_amount, usage_amount, balance, currency = extract_amount_breakdown(payload)
            logger.debug(
                "provider=compatible response_parsed url={} limit_amount={} usage_amount={} balance={} currency={} payload_keys={}",
                url,
                limit_amount,
                usage_amount,
                balance,
                currency,
                sorted(payload.keys()),
            )
            if balance is None:
                logger.debug("provider=compatible balance_extract_failed url={}", url)
                continue

            return BalanceFetchResult(
                success=True,
                limit_amount=limit_amount,
                usage_amount=usage_amount,
                balance=balance,
                currency=currency,
                http_status=response.status_code,
                latency_ms=None,
                error_message=None,
                response_excerpt=response.text[:1000],
            )

        return None
