"""MCP SSE API Key 上下文测试"""

from yunshu_mcp.auth_context import (
    bind_session_api_key,
    extract_api_key_from_scope,
    extract_session_id_from_scope,
    get_mcp_api_key,
    lookup_session_api_key,
    reset_mcp_api_key,
    resolve_api_key_for_scope,
    set_mcp_api_key,
)


def _scope(headers=None, query_string=b""):
    return {
        "type": "http",
        "headers": headers or [],
        "query_string": query_string,
    }


def test_extract_api_key_from_scope():
    scope = _scope(headers=[(b"x-api-key", b"sk-test-123")])
    assert extract_api_key_from_scope(scope) == "sk-test-123"


def test_extract_session_id_from_scope():
    scope = _scope(query_string=b"session_id=abc123")
    assert extract_session_id_from_scope(scope) == "abc123"


def test_session_api_key_binding():
    bind_session_api_key("sess-1", "sk-bound")
    assert lookup_session_api_key("sess-1") == "sk-bound"


def test_resolve_api_key_prefers_header_then_session():
    scope = _scope(
        headers=[(b"X-API-Key", b"sk-header")],
        query_string=b"session_id=sess-2",
    )
    assert resolve_api_key_for_scope(scope) == "sk-header"
    assert lookup_session_api_key("sess-2") == "sk-header"

    scope_post = _scope(query_string=b"session_id=sess-2")
    assert resolve_api_key_for_scope(scope_post) == "sk-header"


def test_contextvar_api_key(monkeypatch):
    monkeypatch.delenv("YUNSHU_API_KEY", raising=False)
    token = set_mcp_api_key("sk-ctx")
    try:
        assert get_mcp_api_key() == "sk-ctx"
    finally:
        reset_mcp_api_key(token)


def test_env_fallback_when_no_context(monkeypatch):
    monkeypatch.setenv("YUNSHU_API_KEY", "sk-env")
    assert get_mcp_api_key() == "sk-env"
