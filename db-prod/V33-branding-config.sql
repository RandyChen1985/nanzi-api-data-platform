-- V33: 品牌 / 版权个性化配置（系统配置 → 版权信息）
-- Date: 2026-07-01

SET NAMES utf8mb4;

INSERT IGNORE INTO sys_config (config_key, config_value, config_group, remark) VALUES
('branding.enabled', 'false', 'branding', '是否启用品牌个性化'),
('branding.product_name', 'NanZi · 数据服务平台', 'branding', '产品名称（浏览器标题、侧栏、登录页）'),
('branding.login_subtitle', 'Your API Data Platform', 'branding', '登录页副标题'),
('branding.icon_url', '/favicon.svg', 'branding', 'Logo / Favicon 地址（相对或绝对 URL）'),
('branding.hide_login_sso', 'false', 'branding', '登录页隐藏 SSO 登录'),
('branding.hide_version_link', 'false', 'branding', '侧栏版本号取消 GitHub 外链'),
('branding.contact_markdown', '', 'branding', '联系信息 Markdown（我的权限 → 联系我们）');
