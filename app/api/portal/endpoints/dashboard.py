"""
Dashboard API endpoints for statistics and overview data.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.dependencies import require_api_key, require_admin
from app.core.database import get_db_connection
from app.core.redis import get_redis
from datetime import datetime, timedelta
from typing import Optional, List
import json
import logging
from app.services.meta_service import MetaService
from app.schemas.resource import ResourceResponse
from app.utils.sharding import get_audit_table_name

router = APIRouter()
logger = logging.getLogger(__name__)


def is_admin(user: dict) -> bool:
    """Check if user is admin"""
    return user.get("role") == "admin"


@router.get("/admin-stats")
async def get_admin_stats(
    period: str = Query("today", pattern="^(today|week|month)$"),
    user: dict = Depends(require_api_key)
):
    """
    Get dashboard statistics using AGGREGATION table for performance.
    """
    admin_flag = is_admin(user)
    user_name = user["user_name"]
    
    # --- Cache Check ---
    redis = await get_redis()
    cache_key = None
    if redis:
        role_part = "admin" if admin_flag else f"user:{user_name}"
        cache_key = f"dashboard:stats:{role_part}:{period}"
        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("Redis read error: %s", e)
    # -------------------
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Get total users (admin only)
            if admin_flag:
                await cursor.execute("SELECT COUNT(*) FROM api_users WHERE status = 1")
                total_users = (await cursor.fetchone())[0]
                
                # Get active users (last 7 days, admin only)
                seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                await cursor.execute("""
                    SELECT COUNT(DISTINCT user_name) 
                    FROM api_access_stats_1m 
                    WHERE time_bucket >= %s AND user_name != 'ALL'
                """, (seven_days_ago,))
                active_users = (await cursor.fetchone())[0]
            else:
                total_users = None
                active_users = None
            
            # Determine time range
            if period == "today":
                start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                start_time = datetime.now() - timedelta(days=7)
            else:  # month
                start_time = datetime.now() - timedelta(days=30)
            
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Get API call statistics
            if admin_flag:
                await cursor.execute("""
                    SELECT 
                        SUM(total_calls) as total_calls,
                        SUM(total_calls * avg_latency) / NULLIF(SUM(total_calls), 0) as weighted_avg_time,
                        SUM(total_error) as error_count
                    FROM api_access_stats_1m
                    WHERE time_bucket >= %s AND user_name = 'ALL'
                """, (start_time_str,))
            else:
                await cursor.execute("""
                    SELECT 
                        SUM(total_calls) as total_calls,
                        SUM(total_calls * avg_latency) / NULLIF(SUM(total_calls), 0) as weighted_avg_time,
                        SUM(total_error) as error_count
                    FROM api_access_stats_1m
                    WHERE time_bucket >= %s AND user_name = %s
                """, (start_time_str, user_name))
            
            stats_row = await cursor.fetchone()
            total_calls = int(stats_row[0]) if stats_row[0] else 0
            avg_time = float(stats_row[1]) if stats_row[1] else 0
            error_count = int(stats_row[2]) if stats_row[2] else 0
            success_count = total_calls - error_count
            
            result = {
                "api_calls": {
                    "period": period,
                    "total": total_calls,
                    "success": success_count,
                    "errors": error_count
                },
                "avg_response_time": round(avg_time, 2),
                "success_rate": round((success_count / total_calls * 100), 2) if total_calls > 0 else 0,
                "error_rate": round((error_count / total_calls * 100), 2) if total_calls > 0 else 0
            }
            
            if admin_flag:
                result["total_users"] = total_users
                result["active_users"] = active_users
            
            if redis and cache_key:
                await redis.setex(cache_key, 300, json.dumps(result))
            
            return result


@router.get("/user-stats")
async def get_user_stats(
    period: str = Query("today", pattern="^(today|week|month)$"),
    user: dict = Depends(require_api_key)
):
    """
    Get user dashboard statistics.
    Returns personal API usage statistics.
    """
    user_name = user["user_name"]
    
    # --- Cache Check ---
    redis = await get_redis()
    cache_key = None
    if redis:
        cache_key = f"dashboard:user-stats:{user_name}:{period}"
        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("Redis read error: %s", e)
    # -------------------

    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Get API key status
            await cursor.execute("""
                SELECT status FROM api_users 
                WHERE user_name = %s
            """, (user_name,))
            user_row = await cursor.fetchone()
            api_key_status = "active" if (user_row and user_row[0] == 1) else "inactive"
            
            # Determine time range
            if period == "today":
                start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                start_time = datetime.now() - timedelta(days=7)
            else:  # month
                start_time = datetime.now() - timedelta(days=30)
            
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Get personal statistics using AGGREGATION table
            await cursor.execute("""
                SELECT 
                    SUM(total_calls) as total_calls,
                    SUM(total_calls * avg_latency) / NULLIF(SUM(total_calls), 0) as avg_time,
                    SUM(total_calls - total_error) as success_count,
                    MAX(time_bucket) as last_call
                FROM api_access_stats_1m
                WHERE user_name = %s AND time_bucket >= %s
            """, (user_name, start_time_str))
            
            stats_row = await cursor.fetchone()
            total_calls = int(stats_row[0]) if stats_row[0] else 0
            avg_time = float(stats_row[1]) if stats_row[1] else 0
            success_count = int(stats_row[2]) if stats_row[2] else 0
            last_call = stats_row[3]
            
            success_rate = (success_count / total_calls * 100) if total_calls > 0 else 0
            
            result = {
                "api_key_status": api_key_status,
                "api_calls": {
                    "period": period,
                    "total": total_calls,
                    "success": success_count
                },
                "avg_response_time": round(avg_time, 2),
                "success_rate": round(success_rate, 2),
                "last_call_time": last_call.isoformat() if last_call else None
            }

            # --- Cache Write ---
            if redis and cache_key:
                try:
                    await redis.setex(cache_key, 300, json.dumps(result, default=str))
                except Exception as e:
                    logger.warning("Redis write error: %s", e)
            # -------------------

            return result


@router.get("/api-trends")
async def get_api_trends(
    days: int = Query(7, ge=1, le=90),
    user: dict = Depends(require_api_key)
):
    """
    Get API call trends over time.
    Returns daily statistics for the specified number of days.
    """
    admin_flag = is_admin(user)
    user_name = user["user_name"]
    
    # --- Cache Check ---
    redis = await get_redis()
    cache_key = None
    if redis:
        role_part = "admin" if admin_flag else f"user:{user_name}"
        cache_key = f"dashboard:trends:{role_part}:{days}"
        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("Redis read error: %s", e)
    # -------------------

    start_date = (datetime.now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Build query based on role using Stats table
            if admin_flag:
                sql = """
                    SELECT 
                        DATE(time_bucket) as date,
                        SUM(total_calls) as total_calls,
                        SUM(total_calls - total_error) as success_calls,
                        SUM(total_error) as error_calls
                    FROM api_access_stats_1m
                    WHERE time_bucket >= %s AND user_name = 'ALL'
                    GROUP BY date
                    ORDER BY date ASC
                """
                params = (start_date_str,)
            else:
                sql = """
                    SELECT 
                        DATE(time_bucket) as date,
                        SUM(total_calls) as total_calls,
                        SUM(total_calls - total_error) as success_calls,
                        SUM(total_error) as error_calls
                    FROM api_access_stats_1m
                    WHERE user_name = %s AND time_bucket >= %s
                    GROUP BY date
                    ORDER BY date ASC
                """
                params = (user_name, start_date_str)
            
            await cursor.execute(sql, params)
            rows = await cursor.fetchall()
            
            trends = []
            for row in rows:
                date_val = row[0]
                total = row[1] or 0
                success = row[2] or 0
                errors = row[3] or 0
                success_rate = (success / total * 100) if total > 0 else 0
                
                trends.append({
                    "date": date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val),
                    "total_calls": total,
                    "success_calls": success,
                    "error_calls": errors,
                    "success_rate": round(success_rate, 2)
                })
            
            # --- Cache Write ---
            if redis and cache_key:
                try:
                    await redis.setex(cache_key, 300, json.dumps(trends, default=str))
                except Exception as e:
                    logger.warning("Redis write error: %s", e)
            # -------------------

            return trends


@router.get("/api-trends-24h")
async def get_api_trends_24h(
    user: dict = Depends(require_api_key)
):
    """
    Get API call trends over the last 24 hours.
    Returns hourly statistics.
    """
    admin_flag = is_admin(user)
    user_name = user["user_name"]

    # --- Cache Check ---
    redis_conn = await get_redis()
    cache_key = None
    if redis_conn:
        role_part = "admin" if admin_flag else f"user:{user_name}"
        cache_key = f"dashboard:trends24h:{role_part}"
        try:
            cached_data = await redis_conn.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("Redis read error: %s", e)
    # -------------------
    
    # Calculate start time (24 hours ago, rounded down to the hour)
    now = datetime.now()
    start_time = (now - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
    start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Build query based on role using Stats table
            if admin_flag:
                sql = """
                    SELECT 
                        DATE_FORMAT(time_bucket, '%%Y-%%m-%%d %%H:00:00') as hour_key,
                        SUM(total_calls) as total_calls,
                        SUM(total_calls - total_error) as success_calls
                    FROM api_access_stats_1m
                    WHERE time_bucket >= %s AND user_name = 'ALL'
                    GROUP BY hour_key
                    ORDER BY hour_key ASC
                """
                params = (start_time_str,)
            else:
                sql = """
                    SELECT 
                        DATE_FORMAT(time_bucket, '%%Y-%%m-%%d %%H:00:00') as hour_key,
                        SUM(total_calls) as total_calls,
                        SUM(total_calls - total_error) as success_calls
                    FROM api_access_stats_1m
                    WHERE user_name = %s AND time_bucket >= %s
                    GROUP BY hour_key
                    ORDER BY hour_key ASC
                """
                params = (user_name, start_time_str)
            
            await cursor.execute(sql, params)
            rows = await cursor.fetchall()
            
            # Map query results to a dictionary for easy sequence completion
            results_map = {}
            for row in rows:
                results_map[str(row[0])] = {
                    "total": row[1] or 0,
                    "success": row[2] or 0
                }
            
            # Generate complete 24-hour sequence to ensure no gaps
            trends = []
            for i in range(24):
                current_hour = start_time + timedelta(hours=i)
                current_hour_str = current_hour.strftime('%Y-%m-%d %H:00:00')
                
                stats = results_map.get(current_hour_str, {"total": 0, "success": 0})
                
                trends.append({
                    "hour": current_hour.strftime('%H:00'),
                    "timestamp": current_hour_str,
                    "total_calls": int(stats["total"]),
                    "success_calls": int(stats["success"])
                })
            
            # --- Cache Write ---
            if redis_conn and cache_key:
                try:
                    await redis_conn.setex(cache_key, 300, json.dumps(trends, default=str))
                except Exception as e:
                    logger.warning("Redis write error: %s", e)
            # -------------------

            return trends


@router.get("/api-peak-24h")
async def get_api_peak_24h(
    user: dict = Depends(require_api_key)
):
    """
    Get the peak (MAX) requests per minute for each hour over the last 24 hours.
    This helps administrators set appropriate rate limits.
    """
    admin_flag = is_admin(user)
    
    # Only admins can see peak statistics for global optimization
    if not admin_flag:
        raise HTTPException(status_code=403, detail="Admin access required")

    # --- Cache Check ---
    redis_conn = await get_redis()
    cache_key = "dashboard:peak24h:admin"
    if redis_conn:
        try:
            cached_data = await redis_conn.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception: pass
    
    # Calculate start time
    now = datetime.now()
    start_time = (now - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)
    start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Aggregate MAX(total_calls) within each hour from the 1m stats table
            sql = """
                SELECT 
                    DATE_FORMAT(time_bucket, '%%Y-%%m-%%d %%H:00:00') as hour_key,
                    MAX(total_calls) as peak_calls
                FROM api_access_stats_1m
                WHERE time_bucket >= %s AND user_name = 'ALL'
                GROUP BY hour_key
                ORDER BY hour_key ASC
            """
            await cursor.execute(sql, (start_time_str,))
            rows = await cursor.fetchall()
            
            results_map = {str(row[0]): row[1] for row in rows}
            
            peaks = []
            for i in range(24):
                current_hour = start_time + timedelta(hours=i)
                current_hour_str = current_hour.strftime('%Y-%m-%d %H:00:00')
                peak = results_map.get(current_hour_str, 0)
                
                peaks.append({
                    "hour": current_hour.strftime('%H:00'),
                    "timestamp": current_hour_str,
                    "peak": int(peak)
                })
            
            if redis_conn:
                await redis_conn.setex(cache_key, 300, json.dumps(peaks))
                
            return peaks


@router.get("/recent-activities")
async def get_recent_activities(
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(require_api_key)
):
    """
    Get recent activities from DAILY SHARDED tables.
    """
    admin_flag = is_admin(user)
    user_name = user["user_name"]
    table_name = get_audit_table_name()

    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            result = {}
            
            # Recent users (admin only)
            if admin_flag:
                await cursor.execute("""
                    SELECT user_name, role, created_at
                    FROM api_users
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (min(limit, 5),))
                
                recent_users = []
                for row in await cursor.fetchall():
                    recent_users.append({
                        "user_name": row[0],
                        "role": row[1],
                        "created_at": row[2].isoformat() if row[2] else None
                    })
                result["recent_users"] = recent_users
            
            # Recent API calls from SHARDED table
            try:
                # 检查表是否存在
                await cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                if not await cursor.fetchone():
                    result["recent_calls"] = []
                    if admin_flag: result["recent_errors"] = []
                else:
                    sql_calls = f"SELECT id, user_name, endpoint, method, status_code, process_time_ms, created_at FROM {table_name}"
                    if not admin_flag:
                        sql_calls += " WHERE user_name = %s"
                        params = (user_name, limit)
                    else:
                        params = (limit,)
                    
                    sql_calls += " ORDER BY created_at DESC, id DESC LIMIT %s"
                    
                    await cursor.execute(sql_calls, params)
                    recent_calls = []
                    for row in await cursor.fetchall():
                        recent_calls.append({
                            "id": row[0], "user_name": row[1], "endpoint": row[2],
                            "method": row[3], "status_code": row[4],
                            "process_time_ms": float(row[5]) if row[5] else 0,
                            "created_at": row[6].isoformat() if row[6] else None
                        })
                    result["recent_calls"] = recent_calls

                    # Recent errors
                    if admin_flag:
                        await cursor.execute(f"""
                            SELECT id, user_name, endpoint, method, status_code, 
                                   error_message, created_at
                            FROM {table_name}
                            WHERE status_code >= 400
                            ORDER BY created_at DESC, id DESC
                            LIMIT %s
                        """, (min(limit, 5),))
                        
                        recent_errors = []
                        for row in await cursor.fetchall():
                            recent_errors.append({
                                "id": row[0], "user_name": row[1], "endpoint": row[2],
                                "method": row[3], "status_code": row[4],
                                "error_message": row[5],
                                "created_at": row[6].isoformat() if row[6] else None
                            })
                        result["recent_errors"] = recent_errors
            except Exception as e:
                import logging
                logging.error(f"Dashboard recent-activities error: {e}")
                result["recent_calls"] = []
                if admin_flag: result["recent_errors"] = []
            
            return result


@router.get("/resource-stats")
async def get_resource_stats(
    period: str = Query("today", pattern="^(today|week|month)$"),
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(require_api_key)
):
    """
    Get per-resource (endpoint) statistics.
    Admins see global stats, users see their own stats.
    """
    admin_flag = is_admin(user)
    user_name = user["user_name"]

    # --- Cache Check ---
    redis = await get_redis()
    cache_key = None
    if redis:
        role_part = "admin" if admin_flag else f"user:{user_name}"
        cache_key = f"dashboard:resource-stats:{role_part}:{period}:{limit}"
        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("Redis read error: %s", e)
    # -------------------

    # Determine time range
    if period == "today":
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_time = datetime.now() - timedelta(days=7)
    else:  # month
        start_time = datetime.now() - timedelta(days=30)
    
    start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')

    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Aggregate stats by endpoint
            if admin_flag:
                sql = """
                    SELECT 
                        endpoint,
                        SUM(total_calls) as total_calls,
                        SUM(total_error) as error_count,
                        SUM(total_calls * avg_latency) / NULLIF(SUM(total_calls), 0) as avg_latency,
                        MAX(max_latency) as max_latency
                    FROM api_access_stats_1m
                    WHERE time_bucket >= %s AND user_name != 'ALL' AND endpoint != 'ALL'
                    GROUP BY endpoint
                    ORDER BY total_calls DESC
                    LIMIT %s
                """
                params = (start_time_str, limit)
            else:
                sql = """
                    SELECT 
                        endpoint,
                        SUM(total_calls) as total_calls,
                        SUM(total_error) as error_count,
                        SUM(total_calls * avg_latency) / NULLIF(SUM(total_calls), 0) as avg_latency,
                        MAX(max_latency) as max_latency
                    FROM api_access_stats_1m
                    WHERE time_bucket >= %s AND user_name = %s AND endpoint != 'ALL'
                    GROUP BY endpoint
                    ORDER BY total_calls DESC
                    LIMIT %s
                """
                params = (start_time_str, user_name, limit)

            await cursor.execute(sql, params)
            rows = await cursor.fetchall()

            results = []
            for row in rows:
                total = int(row[1]) if row[1] else 0
                errors = int(row[2]) if row[2] else 0
                results.append({
                    "endpoint": row[0],
                    "total_calls": total,
                    "error_count": errors,
                    "error_rate": round((errors / total * 100), 2) if total > 0 else 0,
                    "avg_latency": round(float(row[3]), 2) if row[3] else 0,
                    "max_latency": round(float(row[4]), 2) if row[4] else 0
                })

            # --- Cache Write ---
            if redis and cache_key:
                try:
                    await redis.setex(cache_key, 120, json.dumps(results, default=str))
                except Exception as e:
                    logger.warning("Redis write error: %s", e)
            # -------------------

            return results


@router.get("/user-ranking")
async def get_user_ranking(
    period: str = Query("today", pattern="^(today|week|month)$"),
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(require_api_key)
):
    """
    Get Top N users by API call volume.
    Admins see global ranking.
    """
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Permission denied")

    # --- Cache Check ---
    redis = await get_redis()
    cache_key = None
    if redis:
        cache_key = f"dashboard:user-ranking:{period}:{limit}"
        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("Redis read error: %s", e)
    # -------------------

    # Determine time range
    if period == "today":
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_time = datetime.now() - timedelta(days=7)
    else:  # month
        start_time = datetime.now() - timedelta(days=30)
    
    start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')

    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Aggregate stats by user
            await cursor.execute("""
                SELECT 
                    user_name,
                    SUM(total_calls) as total_calls,
                    SUM(total_error) as error_count
                FROM api_access_stats_1m
                WHERE time_bucket >= %s AND user_name != 'ALL'
                GROUP BY user_name
                ORDER BY total_calls DESC
                LIMIT %s
            """, (start_time_str, limit))
            
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                total = int(row[1]) if row[1] else 0
                errors = int(row[2]) if row[2] else 0
                results.append({
                    "user_name": row[0],
                    "total_calls": total,
                    "error_count": errors,
                    "error_rate": round((errors / total * 100), 2) if total > 0 else 0
                })

            # --- Cache Write ---
            if redis and cache_key:
                try:
                    await redis.setex(cache_key, 120, json.dumps(results, default=str))
                except Exception as e:
                    logger.warning("Redis write error: %s", e)
            # -------------------

            return results


@router.get("/online-users")
async def get_online_users(
    user: dict = Depends(require_api_key)
):
    """
    Get current online user count (active Redis sessions).
    Admins also get a list of online users with details.
    """
    redis = await get_redis()
    if not redis:
        return {"count": 0, "users": []}
        
    try:
        # Scan for api key sessions
        # Pattern: auth:api_key:*
        cursor = 0
        all_keys = []
        while True:
            cursor, keys = await redis.scan(cursor, match="auth:api_key:*", count=100)
            all_keys.extend(keys)
            if cursor == 0:
                break
        
        count = len(all_keys)
        
        # If admin, fetch details
        users_details = []
        if user.get("role") == "admin" and all_keys:
            # Use pipeline to fetch hgetall and ttl for all keys
            pipe = redis.pipeline()
            for key in all_keys:
                pipe.hgetall(key)
                pipe.ttl(key)
            
            results = await pipe.execute()
            
            # Results will be [hgetall1, ttl1, hgetall2, ttl2, ...]
            import datetime
            now = datetime.datetime.now()
            
            for i in range(0, len(results), 2):
                user_data = results[i]
                ttl = results[i+1]
                
                if user_data and "user_name" in user_data:
                    # Estimate last active time: now - (max_ttl - current_ttl)
                    # We use 3600 as max_ttl
                    last_active_seconds = 3600 - ttl if ttl > 0 else 0
                    last_active_time = (now - datetime.timedelta(seconds=last_active_seconds)).strftime("%Y-%m-%d %H:%M:%S")
                    
                    users_details.append({
                        "username": user_data["user_name"],
                        "last_active": last_active_time,
                        "role": user_data.get("role", "user")
                    })
            
            # Sort by last active time descending
            users_details.sort(key=lambda x: x["last_active"], reverse=True)

        return {
            "count": count,
            "users": users_details
        }
    except Exception as e:
        logger.warning("Redis error in get_online_users: %s", e)
        return {"count": 0, "users": []}


@router.get("/my-resources", response_model=List[ResourceResponse])
async def get_my_resources(
    user: dict = Depends(require_api_key)
):
    """
    Get all resources that the current user has permission to access.
    Admins see all resources.
    """
    admin_flag = is_admin(user)
    
    if admin_flag:
        return await MetaService.list_resources()
    else:
        # Assuming user["user_id"] is available from AuthService
        return await MetaService.get_user_resources(user["user_id"])