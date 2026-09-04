"""Redfox 数据接口调用日志 API。"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.auth import get_current_user_or_ak
from core.redis_client import (
    clear_redfox_logs,
    get_redfox_logs,
    get_redfox_stats,
)

from .base import error_response, success_response

router = APIRouter(prefix="/redfox", tags=["Redfox 日志"])


@router.get(
    "/stats",
    summary="获取 redfox 调用统计",
    description="按日期聚合 redfox 数据接口调用统计。",
)
async def redfox_stats(
    date: Optional[str] = Query(
        None,
        description="日期，格式为 YYYY-MM-DD，默认为今天",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    current_user: dict = Depends(get_current_user_or_ak),
):
    """获取 redfox 调用统计信息。"""
    try:
        stats = get_redfox_stats(date)
        if "error" in stats:
            return error_response(code=500, message=stats["error"])
        return success_response(stats)
    except Exception as exc:  # noqa: BLE001
        return error_response(code=500, message=f"获取统计信息失败: {exc}")


@router.get(
    "/logs",
    summary="获取 redfox 调用日志列表",
    description="按时间倒序返回最近的 redfox 调用日志。",
)
async def redfox_logs(
    limit: int = Query(50, ge=1, le=500, description="返回条数（1-500）"),
    offset: int = Query(0, ge=0, description="跳过的记录数"),
    current_user: dict = Depends(get_current_user_or_ak),
):
    """获取 redfox 调用日志。"""
    try:
        items = get_redfox_logs(limit=limit, offset=offset)
        return success_response({"items": items, "limit": limit, "offset": offset})
    except Exception as exc:  # noqa: BLE001
        return error_response(code=500, message=f"获取日志失败: {exc}")


@router.post(
    "/logs/clear",
    summary="清空 redfox 调用日志",
    description="清空调用日志列表与当日统计，保留历史日期的统计。",
)
async def redfox_logs_clear(current_user: dict = Depends(get_current_user_or_ak)):
    """清空 redfox 调用日志。"""
    try:
        ok = clear_redfox_logs()
        if not ok:
            return error_response(code=500, message="清空日志失败")
        return success_response({"cleared_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    except Exception as exc:  # noqa: BLE001
        return error_response(code=500, message=f"清空日志失败: {exc}")
