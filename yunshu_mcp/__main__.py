"""python -m yunshu_mcp — stdio 模式启动云枢 MCP Server（供 Cursor / Claude Desktop 使用）。"""

import asyncio
import os
import sys


async def _main() -> None:
    if not os.getenv("YUNSHU_API_KEY"):
        print(
            "错误: 请设置环境变量 YUNSHU_API_KEY（云枢数据平台 API Key）",
            file=sys.stderr,
        )
        sys.exit(1)

    from yunshu_mcp.client import YunshuApiClient
    from yunshu_mcp.server import create_mcp_server_from_db, ensure_mcp_enabled

    try:
        status = await YunshuApiClient().mcp_status()
        if not status.get("enabled"):
            print(status.get("message") or "MCP Server 未启用", file=sys.stderr)
            sys.exit(1)
    except Exception as exc:
        print(f"无法连接数据平台检查 MCP 状态: {exc}", file=sys.stderr)
        sys.exit(1)

    await ensure_mcp_enabled()
    mcp = await create_mcp_server_from_db()
    await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(_main())
