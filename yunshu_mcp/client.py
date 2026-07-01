"""云枢数据平台 MCP Server — 将 /api/v1 能力暴露为 MCP Tools。"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


from yunshu_mcp.auth_context import get_mcp_api_key


class YunshuApiError(Exception):
    pass


class YunshuApiClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or os.getenv("YUNSHU_BASE_URL") or "").rstrip("/")
        self.api_key = (api_key or get_mcp_api_key() or "").strip()

    async def resolve_base_url(self) -> str:
        """优先环境变量，否则从 /mcp/status 读取当前请求的访问根地址。"""
        if self.base_url:
            return self.base_url
        status = await self.mcp_status()
        url = (status.get("public_base_url") or "").strip().rstrip("/")
        if url:
            self.base_url = url
            return url
        return DEFAULT_BASE_URL

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise YunshuApiError(
                "未配置 API Key：SSE 请在 Cursor MCP 的 headers 中设置 X-API-Key；"
                "stdio 请在 env 中设置 YUNSHU_API_KEY（使用您个人的 API Key）"
            )
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    async def _parse(self, resp: httpx.Response) -> Any:
        try:
            body = resp.json()
        except Exception as exc:
            raise YunshuApiError(f"非 JSON 响应 ({resp.status_code}): {resp.text[:200]}") from exc
        if resp.status_code >= 400:
            raise YunshuApiError(body.get("message") or body.get("detail") or resp.text)
        code = body.get("code")
        if code is not None and int(code) != 200:
            raise YunshuApiError(body.get("message") or f"业务错误 code={code}")
        return body.get("data")

    async def mcp_status(self) -> Dict[str, Any]:
        base = self.base_url or DEFAULT_BASE_URL
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{base}/api/v1/mcp/status")
            resp.raise_for_status()
            return resp.json()

    async def list_resources(self) -> Dict[str, Any]:
        base = await self.resolve_base_url()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                f"{base}/api/v1/resources",
                headers=self._headers(),
            )
            return await self._parse(resp)

    async def query_resource(
        self,
        resource: str,
        filters: Optional[List[Any]] = None,
        page: int = 1,
        size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "resource": resource,
            "filters": filters or [],
            "page": page,
            "size": size,
            "sort_order": sort_order,
        }
        if sort_by:
            payload["sort_by"] = sort_by
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{await self.resolve_base_url()}/api/v1/query/",
                headers=self._headers(),
                json=payload,
            )
            return await self._parse(resp)

    async def search_metadata(
        self,
        query: str,
        data_source: str = "default",
        search_type: str = "keyword",
        enable_rerank: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "query": query,
            "data_source": data_source,
            "search_type": search_type,
            "enable_rerank": enable_rerank,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{await self.resolve_base_url()}/api/v1/meta/search",
                headers=self._headers(),
                json=payload,
            )
            return await self._parse(resp)


def dumps_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)
