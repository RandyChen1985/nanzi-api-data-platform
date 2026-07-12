from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import List, Optional, Dict, Union
import asyncio
import inspect
from types import SimpleNamespace
from app.schemas.datasource import (
    DataSourceCreate, DataSourceUpdate, DataSourceResponse, DataSourceConnectionTest,
    DbProfileTaskResponse, DbTableProfileResponse, DbTableProfileSummaryResponse, TableProfileIgnorePayload,
    DataSourcePermissionsResponse,
)
from app.services.datasource_service import DataSourceService
from app.services.db_profile_service import DbProfileService
from app.services.permission_service import PermissionService
from app.core.dependencies import require_admin, require_api_key, require_permission
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


async def _close_test_pool(pool):
    if hasattr(pool, "close"):
        res = pool.close()
        if inspect.isawaitable(res):
            await res
    if hasattr(pool, "wait_closed"):
        res = pool.wait_closed()
        if inspect.isawaitable(res):
            await res


async def _run_connection_test(datasource, pool):
    if datasource.source_type == "clickhouse":
        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                await cursor.fetchone()
    elif datasource.source_type == "mysql":
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                await cursor.fetchone()
    elif datasource.source_type == "oracle":
        is_async_pool = hasattr(pool, 'acquire') and asyncio.iscoroutinefunction(pool.acquire)

        if is_async_pool:
            conn = await pool.acquire()
            async with conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1 FROM DUAL")
                    await cursor.fetchone()
        else:
            def sync_test():
                with pool.acquire() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1 FROM DUAL")
                        cursor.fetchone()
            await asyncio.to_thread(sync_test)
    elif datasource.source_type == "sqlserver":
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                await cursor.fetchone()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported source type: {datasource.source_type}")


def _format_connection_error(datasource, exc: Exception) -> str:
    message = str(exc)
    if datasource.source_type == "sqlserver" and "unsupported protocol" in message.lower():
        return (
            f"{message}\n\n"
            "诊断：客户端已经进入 SQL Server TLS 握手阶段，但当前协议被 ODBC/OpenSSL 拒绝。"
            "如果页面已关闭 Encrypt 且仍报此错，通常是 SQL Server 服务端强制加密，"
            "或服务端只支持 TLS 1.0/1.1。\n"
            "处理建议：优先让 SQL Server 开启 TLS 1.2/升级补丁；临时方案可在本机安装 "
            "ODBC Driver 17 for SQL Server，并把 ODBC Driver 改为 “ODBC Driver 17 for SQL Server” 后重试。"
        )
    return message

@router.get("/datasources", response_model=List[DataSourceResponse])
async def list_datasources(
    status: Optional[str] = None,
    user: dict = Depends(require_api_key)
):
    """
    List data sources with optional status filter.
    """
    datasources = await DataSourceService.list_datasources(status=status)
    return datasources

@router.post("/datasources", response_model=DataSourceResponse)
async def create_datasource(
    datasource: DataSourceCreate,
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    Create a new data source.
    Admin only.
    """
    try:
        # Check if exists
        existing = await DataSourceService.get_datasource_by_name(datasource.source_name)
        if existing:
            raise HTTPException(status_code=400, detail=f"Data source {datasource.source_name} already exists")
        
        new_datasource = await DataSourceService.create_datasource(datasource)
        return new_datasource
    except Exception as e:
        logger.error(f"Failed to create data source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/datasources/test-connection", response_model=dict)
async def test_datasource_connection_with_config(
    request: DataSourceConnectionTest,
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    Test connection using the submitted config without saving it.
    """
    pool = None
    try:
        from app.services.pool_manager import DataSourcePoolManager

        password = request.password
        if request.source_id and not password:
            existing = await DataSourceService.get_datasource(request.source_id)
            if not existing:
                raise HTTPException(status_code=404, detail="Data source not found")
            password = existing.password

        datasource = SimpleNamespace(
            id=request.source_id or -1,
            source_name=request.source_name,
            source_type=request.source_type,
            host=request.host,
            port=request.port,
            database_name=request.database_name,
            username=request.username,
            password=password,
            extra_params=request.extra_params,
            status=request.status,
        )

        pool = await DataSourcePoolManager.create_ephemeral_pool(datasource)
        await _run_connection_test(datasource, pool)
        return {"status": "success", "message": "Connection successful"}
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return {"status": "failed", "message": _format_connection_error(request, e)}
    finally:
        if pool is not None:
            try:
                await _close_test_pool(pool)
            except Exception as close_error:
                logger.warning(f"Failed to close test pool: {close_error}")

@router.get("/datasources/{source_id}", response_model=DataSourceResponse)
async def get_datasource(
    source_id: int,
    user: dict = Depends(require_api_key)
):
    """
    Get data source by ID.
    Admin only.
    """
    datasource = await DataSourceService.get_datasource(source_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Data source not found")
    return datasource


@router.get(
    "/datasources/{source_id}/permissions",
    response_model=DataSourcePermissionsResponse,
)
async def get_datasource_permissions(
    source_id: int,
    user: dict = Depends(require_permission("element:datasource:edit")),
):
    """
    查看指定数据源的直接授权主体（角色 / 用户）及表级范围。
    """
    datasource = await DataSourceService.get_datasource(source_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Data source not found")

    result = await PermissionService.get_datasource_permission_holders(datasource.source_name)
    result.source_id = source_id
    return result

@router.put("/datasources/{source_id}", response_model=DataSourceResponse)
async def update_datasource(
    source_id: int,
    update_data: DataSourceUpdate,
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    Update a data source.
    Admin only.
    """
    try:
        existing = await DataSourceService.get_datasource(source_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Data source not found")
        
        updated = await DataSourceService.update_datasource(source_id, update_data)
        return updated
    except Exception as e:
        logger.error(f"Failed to update data source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/datasources/{source_id}", response_model=dict)
async def delete_datasource(
    source_id: int,
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    Delete a data source.
    Admin only.
    """
    try:
        success = await DataSourceService.delete_datasource(source_id)
        if not success:
            raise HTTPException(status_code=404, detail="Data source not found")
        return {"deleted_id": source_id, "message": "Data source deleted"}
    except ValueError as e:
        # Handle business logic errors (e.g., dependency check)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete data source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/reorder", response_model=dict)
async def reorder_datasources(
    request: Dict[str, List[int]],
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    Update the sorting order of data sources.
    Expects JSON: {"ids": [3, 1, 2]}
    """
    try:
        ids = request.get("ids")
        if not ids:
            raise HTTPException(status_code=400, detail="Missing 'ids' list in request body")
        
        await DataSourceService.reorder_datasources(ids)
        return {"message": "Data sources reordered successfully"}
    except Exception as e:
        logger.error(f"Failed to reorder data sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/datasources/{source_id}/test", response_model=dict)
async def test_datasource_connection(
    source_id: int,
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    Test data source connection.
    Admin only.
    """
    try:
        from app.services.pool_manager import DataSourcePoolManager
        
        datasource = await DataSourceService.get_datasource(source_id)
        if not datasource:
            raise HTTPException(status_code=404, detail="Data source not found")
        
        # Try to get/create pool
        pool = await DataSourcePoolManager.get_pool(source_id)
        await _run_connection_test(datasource, pool)
        
        return {"status": "success", "message": "Connection successful"}
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return {"status": "failed", "message": _format_connection_error(datasource, e)}


@router.post("/datasources/{source_id}/profile", response_model=DbProfileTaskResponse)
async def trigger_datasource_profile(
    source_id: int,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="为 true 时强制全量重跑，重置全部表并重新消耗 LLM Token"),
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    触发数据源元数据智能摸排分析任务（异步后台运行）
    """
    try:
        task = await DbProfileService.trigger_profiling_task(source_id, background_tasks, force=force)
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to trigger profiling task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasources/{source_id}/profile/cancel", response_model=DbProfileTaskResponse)
async def cancel_datasource_profile(
    source_id: int,
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    中断进行中的数据源摸排任务（当前表处理完成后停止，已完成表保留）
    """
    try:
        task = await DbProfileService.cancel_profiling_task(source_id)
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel profiling task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasources/{source_id}/profile-task", response_model=Optional[DbProfileTaskResponse])
async def get_datasource_profile_task(
    source_id: int,
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    获取数据源当前的摸排进度状态
    """
    try:
        task = await DbProfileService.get_task_status(source_id)
        return task
    except Exception as e:
        logger.error(f"Failed to get profiling task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/datasources/{source_id}/table-profiles/{table_name}",
    response_model=DbTableProfileResponse,
)
async def get_datasource_table_profile(
    source_id: int,
    table_name: str,
    user: dict = Depends(require_api_key),
):
    """获取单张表的完整摸排画像（按需加载）"""
    try:
        profile = await DbProfileService.get_table_profile(source_id, table_name)
        if not profile:
            raise HTTPException(status_code=404, detail="Table profile not found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get table profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/datasources/{source_id}/table-profiles",
    response_model=List[Union[DbTableProfileSummaryResponse, DbTableProfileResponse]],
)
async def list_datasource_table_profiles(
    source_id: int,
    summary: bool = Query(True, description="为 true 时仅返回轻量摘要，不含 DDL/样例/字段画像"),
    status: Optional[int] = Query(None, description="按摸排状态过滤，例如 2=已完成"),
    user: dict = Depends(require_api_key),
):
    """
    获取数据源的表画像草稿列表（支持元数据导入查看，所以允许 require_api_key 访问）
    """
    try:
        profiles = await DbProfileService.list_table_profiles(source_id, summary=summary, status=status)
        return profiles
    except Exception as e:
        logger.error(f"Failed to list table profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/datasources/{source_id}/table-profiles/ignore")
async def toggle_table_profile_ignore(
    source_id: int,
    payload: TableProfileIgnorePayload,
    user: dict = Depends(require_permission("element:datasource:edit"))
):
    """
    手动修改指定物理表的忽略状态
    """
    try:
        res = await DbProfileService.toggle_ignore(source_id, payload.table_name, payload.is_ignored)
        if not res:
            raise HTTPException(status_code=404, detail="Table profile not found")
        return {"status": "success", "message": "修改成功", "data": res}
    except Exception as e:
        logger.error(f"Failed to toggle table profile ignore: {e}")
        raise HTTPException(status_code=500, detail=str(e))

