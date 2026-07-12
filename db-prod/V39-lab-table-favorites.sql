-- V39: SQL Lab 用户表收藏（收藏 / 置顶 / 个人备注）
-- 幂等：可重复执行

CREATE TABLE IF NOT EXISTS lab_table_favorites (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户 ID',
    source_id INT NOT NULL COMMENT '数据源 ID',
    table_name VARCHAR(255) NOT NULL COMMENT '表名',
    is_pinned TINYINT(1) DEFAULT 0 COMMENT '是否置顶',
    note VARCHAR(500) NULL COMMENT '用户个人备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_lab_fav_user_source_table (user_id, source_id, table_name),
    INDEX idx_lab_fav_user_source (user_id, source_id),
    INDEX idx_lab_fav_pinned (user_id, source_id, is_pinned)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SQL Lab 用户表收藏';
