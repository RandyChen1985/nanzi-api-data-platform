import logging
import datetime
import asyncio
from app.core.database import get_db_connection
from app.utils.sharding import get_audit_table_name

logger = logging.getLogger(__name__)

async def aggregate_access_logs():
    """
    每 1 分钟聚合当日分表到 api_access_stats_1m
    """
    logger.info("Starting log aggregation job (1m interval)...")
    
    now = datetime.datetime.now()
    current_cycle_end = now.replace(second=0, microsecond=0)
    start_time = current_cycle_end - datetime.timedelta(minutes=1)
    end_time = current_cycle_end
    
    bucket_str = start_time.strftime('%Y-%m-%d %H:%M:00')
    
    # 动态确定表名
    table_name = get_audit_table_name(start_time)
    
    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                # 聚合 SQL (用户维度)
                sql = f"""
                    INSERT INTO api_access_stats_1m 
                    (time_bucket, user_name, endpoint, method, status_code, total_calls, total_error, avg_latency, max_latency)
                    SELECT 
                        %s as time_bucket,
                        user_name,
                        endpoint,
                        method,
                        status_code,
                        COUNT(*) as total_calls,
                        COALESCE(SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END), 0) as total_error,
                        COALESCE(AVG(process_time_ms), 0) as avg_latency,
                        COALESCE(MAX(process_time_ms), 0) as max_latency
                    FROM {table_name}
                    WHERE created_at >= %s AND created_at < %s
                    GROUP BY user_name, endpoint, method, status_code
                    ON DUPLICATE KEY UPDATE 
                        total_calls = VALUES(total_calls),
                        total_error = VALUES(total_error),
                        avg_latency = VALUES(avg_latency),
                        max_latency = VALUES(max_latency)
                """
                
                try:
                    await cursor.execute(sql, (bucket_str, start_time, end_time))
                except Exception as e:
                    if "doesn't exist" in str(e):
                        logger.info(f"Table {table_name} does not exist yet. Skipping.")
                        return
                    raise e
                
                # 全局汇总
                sql_all = f"""
                    INSERT INTO api_access_stats_1m 
                    (time_bucket, user_name, endpoint, method, status_code, total_calls, total_error, avg_latency, max_latency)
                    SELECT 
                        %s as time_bucket,
                        'ALL',
                        'ALL',
                        'ALL',
                        0,
                        COUNT(*) as total_calls,
                        COALESCE(SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END), 0) as total_error,
                        COALESCE(AVG(process_time_ms), 0) as avg_latency,
                        COALESCE(MAX(process_time_ms), 0) as max_latency
                    FROM {table_name}
                    WHERE created_at >= %s AND created_at < %s
                    ON DUPLICATE KEY UPDATE 
                        total_calls = VALUES(total_calls),
                        total_error = VALUES(total_error),
                        avg_latency = VALUES(avg_latency),
                        max_latency = VALUES(max_latency)
                """
                await cursor.execute(sql_all, (bucket_str, start_time, end_time))
                
                affected = cursor.rowcount
                logger.info(f"Log aggregation finished. Table: {table_name}, Period: {start_time} to {end_time}, Affected: {affected}")
                
    except Exception as e:
        logger.error(f"Error in aggregate_access_logs: {e}")

async def run_history_aggregation(days: int = 7, operator: str = "SYSTEM"):
    """
    回填历史数据：按小时块从分表中聚合并记录维护日志
    """
    logger.info(f"Initiating sharded history aggregation: days={days}, operator={operator}")
    start_time_exec = datetime.datetime.now()
    task_id = 0
    total_affected = 0
    
    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO sys_maintenance_log (task_name, status, start_time, operator) VALUES (%s, %s, %s, %s)",
                    ("backfill_sharded", "RUNNING", start_time_exec, operator)
                )
                task_id = cursor.lastrowid
                await conn.commit()

        now = datetime.datetime.now().replace(second=0, microsecond=0)
        start_point = (now - datetime.timedelta(days=days)).replace(minute=0, second=0)
        
        current_start = start_point
        while current_start < now:
            current_end = current_start + datetime.timedelta(hours=1)
            if current_end > now:
                current_end = now
                
            # 动态获取分表名
            table_name = get_audit_table_name(current_start)
            logger.info(f"📊 Aggregating chunk: {current_start} to {current_end} from {table_name}...")
            
            async with get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    # 1. 检查表是否存在
                    await cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                    if not await cursor.fetchone():
                        logger.warning(f"Table {table_name} not found, skipping chunk.")
                        current_start = current_end
                        continue

                    # 2. 聚合当日分表数据 (用户维度)
                    sql = f"""
                        INSERT INTO api_access_stats_1m 
                        (time_bucket, user_name, endpoint, method, status_code, total_calls, total_error, avg_latency, max_latency)
                        SELECT 
                            DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:00') as bucket,
                            user_name,
                            endpoint,
                            method,
                            status_code,
                            COUNT(*) as total_calls,
                            COALESCE(SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END), 0) as total_error,
                            COALESCE(AVG(process_time_ms), 0) as avg_latency,
                            COALESCE(MAX(process_time_ms), 0) as max_latency
                        FROM {table_name}
                        WHERE created_at >= %s AND created_at < %s
                        GROUP BY bucket, user_name, endpoint, method, status_code
                        ON DUPLICATE KEY UPDATE 
                            total_calls = VALUES(total_calls),
                            total_error = VALUES(total_error),
                            avg_latency = VALUES(avg_latency),
                            max_latency = VALUES(max_latency)
                    """
                    await cursor.execute(sql, (current_start, current_end))
                    total_affected += cursor.rowcount
                    
                    # 3. 全局汇总
                    sql_all = f"""
                        INSERT INTO api_access_stats_1m 
                        (time_bucket, user_name, endpoint, method, status_code, total_calls, total_error, avg_latency, max_latency)
                        SELECT 
                            DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:00') as bucket,
                            'ALL',
                            'ALL',
                            'ALL',
                            0,
                            COUNT(*) as total_calls,
                            COALESCE(SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END), 0) as total_error,
                            COALESCE(AVG(process_time_ms), 0) as avg_latency,
                            COALESCE(MAX(process_time_ms), 0) as max_latency
                        FROM {table_name}
                        WHERE created_at >= %s AND created_at < %s
                        GROUP BY bucket
                        ON DUPLICATE KEY UPDATE 
                            total_calls = VALUES(total_calls),
                            total_error = VALUES(total_error),
                            avg_latency = VALUES(avg_latency),
                            max_latency = VALUES(max_latency)
                    """
                    await cursor.execute(sql_all, (current_start, current_end))
                    total_affected += cursor.rowcount
                    await conn.commit()
            
            current_start = current_end
            await asyncio.sleep(0.1)

        # 更新任务成功状态
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE sys_maintenance_log SET status = 'SUCCESS', end_time = %s, affected_rows = %s WHERE id = %s",
                    (datetime.datetime.now(), total_affected, task_id)
                )
                await conn.commit()
        logger.info("✅ History aggregation from sharded tables completed.")

    except Exception as e:
        logger.error(f"Error in run_history_aggregation (sharded): {e}")
        if task_id > 0:
            try:
                async with get_db_connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE sys_maintenance_log SET status = 'FAILED', error_message = %s WHERE id = %s",
                            (str(e), task_id)
                        )
                        await conn.commit()
            except Exception as inner_e:
                logger.error(f"Failed to record failure status: {inner_e}")
