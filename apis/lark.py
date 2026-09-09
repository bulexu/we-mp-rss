"""飞书多维表 (Lark Bitable) 推送配置 API。

路由前缀: ``/api/v1/wx/lark/bitables`` (与其它 ``apis/*.py`` 保持一致)。
"""
from __future__ import annotations

import json
import time
import traceback
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from core.auth import get_current_user_or_ak
from core.config import cfg
from core.db import DB
from core.lark_client import LarkError, get_lark_client
from core.models.lark_bitable import (
    ALLOWED_FIELD_KEYS,
    ArticleLarkPush,
    LarkBitable,
    validate_field_mapping,
)
from core.print import print_error, print_info, print_warning
from .base import error_response, success_response

router = APIRouter(prefix="/lark", tags=["飞书多维表"])


# ===== Pydantic 请求模型 =====

class CreateBitableRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    app_token: str = Field(..., min_length=1, max_length=255)
    table_id: str = Field(..., min_length=1, max_length=255)
    mp_ids: List[str] = Field(default_factory=list)
    field_mapping: dict = Field(default_factory=dict)
    enabled: bool = True


class UpdateBitableRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    app_token: Optional[str] = Field(None, min_length=1, max_length=255)
    table_id: Optional[str] = Field(None, min_length=1, max_length=255)
    mp_ids: Optional[List[str]] = None
    field_mapping: Optional[dict] = None
    enabled: Optional[bool] = None


class ManualPushRequest(BaseModel):
    article_id: str = Field(..., min_length=1)


# ===== Helper =====

def _bitable_to_dict(b: LarkBitable) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "app_token": b.app_token,
        "table_id": b.table_id,
        "mp_ids": b.get_mp_ids(),
        "field_mapping": b.get_field_mapping(),
        "enabled": bool(b.enabled),
        "last_pushed_at": b.last_pushed_at,
        "last_error": b.last_error,
        "last_error_at": b.last_error_at,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


# ===== CRUD =====

@router.get("/bitables", summary="列出飞书多维表配置")
async def list_bitables(
    enabled: Optional[bool] = Query(None),
    mp_id: Optional[str] = Query(None, description="按关联公众号过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user_or_ak),
):
    session = DB.get_session()
    try:
        query = session.query(LarkBitable)
        if enabled is not None:
            query = query.filter(LarkBitable.enabled == enabled)
        all_rows = query.order_by(LarkBitable.created_at.desc()).all()
        if mp_id:
            all_rows = [b for b in all_rows if mp_id in b.get_mp_ids()]
        total = len(all_rows)
        items = [_bitable_to_dict(b) for b in all_rows[offset: offset + limit]]
        return success_response({
            "list": items,
            "total": total,
            "page": {"limit": limit, "offset": offset},
            "allowed_field_keys": sorted(ALLOWED_FIELD_KEYS),
        })
    except Exception as e:
        return error_response(code=500, message=f"查询多维表配置失败: {e}")
    finally:
        try:
            session.close()
        except Exception:
            pass


@router.post("/bitables", summary="创建飞书多维表配置")
async def create_bitable(
    req: CreateBitableRequest,
    current_user: dict = Depends(get_current_user_or_ak),
):
    session = DB.get_session()
    try:
        try:
            normalized_mapping = validate_field_mapping(req.field_mapping)
        except ValueError as ve:
            return error_response(code=400, message=str(ve))

        # 去重 mp_ids
        mp_ids = sorted({m.strip() for m in (req.mp_ids or []) if (m or "").strip()})
        bitable = LarkBitable(
            id=str(uuid.uuid4()),
            name=req.name.strip(),
            app_token=req.app_token.strip(),
            table_id=req.table_id.strip(),
            mp_ids=json.dumps(mp_ids, ensure_ascii=False),
            field_mapping=json.dumps(normalized_mapping, ensure_ascii=False),
            enabled=bool(req.enabled),
        )
        session.add(bitable)
        session.commit()
        session.refresh(bitable)
        return success_response(_bitable_to_dict(bitable), "创建成功")
    except Exception as e:
        session.rollback()
        return error_response(code=500, message=f"创建失败: {e}")
    finally:
        try:
            session.close()
        except Exception:
            pass


@router.get("/bitables/{bitable_id}", summary="获取飞书多维表配置详情")
async def get_bitable(
    bitable_id: str,
    current_user: dict = Depends(get_current_user_or_ak),
):
    session = DB.get_session()
    try:
        b = session.query(LarkBitable).filter(LarkBitable.id == bitable_id).first()
        if not b:
            return error_response(code=404, message="多维表配置不存在")
        return success_response(_bitable_to_dict(b))
    finally:
        try:
            session.close()
        except Exception:
            pass


@router.put("/bitables/{bitable_id}", summary="更新飞书多维表配置")
async def update_bitable(
    bitable_id: str,
    req: UpdateBitableRequest,
    current_user: dict = Depends(get_current_user_or_ak),
):
    session = DB.get_session()
    try:
        b = session.query(LarkBitable).filter(LarkBitable.id == bitable_id).first()
        if not b:
            return error_response(code=404, message="多维表配置不存在")

        if req.name is not None:
            b.name = req.name.strip()
        if req.app_token is not None:
            b.app_token = req.app_token.strip()
        if req.table_id is not None:
            b.table_id = req.table_id.strip()
        if req.mp_ids is not None:
            mp_ids = sorted({m.strip() for m in req.mp_ids if (m or "").strip()})
            b.set_mp_ids(mp_ids)
        if req.field_mapping is not None:
            try:
                normalized = validate_field_mapping(req.field_mapping)
            except ValueError as ve:
                return error_response(code=400, message=str(ve))
            b.set_field_mapping(normalized)
        if req.enabled is not None:
            b.enabled = bool(req.enabled)

        session.commit()
        session.refresh(b)
        return success_response(_bitable_to_dict(b), "更新成功")
    except Exception as e:
        session.rollback()
        return error_response(code=500, message=f"更新失败: {e}")
    finally:
        try:
            session.close()
        except Exception:
            pass


@router.delete("/bitables/{bitable_id}", summary="删除飞书多维表配置")
async def delete_bitable(
    bitable_id: str,
    current_user: dict = Depends(get_current_user_or_ak),
):
    session = DB.get_session()
    try:
        b = session.query(LarkBitable).filter(LarkBitable.id == bitable_id).first()
        if not b:
            return error_response(code=404, message="多维表配置不存在")
        session.delete(b)
        session.commit()
        return success_response(message="删除成功")
    except Exception as e:
        session.rollback()
        return error_response(code=500, message=f"删除失败: {e}")
    finally:
        try:
            session.close()
        except Exception:
            pass


# ===== 验证可达 =====

@router.post("/bitables/{bitable_id}/test", summary="验证可达: 拉取字段定义")
async def test_bitable(
    bitable_id: str,
    current_user: dict = Depends(get_current_user_or_ak),
):
    """通过 ``GET /bitable/v1/apps/{app_token}/tables/{table_id}/fields`` 验证:

    * LARK_APP_ID / LARK_APP_SECRET 是否能拿到 tenant_access_token
    * app_token / table_id 是否真实存在且有权限

    仅返回字段定义供 UI 提示, 不修改数据库。
    """
    session = DB.get_session()
    try:
        b = session.query(LarkBitable).filter(LarkBitable.id == bitable_id).first()
        if not b:
            return error_response(code=404, message="多维表配置不存在")
        client = get_lark_client()
        if client is None:
            return error_response(
                code=400,
                message="未配置 lark.app_id / lark.app_secret,"
                        "请检查 config.yaml 或环境变量 LARK_APP_ID / LARK_APP_SECRET",
            )
        try:
            fields = client.list_fields(b.app_token, b.table_id)
            return success_response({
                "ok": True,
                "field_count": len(fields),
                "fields": [
                    {"name": f.get("field_name"), "type": f.get("type"), "id": f.get("field_id")}
                    for f in fields
                ],
            }, "连通正常")
        except LarkError as le:
            return success_response({
                "ok": False,
                "code": getattr(le, "code", None),
                "message": str(le),
            }, "连通失败")
        except Exception as e:  # noqa: BLE001
            return success_response({"ok": False, "message": str(e)}, "连通失败")
    finally:
        try:
            session.close()
        except Exception:
            pass


# ===== 推送 =====

@router.post("/bitables/{bitable_id}/push", summary="手动推送单篇文章到该 Bitable")
async def manual_push(
    bitable_id: str,
    req: ManualPushRequest,
    current_user: dict = Depends(get_current_user_or_ak),
):
    """绕过自动 hook,  把 article_id 强制推到指定 Bitable;  仍走 worker pool

    (异步执行,  返回任务标记 + 已存在的 article_lark_pushes 用于幂等检查)。
    """
    from core.models.article import Article as ArticleModel
    from core.models.feed import Feed
    from core.lark_push import lark_maybe_push

    session = DB.get_session()
    try:
        b = session.query(LarkBitable).filter(LarkBitable.id == bitable_id).first()
        if not b:
            return error_response(code=404, message="多维表配置不存在")
        art = (
            session.query(ArticleModel)
            .filter(ArticleModel.id == req.article_id)
            .first()
        )
        if not art:
            return error_response(code=404, message="文章不存在")
        already_pushed = (
            session.query(ArticleLarkPush)
            .filter(
                ArticleLarkPush.article_id == art.id,
                ArticleLarkPush.bitable_id == b.id,
            )
            .first()
        )
        lark_maybe_push(art.id)
        return success_response({
            "submitted": True,
            "article_id": art.id,
            "bitable_id": b.id,
            "already_pushed": bool(already_pushed),
            "previous_record_id": already_pushed.record_id if already_pushed else None,
        }, "已提交到 worker (异步执行)")
    except Exception as e:
        return error_response(code=500, message=f"提交推送失败: {e}")
    finally:
        try:
            session.close()
        except Exception:
            pass


@router.get("/status", summary="查询 lark 全局状态 (前端 banner 用)")
async def get_lark_status(
    current_user: dict = Depends(get_current_user_or_ak),
):
    """汇总诊断信息,帮助定位 "worker 没触发 / 没推出去" 的原因。

    返回字段:
      * ``enabled``         — 全局开关 ``cfg.lark.enabled`` 实际值
      * ``has_app_id``      — app_id 是否非空
      * ``has_app_secret``  — app_secret 是否非空
      * ``bitable_count``   — 数据库中 Bitable 行数 (含禁用)
      * ``enabled_count``   — enabled=True 的行数
      * ``token_ok``        — 是否能成功拿到 tenant_access_token (None 表示未尝试)
    """
    from core.lark_client import get_lark_client

    enabled = bool(cfg.get("lark.enabled", False))
    app_id = (cfg.get("lark.app_id") or "").strip()
    app_secret = (cfg.get("lark.app_secret") or "").strip()

    session = DB.get_session()
    try:
        bitable_count = session.query(LarkBitable).count()
        enabled_count = (
            session.query(LarkBitable)
            .filter(LarkBitable.enabled == True)  # noqa: E712
            .count()
        )
    finally:
        try:
            session.close()
        except Exception:
            pass

    token_ok: Optional[bool] = None
    if app_id and app_secret:
        try:
            client = get_lark_client()
            token_ok = bool(client and client.get_tenant_access_token())
        except Exception:  # noqa: BLE001
            token_ok = False

    issues: List[str] = []
    if not enabled:
        issues.append("全局未启用: 请在 config.yaml 设置 lark.enabled: True (或环境变量 LARK_ENABLED=True)")
    if not app_id:
        issues.append("缺少 lark.app_id (或环境变量 LARK_APP_ID)")
    if not app_secret:
        issues.append("缺少 lark.app_secret (或环境变量 LARK_APP_SECRET)")
    if enabled and app_id and app_secret and token_ok is False:
        issues.append("已配置但拉取 tenant_access_token 失败, 请检查 app_id / app_secret 是否有效")
    if enabled and bitable_count == 0:
        issues.append("还没有任何 Bitable 配置, 请新建一条")
    if enabled and enabled_count == 0:
        issues.append("Bitable 全部处于禁用状态, 请至少启用一条")

    return success_response({
        "enabled": enabled,
        "has_app_id": bool(app_id),
        "has_app_secret": bool(app_secret),
        "bitable_count": bitable_count,
        "enabled_count": enabled_count,
        "token_ok": token_ok,
        "issues": issues,
    })


@router.get("/pushes", summary="查询推送历史")
async def list_pushes(
    article_id: Optional[str] = Query(None),
    bitable_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user_or_ak),
):
    session = DB.get_session()
    try:
        q = session.query(ArticleLarkPush)
        if article_id:
            q = q.filter(ArticleLarkPush.article_id == article_id)
        if bitable_id:
            q = q.filter(ArticleLarkPush.bitable_id == bitable_id)
        total = q.count()
        rows = (
            q.order_by(ArticleLarkPush.pushed_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        items = [
            {
                "article_id": r.article_id,
                "bitable_id": r.bitable_id,
                "record_id": r.record_id,
                "pushed_at": r.pushed_at,
            }
            for r in rows
        ]
        return success_response({
            "list": items,
            "total": total,
            "page": {"limit": limit, "offset": offset},
        })
    except Exception as e:
        return error_response(code=500, message=f"查询推送历史失败: {e}")
    finally:
        try:
            session.close()
        except Exception:
            pass