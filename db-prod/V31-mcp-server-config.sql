-- V31: MCP Server 开关与接入配置
-- Date: 2026-07-01
-- Description: 控制数据平台 MCP Server（SSE）是否对外提供，及接入说明类配置。

SET NAMES utf8mb4;

INSERT IGNORE INTO sys_config (config_key, config_value, config_group, remark) VALUES
('mcp.server.enabled', 'false', 'mcp', '是否启用 MCP Server（SSE 端点 /mcp/sse）'),
('mcp.server.instructions', '云枢数据平台 MCP：先 list_resources 查看可访问资源，search_metadata 检索元数据，query_resource 查询数据。', 'mcp', 'MCP 会话 instructions 提示文案');
