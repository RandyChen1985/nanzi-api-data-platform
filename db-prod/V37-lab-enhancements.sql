-- V37: SQL Lab 增强功能表（保存查询、异步导出、AI 反馈、分析会话）
-- 幂等：可重复执行

CREATE TABLE IF NOT EXISTS lab_saved_queries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '创建人',
    name VARCHAR(200) NOT NULL COMMENT '查询名称',
    sql_text MEDIUMTEXT NOT NULL COMMENT 'SQL 内容',
    source_id INT NOT NULL COMMENT '数据源 ID',
    lab_mode VARCHAR(20) DEFAULT 'analyst' COMMENT 'api / analyst',
    test_params JSON NULL COMMENT '测试参数 JSON',
    tags JSON NULL COMMENT '标签',
    is_shared TINYINT(1) DEFAULT 0 COMMENT '是否团队共享',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_lab_saved_user (user_id),
    INDEX idx_lab_saved_source (source_id),
    INDEX idx_lab_saved_shared (is_shared)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SQL Lab 保存查询';

CREATE TABLE IF NOT EXISTS lab_export_jobs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    source_id INT NOT NULL,
    sql_text MEDIUMTEXT NOT NULL,
    params JSON NULL,
    format VARCHAR(10) DEFAULT 'xlsx' COMMENT 'xlsx / csv',
    status TINYINT DEFAULT 0 COMMENT '0=pending 1=running 2=done 3=failed',
    row_count INT DEFAULT 0,
    file_path VARCHAR(500) NULL,
    error_message TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    INDEX idx_lab_export_user (user_id),
    INDEX idx_lab_export_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SQL Lab 异步导出任务';

CREATE TABLE IF NOT EXISTS lab_ai_feedback (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    source_id INT NULL,
    prompt TEXT NULL,
    generated_sql MEDIUMTEXT NULL,
    rating TINYINT NOT NULL COMMENT '1=踩 2=赞',
    execution_success TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lab_feedback_user (user_id),
    INDEX idx_lab_feedback_rating (rating)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SQL Lab AI 生成反馈';

CREATE TABLE IF NOT EXISTS lab_analysis_sessions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    sql_text MEDIUMTEXT NULL,
    columns_json JSON NULL,
    messages_json JSON NOT NULL COMMENT '对话记录',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lab_analysis_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SQL Lab AI 分析会话存档';
