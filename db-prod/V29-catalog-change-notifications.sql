-- V29: 目录/API 变更通知
-- Date: 2026-07-01
-- Description: 关联 API 资源配置变更时，向数据产品负责人写入站内通知；可选 Webhook。

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `data_product_change_notifications` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` BIGINT NOT NULL COMMENT '接收人 api_users.id',
  `product_id` BIGINT NOT NULL COMMENT 'data_products.id',
  `product_key` VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '产品标识',
  `product_display_name` VARCHAR(200) NOT NULL COMMENT '产品展示名（快照）',
  `resource_key` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '变更的 API 资源',
  `resource_name` VARCHAR(200) DEFAULT NULL COMMENT '资源名称（快照）',
  `version_id` BIGINT DEFAULT NULL COMMENT 'sys_resource_meta_versions.id',
  `action_type` VARCHAR(32) NOT NULL COMMENT 'UPDATE / ROLLBACK',
  `change_summary` VARCHAR(500) DEFAULT NULL COMMENT '变更摘要',
  `operator_user_id` BIGINT DEFAULT NULL COMMENT '操作人用户 ID',
  `operator_name` VARCHAR(64) DEFAULT NULL COMMENT '操作人用户名',
  `is_read` TINYINT NOT NULL DEFAULT 0 COMMENT '0 未读 1 已读',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '通知时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_read_created` (`user_id`, `is_read`, `created_at`),
  KEY `idx_product_id` (`product_id`),
  KEY `idx_resource_key` (`resource_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据产品关联 API 变更通知';

INSERT IGNORE INTO sys_config (config_key, config_value, config_group, remark) VALUES
('catalog.notify_resource_change.enabled', 'true', 'catalog', '资源变更时通知关联产品负责人'),
('catalog.notify_resource_change.webhook_url', '', 'catalog', '可选 Webhook URL（POST JSON，留空则不推送）');
