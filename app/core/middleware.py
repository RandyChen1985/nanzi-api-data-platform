from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.background import BackgroundTask
import time
import uuid
import logging
import json
from contextvars import ContextVar
from app.core.database import get_db_connection
from app.core.config import settings
from app.utils.sharding import ensure_audit_table_exists

logger = logging.getLogger(__name__)

# Max chars for audit response body (truncated to reduce storage & sensitive data exposure)
def _truncate_response_body(body: str | None) -> str | None:
    if body is None:
        return None
    max_chars = settings.AUDIT_RESPONSE_BODY_MAX_CHARS
    if max_chars <= 0:
        return None
    if len(body) <= max_chars:
        return body
    return body[:max_chars] + "…[truncated]"

# Context variable to store trace_id for access in Pydantic models/other services
request_trace_id: ContextVar[str] = ContextVar("request_trace_id", default="")

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        process_time = time.perf_counter() - start_time
        
        # Add Server-Timing header
        duration_ms = process_time * 1000
        response.headers["Server-Timing"] = f"total;dur={duration_ms:.2f}"
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response

async def _write_access_log(log_data: dict):
    """Asynchronous task to write log to MySQL (Daily Sharding)"""
    try:
        async with get_db_connection() as conn:
            # 1. Ensure table exists (Daily Partitioning)
            table_name = await ensure_audit_table_exists(conn)
            
            async with conn.cursor() as cursor:
                # 2. Insert into the sharded table (Unified Schema)
                sql = f"""
                    INSERT INTO {table_name} (
                        trace_id, user_id, user_name, endpoint, method, status_code,
                        process_time_ms, client_ip, request_params, response_body, 
                        action_type, source_sql, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                await cursor.execute(sql, (
                    log_data["trace_id"],
                    log_data.get("user_id"),
                    log_data["user_name"],
                    log_data["endpoint"],
                    log_data["method"],
                    log_data["status_code"],
                    log_data["process_time_ms"],
                    log_data["client_ip"],
                    log_data["request_params"],
                    log_data.get("response_body"),
                    log_data.get("action_type", "API_QUERY"),
                    log_data.get("source_sql"),
                    log_data["created_at"]
                ))
    except Exception as e:
        logging.error(f"Failed to write access log to DB: {e}")

from starlette.background import BackgroundTask, BackgroundTasks

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        is_ai_chat = "/ai/chat-analysis" in path
        
        # Generate trace_id
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        
        # Set context variable
        token = request_trace_id.set(trace_id)
        
        # Capture request body for POST/PUT/PATCH (Safely skip for AI chat)
        body = None
        if not is_ai_chat and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body = body_bytes.decode('utf-8', errors='ignore')
                
                # Re-construct receive to allow multiple reads
                async def receive():
                    return {"type": "http.request", "body": body_bytes, "more_body": False}
                request._receive = receive
            except Exception as e:
                logging.debug(f"Failed to capture request body: {e}")

        start_time = time.perf_counter()
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            logging.error(f"Middleware caught exception: {e}")
            raise e
        
        # Inject RateLimit Headers if present in request.state
        ratelimit_headers = getattr(request.state, "ratelimit_headers", None)
        if ratelimit_headers:
            for k, v in ratelimit_headers.items():
                response.headers[k] = v

        # Capture response body (ONLY for standard JSON responses, NEVER for AI streams)
        response_body = None
        content_type = response.headers.get("content-type", "")
        if not is_ai_chat and "application/json" in content_type:
            try:
                res_body = [section async for section in response.body_iterator]
                response.body_iterator = iterate_in_threadpool(iter(res_body))
                response_body = b"".join(res_body).decode("utf-8", errors="ignore")
            except Exception as e:
                logging.debug(f"Failed to capture response body: {e}")

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Prepare log data (moved up to ensure variables are defined)
        user = getattr(request.state, "user", None)
        user_name = user.get("user_name", "anonymous") if user and isinstance(user, dict) else "anonymous"
        user_id = user.get("user_id") if user and isinstance(user, dict) else None
        
        # Skip logging for some internal/health endpoints
        if path in ["/health", "/favicon.ico"] or path.startswith("/assets"):
            return response

        # Combine query params and body for request_params log
        params_dict = dict(request.query_params)
        if body:
            try:
                body_json = json.loads(body)
                if isinstance(body_json, dict):
                    params_dict.update(body_json)
                else:
                    params_dict["_body"] = body
            except:
                params_dict["_body"] = body

        log_data = {
            "trace_id": trace_id,
            "user_id": user_id,
            "user_name": user_name,
            "endpoint": path,
            "method": request.method,
            "status_code": response.status_code,
            "process_time_ms": duration_ms,
            "client_ip": request.client.host if request.client else "unknown",
            "request_params": json.dumps(params_dict, ensure_ascii=False),
            "response_body": _truncate_response_body(response_body),
            "action_type": getattr(request.state, "action_type", "API_QUERY"),
            "source_sql": getattr(request.state, "source_sql", None),
            "created_at": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Attach background task to write to DB (Safely Merge)
        new_task = BackgroundTask(_write_access_log, log_data)
        if response.background is None:
            response.background = new_task
        elif isinstance(response.background, BackgroundTasks):
            response.background.add_task(_write_access_log, log_data)
        elif isinstance(response.background, BackgroundTask):
            # Convert single existing task to BackgroundTasks
            existing_task = response.background
            response.background = BackgroundTasks()
            response.background.tasks.append(existing_task)
            response.background.add_task(_write_access_log, log_data)
        else:
            # Fallback (unlikely)
            response.background = new_task
        
        # Log to console as well
        logging.info(
            f"ACCESS | {log_data['user_name']} | {log_data['client_ip']} | "
            f"{log_data['method']} {log_data['endpoint']} | "
            f"{log_data['status_code']} | {duration_ms:.2f}ms | {trace_id}"
        )
        
        # Add trace_id to response header
        response.headers["X-Trace-ID"] = trace_id
        
        return response

from starlette.concurrency import iterate_in_threadpool
