-- V30: 钉钉审批通知配置
-- Date: 2026-07-01
-- Description: 目录权限申请/审批结果推送钉钉机器人。

SET NAMES utf8mb4;

INSERT IGNORE INTO sys_config (config_key, config_value, config_group, remark) VALUES
('notify.dingtalk.enabled', 'false', 'notify', '启用钉钉机器人通知'),
('notify.dingtalk.webhook_url', '', 'notify', '钉钉自定义机器人 Webhook 地址'),
('notify.dingtalk.secret', '', 'notify', '钉钉机器人加签密钥（可选）'),
('notify.dingtalk.on_request', 'true', 'notify', '新权限申请时推送'),
('notify.dingtalk.on_result', 'true', 'notify', '审批通过/拒绝时推送');
