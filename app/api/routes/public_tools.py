from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.api.schemas.toolbox import ApiTestRequest, NekoQueryRequest, ParseRequest
from app.core.config import get_settings
from app.services.public_tool_service import (
    CHANNELS,
    build_neko_tool_config,
    build_parser_llm_config,
    build_ui_config_payload,
    call_provider,
    extract_text_from_response,
    mask_key,
    normalize_base_url,
    normalize_cli_profile,
    parse_by_rules,
    query_neko_token,
    resolve_default_cli_profile,
    safe_extract_json,
    SlidingWindowRateLimiter,
)

router = APIRouter()
settings = get_settings()
rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.api_tool_rate_limit_per_minute,
    window_sec=60,
)


def _check_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail=(
                "请求过于频繁，请稍后再试"
                f"（限制：{settings.api_tool_rate_limit_per_minute}次/分钟）。"
            ),
        )


def _get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def _handle_provider_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, TimeoutError):
        return HTTPException(status_code=504, detail=str(exc))
    if isinstance(exc, ConnectionError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/config")
async def config_endpoint() -> dict[str, Any]:
    parser_config = build_parser_llm_config(settings)
    neko_config = build_neko_tool_config(settings)
    return {
        "ok": True,
        **build_ui_config_payload(settings),
        "defaultCliProfile": resolve_default_cli_profile(settings),
        "cliProfiles": ["default", "cc", "codex", "geminicli"],
        "llmParser": {
            "enabled": parser_config.enabled,
            "channel": parser_config.channel,
            "baseUrl": parser_config.base_url,
            "model": parser_config.model,
            "cliProfile": parser_config.cli_profile,
        },
        "nekoTool": neko_config.to_client_payload(),
    }


@router.post("/parse/rule")
async def parse_rule(req: ParseRequest) -> dict[str, Any]:
    parsed = parse_by_rules(req.raw_text)
    return {"ok": True, "source": "rule", "data": parsed}


@router.post("/parse/llm")
async def parse_llm(request: Request, req: ParseRequest) -> dict[str, Any]:
    _check_rate_limit(request)
    parser_config = build_parser_llm_config(settings)
    try:
        parser_config.validate_or_raise()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    prompt = "\n".join(
        [
            "你是配置解析器。",
            "请从用户输入文本中提取 API 参数，并且仅返回 JSON。",
            "JSON 字段固定为：channel, baseUrl, apiKey, model。",
            "channel 允许值：openai_chat, openai_responses, gemini, claude。",
            "无法确定的字段填空字符串。",
            "",
            req.raw_text,
        ]
    )

    try:
        call_result = await call_provider(
            client=_get_http_client(request),
            channel=parser_config.channel,
            base_url=parser_config.base_url,
            api_key=parser_config.api_key,
            model=parser_config.model,
            prompt=prompt,
            timeout_sec=parser_config.timeout_sec,
            cli_profile=parser_config.cli_profile,
            log_preview_len=settings.log_preview_len,
        )
    except (ValueError, TimeoutError, ConnectionError, RuntimeError) as exc:
        raise _handle_provider_error(exc) from exc

    llm_text = extract_text_from_response(parser_config.channel, call_result["response"])
    llm_json = safe_extract_json(llm_text) if llm_text else None
    if not isinstance(llm_json, dict):
        fallback = parse_by_rules(req.raw_text)
        return {
            "ok": True,
            "source": "llm_fallback_rule",
            "note": "LLM 返回不是可解析 JSON，已自动回退到规则解析。",
            "data": fallback,
        }

    parsed = {
        "channel": llm_json.get("channel", ""),
        "baseUrl": llm_json.get("baseUrl", ""),
        "apiKey": llm_json.get("apiKey", ""),
        "model": llm_json.get("model", ""),
    }
    if parsed["channel"] not in CHANNELS:
        parsed["channel"] = ""
    return {"ok": True, "source": "llm", "data": parsed}


@router.post("/test")
async def test_api(request: Request, req: ApiTestRequest) -> dict[str, Any]:
    _check_rate_limit(request)

    cli_profile = normalize_cli_profile(req.cli_profile)
    if cli_profile == "default":
        cli_profile = resolve_default_cli_profile(settings)

    started = time.perf_counter()
    try:
        result = await call_provider(
            client=_get_http_client(request),
            channel=req.channel,
            base_url=req.base_url,
            api_key=req.api_key,
            model=req.model,
            prompt=req.prompt,
            timeout_sec=req.timeout_sec,
            cli_profile=cli_profile,
            log_preview_len=settings.log_preview_len,
        )
    except (ValueError, TimeoutError, ConnectionError, RuntimeError) as exc:
        raise _handle_provider_error(exc) from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "ok": 200 <= result["status"] < 300,
        "channel": req.channel,
        "model": req.model,
        "baseUrl": normalize_base_url(req.base_url),
        "apiKeyMasked": mask_key(req.api_key),
        "elapsedMs": elapsed_ms,
        "status": result["status"],
        "statusText": result["status_text"],
        "requestUrl": result["request_url_masked"],
        "cliProfile": cli_profile,
        "response": result["response"],
    }


@router.post("/neko/query")
async def neko_query(request: Request, req: NekoQueryRequest) -> dict[str, Any]:
    _check_rate_limit(request)
    cli_profile = resolve_default_cli_profile(settings)
    neko_config = build_neko_tool_config(settings)
    try:
        return await query_neko_token(
            client=_get_http_client(request),
            config=neko_config,
            token=req.token,
            base_url=req.base_url,
            variant=req.variant,
            fetch_balance=req.fetch_balance,
            fetch_detail=req.fetch_detail,
            timeout_sec=req.timeout_sec,
            cli_profile=cli_profile,
            log_preview_len=settings.log_preview_len,
        )
    except (ValueError, TimeoutError, ConnectionError, RuntimeError) as exc:
        raise _handle_provider_error(exc) from exc
