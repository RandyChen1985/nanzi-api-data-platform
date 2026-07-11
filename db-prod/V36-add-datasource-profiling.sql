-- 原因：为数据源管理模块新增数据库摸排任务管理及表/视图画像草稿库。
-- 需求背景：一个数据源同一时间只能运行一个摸排任务；需要保存串行处理的进度供前端高频轮询；不与元数据表关联。
-- 创建人：Antigravity
-- 创建时间：2026-07-11

CREATE TABLE IF NOT EXISTS `db_profile_tasks` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `connection_id` BIGINT(20) NOT NULL COMMENT '关联外部数据源连接配置ID',
  `status` TINYINT NOT NULL DEFAULT 0 COMMENT '任务状态: 0-排队中, 1-进行中, 2-完成, 3-异常中断',
  `total_tables` INT NOT NULL DEFAULT 0 COMMENT '总表/视图数',
  `processed_tables` INT NOT NULL DEFAULT 0 COMMENT '已处理表/视图数',
  `current_table` VARCHAR(100) DEFAULT NULL COMMENT '当前正在处理的物理表名',
  `error_message` TEXT DEFAULT NULL COMMENT '异常中断的说明',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_conn_task` (`connection_id`),
  CONSTRAINT `fk_task_conn` FOREIGN KEY (`connection_id`) REFERENCES `sys_data_source` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `db_table_profiles` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `connection_id` BIGINT(20) NOT NULL COMMENT '关联外部数据源连接配置ID',
  `table_name` VARCHAR(100) NOT NULL COMMENT '数据库物理表/视图名',
  `table_type` VARCHAR(20) NOT NULL COMMENT '对象物理类型: table|view',
  `engine` VARCHAR(50) DEFAULT NULL COMMENT '存储引擎',
  `ddl` TEXT DEFAULT NULL COMMENT '物理建表 DDL',
  `sample_data` TEXT DEFAULT NULL COMMENT '3条采样数据样例(JSON格式)',
  `ai_term` VARCHAR(100) DEFAULT NULL COMMENT 'AI识别的中文备注名/术语',
  `ai_description` VARCHAR(500) DEFAULT NULL COMMENT 'AI分析的真实用途描述',
  `ai_tags` JSON DEFAULT NULL COMMENT 'AI生成的分类标签数组',
  `columns_profile` JSON DEFAULT NULL COMMENT 'AI生成的字段描述画像(JSON数组)',
  `status` TINYINT DEFAULT 0 COMMENT '摸排状态: 0-待开始, 1-摸排中, 2-摸排成功, 3-摸排失败',
  `error_message` TEXT DEFAULT NULL COMMENT '分析失败时的异常说明',
  `confidence_score` SMALLINT NOT NULL DEFAULT 100 COMMENT '置信度/业务相关度评分(0-100)',
  `is_temporary` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否为临时/备份表',
  `is_ignored` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '分析中是否忽略该表',
  `confidence_reason` TEXT DEFAULT NULL COMMENT '置信度判定与扣分原因',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_conn_table` (`connection_id`, `table_name`),
  CONSTRAINT `fk_profile_conn` FOREIGN KEY (`connection_id`) REFERENCES `sys_data_source` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
