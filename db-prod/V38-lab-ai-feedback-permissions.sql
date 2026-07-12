-- V38: SQL Lab AI 反馈管理页权限
SET NAMES utf8mb4;

INSERT IGNORE INTO sys_ui_permissions (perm_type, perm_code) VALUES
('menu', 'menu:lab:feedback'),
('element', 'element:lab:feedback:manage');

-- 管理员默认拥有菜单与「查看全部用户反馈」
INSERT IGNORE INTO sys_ui_permissions (role_id, perm_type, perm_code, enabled)
SELECT r.id, 'menu', 'menu:lab:feedback', 1
FROM sys_roles r
WHERE r.role_code = 'admin';

INSERT IGNORE INTO sys_ui_permissions (role_id, perm_type, perm_code, enabled)
SELECT r.id, 'element', 'element:lab:feedback:manage', 1
FROM sys_roles r
WHERE r.role_code = 'admin';
