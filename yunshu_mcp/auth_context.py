"""MCP 请求级 API Key 上下文（SSE 模式从 HTTP 头传入，stdio 走环境变量）。"""

from __future__ import annotations

import os
from contextvars import ContextVar, Token
from typing import Dict, Optional
from urllib.parse import parse_qs

_mcp_api_key_ctx: ContextVar[Optional[str]] = ContextVar("mcp_api_key", default=None)
_session_api_keys: Dict[str, str] = {}


def get_mcp_api_key() -> str:
    key = _mcp_api_key_ctx.get()
    if key:
        return key
    return (os.getenv("YUNSHU_API_KEY") or "").strip()


def bind_session_api_key(session_id: str, api_key: str) -> None:
    if session_id and api_key:
        _session_api_keys[session_id] = api_key


def lookup_session_api_key(session_id: str) -> str:
    return (_session_api_keys.get(session_id) or "").strip()


def set_mcp_api_key(api_key: Optional[str]) -> Optional[Token]:
    if api_key:
        return _mcp_api_key_ctx.set(api_key)
    return None


def reset_mcp_api_key(token: Optional[Token]) -> None:
    if token is not None:
        _mcp_api_key_ctx.reset(token)


def extract_api_key_from_scope(scope: dict) -> str:
    for name, value in scope.get("headers") or []:
        if name.lower() == b"x-api-key":
            return value.decode("utf-8", errors="ignore").strip()
    return ""


def extract_session_id_from_scope(scope: dict) -> str:
    query = (scope.get("query_string") or b"").decode("utf-8", errors="ignore")
    if not query:
        return ""
    return (parse_qs(query).get("session_id") or [""])[0].strip()


def resolve_api_key_for_scope(scope: dict) -> str:
    """从请求头或已绑定的 SSE session 解析 API Key。"""
    key = extract_api_key_from_scope(scope)
    session_id = extract_session_id_from_scope(scope)
    if key and session_id:
        bind_session_api_key(session_id, key)
        return key
    if session_id:
        return lookup_session_api_key(session_id)
    return key
