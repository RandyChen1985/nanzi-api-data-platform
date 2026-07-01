-- V32: MCP 平台对外地址（供 SSE URL 展示与 stdio 客户端自动发现）
-- Date: 2026-07-01

SET NAMES utf8mb4;

INSERT IGNORE INTO sys_config (config_key, config_value, config_group, remark) VALUES
('mcp.server.public_base_url', '', 'mcp', '平台对外 Base URL，如 https://data.example.com（勿带末尾斜杠）');
