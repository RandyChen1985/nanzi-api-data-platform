-- V40: 品牌重命名 云枢/Yunshu → NanZi（幂等更新默认品牌文案）
-- Date: 2026-07-17
-- Note: 仅覆盖仍为旧默认值的配置；已自定义的 branding 文案不受影响。

SET NAMES utf8mb4;

UPDATE sys_config
SET config_value = 'NanZi · 数据服务平台'
WHERE config_key = 'branding.product_name'
  AND config_value IN (
    '云枢 · 数据服务平台',
    'Yunshu · 数据服务平台',
    '南孜 · 数据服务平台',
    '南孜·数据服务平台'
  );

UPDATE sys_config
SET config_value = 'NanZi API Data Platform'
WHERE config_key = 'branding.login_subtitle'
  AND config_value IN ('Yunshu API Data Platform');

-- MCP 默认 instructions（若仍为旧文案则更新）
UPDATE sys_config
SET config_value = '南孜数据平台 MCP：先调用 nanzi_list_resources 查看可访问资源，nanzi_search_metadata 检索表/指标元数据，nanzi_query_resource 按资源 Key 查询数据。'
WHERE config_key = 'mcp.server.instructions'
  AND (
    config_value LIKE '%云枢%'
    OR config_value LIKE '%yunshu_list_resources%'
    OR config_value LIKE '%Yunshu%'
  );
