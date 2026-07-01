-- V28: 资源配置版本历史
-- Date: 2026-07-01
-- Description: 记录 sys_resource_meta 变更快照，支持版本对比与回滚。

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `sys_resource_meta_versions` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  `resource_key` VARCHAR(100) NOT NULL COMMENT '资源标识',
  `version_no` INT NOT NULL COMMENT '该资源下的顺序版本号',
  `action_type` VARCHAR(32) NOT NULL DEFAULT 'UPDATE' COMMENT '操作类型：CREATE / UPDATE / ROLLBACK',
  `snapshot` JSON NOT NULL COMMENT '完整可变配置快照',
  `change_summary` VARCHAR(500) DEFAULT NULL COMMENT '变更字段摘要',
  `operator_user_id` BIGINT DEFAULT NULL COMMENT '操作人用户 ID',
  `operator_name` VARCHAR(64) DEFAULT NULL COMMENT '操作人用户名',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '版本创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_resource_version` (`resource_key`, `version_no`),
  KEY `idx_resource_key_created` (`resource_key`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API 资源配置版本历史';
