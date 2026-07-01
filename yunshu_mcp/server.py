"""FastMCP 工具定义与 Server 实例。"""

from __future__ import annotations

import os
from typing import Any, List, Optional

from mcp.server.fastmcp import FastMCP

from yunshu_mcp.client import YunshuApiClient, YunshuApiError, dumps_json
from yunshu_mcp.auth_context import get_mcp_api_key

_mcp_instance: Optional[FastMCP] = None


async def ensure_mcp_enabled() -> None:
    try:
        from app.services.mcp_settings_service import McpSettingsService

        if not await McpSettingsService.is_enabled():
            raise RuntimeError("MCP Server 未启用，请在管理后台「系统配置 → MCP 服务」中开启")
    except ImportError:
        client = YunshuApiClient()
        status = await client.mcp_status()
        if not status.get("enabled"):
            raise RuntimeError(status.get("message") or "MCP Server 未启用")


def _client() -> YunshuApiClient:
    return YunshuApiClient(api_key=get_mcp_api_key() or None)


def create_mcp_server(instructions: Optional[str] = None) -> FastMCP:
    global _mcp_instance
    if _mcp_instance is not None:
        return _mcp_instance

    default_instructions = (
        "云枢数据平台：使用 yunshu_list_resources 发现资源，"
        "yunshu_search_metadata 检索元数据，yunshu_query_resource 查询数据。"
    )
    mcp = FastMCP("yunshu-data", instructions=instructions or default_instructions)

    @mcp.tool()
    async def yunshu_list_resources() -> str:
        """列出当前 API Key 可访问的数据 API 资源（resource_key、名称、分组、可筛选字段）。"""
        await ensure_mcp_enabled()
        try:
            data = await _client().list_resources()
            return dumps_json(data)
        except YunshuApiError as exc:
            return f"错误: {exc}"

    @mcp.tool()
    async def yunshu_query_resource(
        resource: str,
        filters_json: str = "[]",
        page: int = 1,
        size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
    ) -> str:
        """
        按资源 Key 查询数据（POST /api/v1/query）。
        filters_json 为 JSON 数组，如 [["status","=","1"]]
        """
        await ensure_mcp_enabled()
        import json

        try:
            filters: List[Any] = json.loads(filters_json) if filters_json else []
        except json.JSONDecodeError as exc:
            return f"filters_json 解析失败: {exc}"
        try:
            data = await _client().query_resource(
                resource=resource,
                filters=filters,
                page=page,
                size=size,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            return dumps_json(data)
        except YunshuApiError as exc:
            return f"错误: {exc}"

    @mcp.tool()
    async def yunshu_search_metadata(
        query: str,
        data_source: str = "default",
        search_type: str = "keyword",
        enable_rerank: bool = False,
    ) -> str:
        """
        检索元数据（表/指标 YAML 上下文）。需要 system.metadata.search 资源权限。
        search_type: keyword | semantic
        """
        await ensure_mcp_enabled()
        try:
            data = await _client().search_metadata(
                query=query,
                data_source=data_source,
                search_type=search_type,
                enable_rerank=enable_rerank,
            )
            return dumps_json(data)
        except YunshuApiError as exc:
            return f"错误: {exc}"

    _mcp_instance = mcp
    return mcp


async def create_mcp_server_from_db() -> FastMCP:
    instructions = os.getenv("MCP_INSTRUCTIONS")
    try:
        from app.services.mcp_settings_service import McpSettingsService

        settings = await McpSettingsService.get_settings()
        instructions = settings.get("instructions") or instructions
    except Exception:
        pass
    return create_mcp_server(instructions=instructions)


def get_mcp_server() -> FastMCP:
    return create_mcp_server()
