from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.providers.utils import extract_amount_breakdown, extract_payload

CHANNELS = {"openai_chat", "openai_responses", "gemini", "claude"}
CLI_PROFILES = {"default", "cc", "codex", "geminicli"}
CLI_UA_MAP = {
    "default": "html-api-test/1.1",
    "cc": "cc-cli/1.0",
    "codex": "codex-cli/1.0",
    "geminicli": "gemini-cli/1.0",
}

_TOKEN_RE = re.compile(r"^sk-[A-Za-z0-9_-]{10,}$")
_URL_RE = re.compile(r"^https?://", flags=re.I)

logger = get_logger("app")
upstream_logger = get_logger("upstream")


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_sec: int = 60) -> None:
        self.max_requests = max_requests
        self.window_sec = window_sec
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_sec
        hits = [hit for hit in self._hits[key] if hit > cutoff]
        self._hits[key] = hits
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True


@dataclass(frozen=True)
class LLMParserConfig:
    channel: str
    base_url: str
    api_key: str
    model: str
    timeout_sec: float
    cli_profile: str

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def validate_or_raise(self) -> None:
        if self.channel not in CHANNELS:
            raise ValueError(
                "PARSER_LLM_CHANNEL 无效，允许值：openai_chat/openai_responses/gemini/claude"
            )
        if not self.enabled:
            raise ValueError(
                "LLM 解析器未配置完成。请设置环境变量："
                "PARSER_LLM_BASE_URL, PARSER_LLM_API_KEY, PARSER_LLM_MODEL"
            )


@dataclass
class NekoToolConfig:
    enabled: bool
    show_balance: bool
    show_detail: bool
    base_urls: dict[str, str]
    default_site_key: str
    timeout_sec: float

    def normalize(self) -> NekoToolConfig:
        if self.default_site_key not in self.base_urls:
            self.default_site_key = next(iter(self.base_urls.keys()), "")
        self.enabled = bool(self.base_urls)
        return self

    def to_client_payload(self) -> dict[str, Any]:
        default_base_url = ""
        if self.default_site_key and self.default_site_key in self.base_urls:
            default_base_url = self.base_urls[self.default_site_key]
        elif self.base_urls:
            default_base_url = next(iter(self.base_urls.values()), "")

        return {
            "enabled": self.enabled,
            "showBalance": self.show_balance,
            "showDetail": self.show_detail,
            "baseUrls": self.base_urls,
            "defaultSiteKey": self.default_site_key,
            "defaultBaseUrl": default_base_url,
            "timeoutSec": self.timeout_sec,
        }


def normalize_cli_profile(profile: str) -> str:
    value = (profile or "").strip().lower()
    return value if value in CLI_PROFILES else "default"


def resolve_default_cli_profile(settings: Settings) -> str:
    return normalize_cli_profile((settings.default_cli_profile or "codex").strip())


def build_cli_headers(cli_profile: str) -> dict[str, str]:
    profile = normalize_cli_profile(cli_profile)
    return {
        "User-Agent": CLI_UA_MAP.get(profile, CLI_UA_MAP["default"]),
        "X-Api-Client": profile,
    }


def build_ui_config_payload(settings: Settings) -> dict[str, Any]:
    default_channel = (settings.default_test_channel or "").strip().lower()
    if default_channel not in CHANNELS:
        default_channel = "openai_responses"
    return {
        "defaultChannel": default_channel,
        "defaults": {
            "openai_chat": {
                "baseUrl": settings.default_openai_base_url.strip(),
                "model": settings.default_openai_chat_model.strip(),
            },
            "openai_responses": {
                "baseUrl": settings.default_openai_base_url.strip(),
                "model": settings.default_openai_responses_model.strip(),
            },
            "gemini": {
                "baseUrl": settings.default_gemini_base_url.strip(),
                "model": settings.default_gemini_model.strip(),
            },
            "claude": {
                "baseUrl": settings.default_claude_base_url.strip(),
                "model": settings.default_claude_model.strip(),
            },
        },
    }


def build_parser_llm_config(settings: Settings) -> LLMParserConfig:
    timeout_sec = float(settings.parser_llm_timeout_sec)
    timeout_sec = max(3.0, min(120.0, timeout_sec))
    channel = (settings.parser_llm_channel or "openai_chat").strip().lower()
    cli_profile = normalize_cli_profile(
        (settings.parser_llm_cli_profile or settings.default_cli_profile or "default").strip()
    )
    return LLMParserConfig(
        channel=channel,
        base_url=(settings.parser_llm_base_url or "").strip(),
        api_key=(settings.parser_llm_api_key or "").strip(),
        model=(settings.parser_llm_model or "").strip(),
        timeout_sec=timeout_sec,
        cli_profile=cli_profile,
    )


def _parse_neko_base_urls(raw_urls: str) -> dict[str, str]:
    raw = (raw_urls or "{}").strip()
    parsed: dict[str, str] = {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            for key, value in data.items():
                key_text = str(key).strip()
                value_text = str(value).strip()
                if key_text and value_text:
                    parsed[key_text] = value_text.rstrip("/")
        elif isinstance(data, str) and data.strip():
            parsed["default"] = data.strip().rstrip("/")
    except Exception:
        parsed = {}
    return parsed


def build_neko_tool_config(settings: Settings) -> NekoToolConfig:
    base_urls = _parse_neko_base_urls(settings.neko_base_urls)
    fallback_single = (settings.neko_base_url or "").strip()
    if not base_urls and fallback_single:
        base_urls["default"] = fallback_single.rstrip("/")

    default_site_key = (settings.neko_default_site_key or "").strip()
    if not default_site_key or default_site_key not in base_urls:
        default_site_key = next(iter(base_urls.keys()), "")

    config = NekoToolConfig(
        enabled=bool(base_urls),
        show_balance=bool(settings.neko_show_balance),
        show_detail=bool(settings.neko_show_detail),
        base_urls=base_urls,
        default_site_key=default_site_key,
        timeout_sec=max(3.0, min(120.0, float(settings.neko_timeout_sec))),
    )
    return config.normalize()


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 10:
        return f"{key[:2]}***"
    return f"{key[:6]}...{key[-4:]}"


def truncate_text(text: str, limit: int = 220) -> str:
    value = (text or "").replace("\n", "\\n")
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...(truncated:{len(value) - limit})"


def safe_json_dumps(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)


def mask_dict_for_log(data: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()
        if isinstance(value, str) and any(token in key_lower for token in ("key", "token", "authorization")):
            masked[key] = mask_key(value)
        else:
            masked[key] = value
    return masked


def normalize_url_candidate(raw: str) -> str:
    if not raw:
        return ""
    cleaned = raw.strip().strip("<>").strip()
    cleaned = cleaned.split("](")[0]
    cleaned = cleaned.rstrip(")],。；;，")
    return cleaned


def decode_redirect_url(url: str) -> str:
    try:
        query = parse_qs(urlparse(url).query)
    except Exception:
        return ""
    for key in ("to", "url", "target", "redirect", "redirect_url", "dest"):
        value = query.get(key, [""])[0].strip()
        if re.match(r"^https?://", value, flags=re.I):
            return normalize_url_candidate(value)
    return ""


def extract_first_url(text: str) -> str:
    candidates: list[str] = []
    markdown_links = re.findall(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", text, flags=re.I)
    for label, href in markdown_links:
        label_url = normalize_url_candidate(label)
        href_url = normalize_url_candidate(href)
        if re.match(r"^https?://", label_url, flags=re.I):
            candidates.append(label_url)
        if re.match(r"^https?://", href_url, flags=re.I):
            redirect = decode_redirect_url(href_url)
            if redirect:
                candidates.append(redirect)
            candidates.append(href_url)

    plain_urls = re.findall(r"https?://[^\s\"'`<>\])]+", text, flags=re.I)
    for raw in plain_urls:
        url = normalize_url_candidate(raw)
        if not re.match(r"^https?://", url, flags=re.I):
            continue
        redirect = decode_redirect_url(url)
        if redirect:
            candidates.append(redirect)
        candidates.append(url)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            return candidate
    return ""


def extract_base_url(url: str) -> str:
    if not url:
        return ""
    no_query = url.split("?")[0]
    no_query = re.sub(r"/v1/chat/completions$", "", no_query, flags=re.I)
    no_query = re.sub(r"/v1/responses$", "", no_query, flags=re.I)
    no_query = re.sub(r"/v1/messages$", "", no_query, flags=re.I)
    no_query = re.sub(r"/v1beta/models/[^/:]+:generateContent$", "/v1beta", no_query, flags=re.I)
    return no_query


def pick_channel_by_text(text: str, key: str) -> str:
    text_lower = (text or "").lower()
    if key.startswith("sk-ant-") or "anthropic" in text_lower or "claude" in text_lower:
        return "claude"
    if key.startswith("AIza") or "gemini" in text_lower or "generativelanguage" in text_lower:
        return "gemini"
    if "/v1/responses" in text_lower or "responses" in text_lower:
        return "openai_responses"
    return "openai_chat"


def parse_by_rules(raw_text: str) -> dict[str, str]:
    text = (raw_text or "").strip()
    lines = text.splitlines()
    kv: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*[:=]\s*(.+?)\s*$", line)
        if not match:
            continue
        key = match.group(1).lower()
        value = match.group(2).strip().strip('"').strip("'")
        kv[key] = value

    base_candidates = [kv.get(key, "") for key in ("base_url", "api_base", "baseurl", "endpoint", "url", "host")]
    key_candidates = [kv.get(key, "") for key in ("api_key", "apikey", "key", "token", "authorization")]
    model_candidates = [kv.get(key, "") for key in ("model", "model_name", "deployment", "deployment_name")]

    base_candidates = [item for item in base_candidates if item]
    key_candidates = [item for item in key_candidates if item]
    model_candidates = [item for item in model_candidates if item]

    url_value = extract_first_url(text)
    key_from_query = ""
    if url_value:
        try:
            key_from_query = parse_qs(urlparse(url_value).query).get("key", [""])[0]
        except Exception:
            key_from_query = ""

    key_match = (
        re.search(r"sk-ant-[A-Za-z0-9_-]{10,}", text)
        or re.search(r"AIza[0-9A-Za-z_-]{20,}", text)
        or re.search(r"sk-[A-Za-z0-9_-]{10,}", text)
    )
    model_match = re.search(r"\b(gpt-[A-Za-z0-9._-]+|claude-[A-Za-z0-9._-]+|gemini-[A-Za-z0-9._-]+)\b", text)

    api_key = (key_candidates[0] if key_candidates else "") or key_from_query or (key_match.group(0) if key_match else "")
    api_key = re.sub(r"^Bearer\s+", "", api_key, flags=re.I)
    base_url = extract_base_url((base_candidates[0] if base_candidates else "") or url_value)
    model = (model_candidates[0] if model_candidates else "") or (model_match.group(0) if model_match else "")
    channel = pick_channel_by_text(text, api_key)

    return {"channel": channel, "baseUrl": base_url, "apiKey": api_key, "model": model}


def try_parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def safe_extract_json(text: str) -> dict[str, Any] | None:
    direct = try_parse_json(text or "")
    if isinstance(direct, dict):
        return direct

    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text or "", flags=re.I)
    if code_block:
        from_block = try_parse_json(code_block.group(1).strip())
        if isinstance(from_block, dict):
            return from_block

    object_match = re.search(r"\{[\s\S]*\}", text or "")
    if object_match:
        from_object = try_parse_json(object_match.group(0))
        if isinstance(from_object, dict):
            return from_object

    return None


def normalize_base_url(raw: str) -> str:
    return (raw or "").strip().rstrip("/")


def build_endpoint(base_url: str, path: str) -> str:
    base = normalize_base_url(base_url)
    fixed = path
    if base.endswith("/v1") and fixed.startswith("/v1/"):
        fixed = fixed[3:]
    if base.endswith("/v1beta") and fixed.startswith("/v1beta/"):
        fixed = fixed[7:]
    return f"{base}{fixed}"


def extract_text_from_response(channel: str, response: Any) -> str:
    if isinstance(response, str):
        return response
    if not isinstance(response, dict):
        return ""
    try:
        if channel == "openai_chat":
            choices = response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if isinstance(content, list):
                    chunks = [chunk.get("text", "") for chunk in content if isinstance(chunk, dict)]
                    return "\n".join(chunk for chunk in chunks if chunk).strip()
                if isinstance(content, str):
                    return content
        elif channel == "openai_responses":
            output_text = response.get("output_text")
            if isinstance(output_text, str):
                return output_text
            output_items = response.get("output", [])
            texts: list[str] = []
            for item in output_items:
                if not isinstance(item, dict):
                    continue
                for content in item.get("content", []):
                    if isinstance(content, dict):
                        text = content.get("text", "")
                        if text:
                            texts.append(text)
            return "\n".join(texts).strip()
        elif channel == "gemini":
            candidates = response.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                texts = [part.get("text", "") for part in parts if isinstance(part, dict) and part.get("text")]
                return "\n".join(texts).strip()
        elif channel == "claude":
            parts = response.get("content", [])
            texts = [part.get("text", "") for part in parts if isinstance(part, dict) and part.get("text")]
            return "\n".join(texts).strip()
    except Exception:
        upstream_logger.warning("[extract_text] channel={} 解析失败", channel, exc_info=True)
        return ""
    return ""


async def call_provider(
    *,
    client: httpx.AsyncClient,
    channel: str,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout_sec: float,
    cli_profile: str = "default",
    log_preview_len: int = 220,
) -> dict[str, Any]:
    if channel not in CHANNELS:
        raise ValueError("不支持的渠道")

    profile = normalize_cli_profile(cli_profile)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    headers.update(build_cli_headers(profile))
    body: dict[str, Any]

    if channel == "openai_chat":
        url = build_endpoint(base_url, "/v1/chat/completions")
        headers["Authorization"] = f"Bearer {api_key}"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    elif channel == "openai_responses":
        url = build_endpoint(base_url, "/v1/responses")
        headers["Authorization"] = f"Bearer {api_key}"
        body = {"model": model, "input": prompt}
    elif channel == "gemini":
        url = build_endpoint(
            base_url,
            f"/v1beta/models/{quote(model, safe='')}:generateContent?key={quote(api_key, safe='')}",
        )
        body = {"contents": [{"parts": [{"text": prompt}]}]}
    else:
        url = build_endpoint(base_url, "/v1/messages")
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        body = {
            "model": model,
            "max_tokens": 128,
            "messages": [{"role": "user", "content": prompt}],
        }

    request_url_masked = url.replace(api_key, mask_key(api_key)) if channel == "gemini" else url
    upstream_logger.info(
        "[UPSTREAM_REQ] channel={} model={} timeout_sec={} cli_profile={} ua={} url={} body={}",
        channel,
        model,
        timeout_sec,
        profile,
        headers.get("User-Agent", ""),
        request_url_masked,
        truncate_text(safe_json_dumps(mask_dict_for_log(body)), log_preview_len),
    )

    timeout = httpx.Timeout(connect=5.0, read=timeout_sec, write=10.0, pool=5.0)
    started = time.perf_counter()
    try:
        response = await client.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.TimeoutException as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        upstream_logger.warning(
            "[UPSTREAM_TIMEOUT] channel={} model={} elapsed_ms={} url={} error={}",
            channel,
            model,
            elapsed_ms,
            request_url_masked,
            exc,
        )
        raise TimeoutError(f"上游请求超时（{elapsed_ms}ms）：{exc}") from exc
    except httpx.ConnectError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        upstream_logger.warning(
            "[UPSTREAM_CONNECT_ERR] channel={} model={} elapsed_ms={} url={} error={}",
            channel,
            model,
            elapsed_ms,
            request_url_masked,
            exc,
        )
        raise ConnectionError(f"无法连接上游服务：{exc}") from exc
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        upstream_logger.exception(
            "[UPSTREAM_ERR] channel={} model={} elapsed_ms={} url={} error={}",
            channel,
            model,
            elapsed_ms,
            request_url_masked,
            exc,
        )
        raise RuntimeError(f"上游请求失败：{exc}") from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    content_type = response.headers.get("content-type", "")
    text = response.text
    parsed = try_parse_json(text) if "application/json" in content_type else None
    response_payload: Any = parsed if parsed is not None else text

    upstream_logger.info(
        "[UPSTREAM_RES] channel={} model={} status={} elapsed_ms={} cli_profile={} content_type={} body_preview={}",
        channel,
        model,
        response.status_code,
        elapsed_ms,
        profile,
        content_type,
        truncate_text(text, log_preview_len),
    )
    return {
        "status": response.status_code,
        "status_text": response.reason_phrase,
        "request_url_masked": request_url_masked,
        "response": response_payload,
    }


def validate_token_or_raise(token: str) -> str:
    value = (token or "").strip()
    if not value:
        raise ValueError("token 不能为空")
    if not _TOKEN_RE.match(value):
        raise ValueError("token 格式非法，期望以 sk- 开头且长度足够")
    return value


def resolve_base_url_or_raise(config: NekoToolConfig, base_url: str) -> tuple[str, str]:
    manual = (base_url or "").strip().rstrip("/")
    if manual:
        if not _URL_RE.match(manual):
            raise ValueError("base_url 格式非法，必须以 http:// 或 https:// 开头")
        return manual, "manual"

    default_key = (config.default_site_key or "").strip()
    if default_key:
        default_url = (config.base_urls.get(default_key) or "").strip().rstrip("/")
        if default_url:
            return default_url, f"config:{default_key}"

    for key, value in config.base_urls.items():
        resolved = (value or "").strip().rstrip("/")
        if resolved:
            return resolved, f"config:{key}"

    raise ValueError("请填写 NewAPI Base URL")


def _is_success_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "ok", "success", "200"}
    return False


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _pick_message(payload: Any, default: str) -> str:
    if isinstance(payload, dict):
        for key in ("message", "msg", "detail", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return default


def _extract_usage_info(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("usage 返回不是 JSON 对象")

    success = _is_success_flag(payload.get("success")) or _is_success_flag(payload.get("code"))
    data = payload.get("data")
    if isinstance(data, dict) and not success:
        success = True
    if not success or not isinstance(data, dict):
        raise RuntimeError(_pick_message(payload, "查询令牌信息失败"))

    expires_at = _to_int(data.get("expires_at", data.get("expired_time", 0)))
    return {
        "tokenName": data.get("name") or data.get("token_name") or "",
        "unlimitedQuota": bool(data.get("unlimited_quota", data.get("unlimitedQuota", False))),
        "totalGranted": _to_float(data.get("total_granted", data.get("totalGranted", 0))),
        "totalUsed": _to_float(data.get("total_used", data.get("totalUsed", 0))),
        "totalAvailable": _to_float(data.get("total_available", data.get("totalAvailable", 0))),
        "expiresAt": expires_at,
        "expiresAtText": _format_expire(expires_at),
    }


def _extract_logs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise RuntimeError("log 返回不是 JSON 对象")

    success = _is_success_flag(payload.get("success")) or _is_success_flag(payload.get("code"))
    data = payload.get("data")
    if isinstance(data, list) and not success:
        success = True
    if not success or not isinstance(data, list):
        raise RuntimeError(_pick_message(payload, "查询调用日志失败"))

    return list(reversed([item for item in data if isinstance(item, dict)]))


def _format_expire(expires_at: int) -> str:
    if expires_at <= 0:
        return "永不过期"
    try:
        dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    except Exception:
        return "未知"
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _build_stats(logs: list[dict[str, Any]]) -> dict[str, Any]:
    total_quota = 0.0
    total_prompt = 0
    total_completion = 0
    models: dict[str, int] = {}
    for row in logs:
        total_quota += _to_float(row.get("quota", 0))
        total_prompt += _to_int(row.get("prompt_tokens", 0))
        total_completion += _to_int(row.get("completion_tokens", 0))
        model = str(row.get("model_name") or "").strip()
        if model:
            models[model] = models.get(model, 0) + 1
    return {
        "logCount": len(logs),
        "totalQuota": total_quota,
        "totalPromptTokens": total_prompt,
        "totalCompletionTokens": total_completion,
        "models": models,
    }


async def _get_json(
    *,
    client: httpx.AsyncClient,
    url: str,
    url_for_log: str | None = None,
    headers: dict[str, str],
    timeout_sec: float,
    log_preview_len: int,
    log_tag: str,
) -> Any:
    started = time.perf_counter()
    log_url = url_for_log or url
    masked_headers = {
        key: (mask_key(value) if key.lower() == "authorization" else value)
        for key, value in headers.items()
    }
    upstream_logger.info(
        "[{}_REQ] url={} headers={}",
        log_tag,
        log_url,
        safe_json_dumps(masked_headers),
    )

    timeout = httpx.Timeout(connect=5.0, read=timeout_sec, write=10.0, pool=5.0)
    try:
        response = await client.get(url, headers=headers, timeout=timeout)
    except httpx.TimeoutException as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        upstream_logger.warning(
            "[{}_TIMEOUT] elapsed_ms={} url={} error={}",
            log_tag,
            elapsed_ms,
            log_url,
            exc,
        )
        raise TimeoutError(f"请求超时（{elapsed_ms}ms）: {exc}") from exc
    except httpx.ConnectError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        upstream_logger.warning(
            "[{}_CONNECT_ERR] elapsed_ms={} url={} error={}",
            log_tag,
            elapsed_ms,
            log_url,
            exc,
        )
        raise ConnectionError(f"无法连接目标站点: {exc}") from exc
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        upstream_logger.exception(
            "[{}_HTTP_ERR] elapsed_ms={} url={} error={}",
            log_tag,
            elapsed_ms,
            log_url,
            exc,
        )
        raise RuntimeError(f"请求失败: {exc}") from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    text = response.text
    upstream_logger.info(
        "[{}_RES] status={} elapsed_ms={} body_preview={}",
        log_tag,
        response.status_code,
        elapsed_ms,
        truncate_text(text, log_preview_len),
    )
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code} {response.reason_phrase}: {truncate_text(text, 160)}")
    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError("返回内容不是合法 JSON") from exc


def _decimal_to_float(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def _extract_user_self_usage_info(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("self 返回不是 JSON 对象")

    success = _is_success_flag(payload.get("success")) or _is_success_flag(payload.get("code"))
    data = extract_payload(payload)
    if isinstance(data, dict) and not success:
        success = True
    if not success or not isinstance(data, dict):
        raise RuntimeError(_pick_message(payload, "查询令牌信息失败"))

    limit_amount, usage_amount, balance, currency = extract_amount_breakdown(data)
    return {
        "tokenName": data.get("name") or data.get("username") or "",
        "unlimitedQuota": bool(data.get("unlimited_quota", data.get("unlimitedQuota", False))),
        "totalGranted": _decimal_to_float(limit_amount),
        "totalUsed": _decimal_to_float(usage_amount),
        "totalAvailable": _decimal_to_float(balance),
        "expiresAt": -1,
        "expiresAtText": "未知",
        "currency": currency or "",
    }


async def query_neko_token(
    *,
    client: httpx.AsyncClient,
    config: NekoToolConfig,
    token: str,
    base_url: str,
    variant: str,
    fetch_balance: bool | None,
    fetch_detail: bool | None,
    timeout_sec: float | None,
    cli_profile: str,
    log_preview_len: int,
) -> dict[str, Any]:
    token_value = validate_token_or_raise(token)
    resolved_base_url, base_url_source = resolve_base_url_or_raise(config, base_url)
    variant_value = (variant or "newapi").strip().lower()
    if variant_value not in {"newapi", "newapi_legacy"}:
        variant_value = "newapi"

    need_balance = config.show_balance if fetch_balance is None else bool(fetch_balance)
    need_detail = config.show_detail if fetch_detail is None else bool(fetch_detail)
    if not (need_balance or need_detail):
        raise ValueError("请至少启用一个查询项（余额信息或调用明细）")

    timeout = float(timeout_sec if timeout_sec is not None else config.timeout_sec)
    timeout = max(3.0, min(120.0, timeout))

    profile = normalize_cli_profile(cli_profile)
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token_value}"}
    headers.update(build_cli_headers(profile))

    result: dict[str, Any] = {
        "baseUrl": resolved_base_url,
        "baseUrlSource": base_url_source,
        "tokenMasked": mask_key(token_value),
        "variant": variant_value,
        "fetchBalance": need_balance,
        "fetchDetail": need_detail,
        "tokenValid": False,
        "tokenInfo": None,
        "logs": [],
        "stats": {
            "logCount": 0,
            "totalQuota": 0.0,
            "totalPromptTokens": 0,
            "totalCompletionTokens": 0,
            "models": {},
        },
        "errors": [],
        "cliProfile": profile,
    }

    if need_balance:
        try:
            if variant_value == "newapi_legacy":
                user_self_url = f"{resolved_base_url}/api/user/self"
                user_self_payload = await _get_json(
                    client=client,
                    url=user_self_url,
                    headers=headers,
                    timeout_sec=timeout,
                    log_preview_len=log_preview_len,
                    log_tag="NEKO_SELF",
                )
                result["tokenInfo"] = _extract_user_self_usage_info(user_self_payload)
            else:
                usage_url = f"{resolved_base_url}/api/usage/token"
                try:
                    usage_payload = await _get_json(
                        client=client,
                        url=usage_url,
                        headers=headers,
                        timeout_sec=timeout,
                        log_preview_len=log_preview_len,
                        log_tag="NEKO_USAGE",
                    )
                except RuntimeError as exc:
                    message = str(exc)
                    if "HTTP 404" in message or "HTTP 405" in message:
                        usage_payload = await _get_json(
                            client=client,
                            url=f"{resolved_base_url}/api/usage/token/",
                            headers=headers,
                            timeout_sec=timeout,
                            log_preview_len=log_preview_len,
                            log_tag="NEKO_USAGE",
                        )
                    else:
                        raise
                result["tokenInfo"] = _extract_usage_info(usage_payload)
            result["tokenValid"] = True
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"令牌信息查询失败: {exc}")

    if need_detail:
        try:
            if variant_value == "newapi":
                logs_url = f"{resolved_base_url}/api/log/token?key={quote(token_value)}"
                logs_masked_url = f"{resolved_base_url}/api/log/token?key={mask_key(token_value)}"
                logs_headers = {"Accept": "application/json"}
                logs_headers.update(build_cli_headers(profile))
                try:
                    logs_payload = await _get_json(
                        client=client,
                        url=logs_url,
                        url_for_log=logs_masked_url,
                        headers=logs_headers,
                        timeout_sec=timeout,
                        log_preview_len=log_preview_len,
                        log_tag="NEKO_LOG",
                    )
                except Exception:
                    logs_payload = await _get_json(
                        client=client,
                        url=f"{resolved_base_url}/api/log/token",
                        headers=headers,
                        timeout_sec=timeout,
                        log_preview_len=log_preview_len,
                        log_tag="NEKO_LOG",
                    )
            else:
                logs_url = f"{resolved_base_url}/api/log/token"
                try:
                    logs_payload = await _get_json(
                        client=client,
                        url=logs_url,
                        headers=headers,
                        timeout_sec=timeout,
                        log_preview_len=log_preview_len,
                        log_tag="NEKO_LOG",
                    )
                except Exception:
                    logs_url = f"{resolved_base_url}/api/log/token?key={quote(token_value)}"
                    logs_masked_url = f"{resolved_base_url}/api/log/token?key={mask_key(token_value)}"
                    logs_headers = {"Accept": "application/json"}
                    logs_headers.update(build_cli_headers(profile))
                    logs_payload = await _get_json(
                        client=client,
                        url=logs_url,
                        url_for_log=logs_masked_url,
                        headers=logs_headers,
                        timeout_sec=timeout,
                        log_preview_len=log_preview_len,
                        log_tag="NEKO_LOG",
                    )

            logs = _extract_logs(logs_payload)
            result["logs"] = logs
            result["stats"] = _build_stats(logs)
            result["tokenValid"] = True
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"调用明细查询失败: {exc}")

    result["ok"] = result["tokenValid"] and not result["errors"]
    if not result["tokenValid"]:
        raise RuntimeError("；".join(result["errors"]) or "查询失败，请检查 token 与 base_url")
    return result
