"""飞书多维表推送 worker。

入口点:
  * ``lark_maybe_push(article_id)`` — 提交异步任务到模块级 ``ThreadPoolExecutor``,
    立刻返回,  不阻塞调用方 (Playwright/Redfox/RPA/refresh/add_article 4 处都调这个)。

worker 内部:
  1. 开新 session
  2. 读 article + Feed.mp_name
  3. 全局 ``lark.enabled`` 为 False → 直接退出
  4. 查关联 Bitables (``LarkBitable.enabled=True`` 且 ``mp_ids`` 含 ``article.mp_id``)
  5. 对每个 Bitable:
     *  检查 ``article_lark_pushes(article_id, bitable_id)`` 是否存在, 存在 → 跳过
     *  不存在 → 构造 ``fields`` 字典, 调 ``batch_create``
     *  成功后写 ``article_lark_pushes`` 并更新 ``last_pushed_at``
     *  失败后更新 ``last_error`` / ``last_error_at`` 并 log

幂等性靠 ``article_lark_pushes`` 复合主键 + 罕见的并发竞争时 SQLite/PostgreSQL
INSERT 主键冲突由 IntegrityError 兜底捕获。
"""
from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from core.config import cfg
from core.db import DB
from core.lark_client import LarkClient, LarkError, get_lark_client
from core.models.article import Article
from core.models.feed import Feed
from core.models.lark_bitable import ALLOWED_FIELD_KEYS, ArticleLarkPush, LarkBitable
from core.print import print_warning, print_info

# 模块级线程池: 4 worker 足够覆盖大多数场景, 不会把 token 刷新打爆。
# daemon=True 跟随主进程退出, 不阻止进程关闭。
_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_LOCK_IMPORTED = False


def _lark_thread_excepthook(args):
    """捕获 ThreadPoolExecutor 线程里漏出的异常, 打完整 traceback。

    默认 ``threading.excepthook`` 只打 ``Exception in thread ...`` 一行,
    对调试 worker 死因极不友好。这里补足 traceback。
    """
    print_warning(
        f"[lark] uncaught exception in thread {args.thread.name!r}: "
        f"{args.exc_value!r}"
    )
    traceback.print_exception(
        type(args.exc_value), args.exc_value, args.exc_traceback
    )


# 仅设置一次, 避免 reload 时重复挂多个 hook。
if not getattr(threading.excepthook, "_lark_hook_installed", False):
    _orig_excepthook = threading.excepthook
    def _patched_excepthook(args):
        if args.thread.name and args.thread.name.startswith("lark-push"):
            _lark_thread_excepthook(args)
            return
        _orig_excepthook(args)
    _patched_excepthook._lark_hook_installed = True  # type: ignore[attr-defined]
    threading.excepthook = _patched_excepthook


def _get_executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lark-push")
    return _EXECUTOR


# ---------- 字段映射取值 ----------

def _resolve_field_value(article: Article, feed: Feed | None, key: str):
    """把字段映射白名单 key 转成实际可发给飞书的值。

    对 ``publish_time`` 自动转 ISO8601 字符串 (避免飞书接到 epoch 数字一脸懵)。
    其他 key 直接 ``getattr`` Article / Feed。
    """
    if key == "publish_time":
        ts = getattr(article, "publish_time", None)
        if not ts:
            return None
        try:
            # publish_time 既可能是秒也可能是毫秒
            ts = int(ts)
            if ts > 10_000_000_000:
                ts = ts // 1000
            return datetime.utcfromtimestamp(ts).isoformat() + "Z"
        except (TypeError, ValueError, OverflowError):
            return None

    if key in {"mp_id", "mp_name"}:
        if feed is None and key == "mp_name":
            return None
        if key == "mp_name":
            return getattr(feed, "mp_name", None)
        return getattr(article, "mp_id", None)

    return getattr(article, key, None)


def _build_fields_for_article(
    article: Article,
    feed: Feed | None,
    mapping: dict,
) -> dict:
    fields: dict = {}
    for lhs, rhs in mapping.items():
        if lhs not in ALLOWED_FIELD_KEYS:
            continue
        value = _resolve_field_value(article, feed, lhs)
        if value is None:
            continue
        fields[rhs] = value
    return fields


# ---------- 主入口 ----------

def lark_maybe_push(article_id: str) -> None:
    """回调入口: 把 article 异步推到所有关联 Bitables。

    调用方只负责传 article_id 进来,  不要传 session 或 ORM 对象
    (worker 自己开新 session, 避免调用方 session 已关闭问题)。

    多次调用同一 article_id 安全:  worker 内部用复合主键 + IntegrityError 兜底。
    """
    if not cfg.get("lark.enabled", False):
        return
    if not article_id:
        return
    try:
        _get_executor().submit(_push_article_job, str(article_id))
    except RuntimeError:
        # 进程关闭时 executor 已 shutdown, 静默忽略
        pass


def _push_article_job(article_id: str) -> None:
    """worker 线程执行的实际推送逻辑。"""
    print_info(f"[lark] worker start article_id={article_id}")
    session = DB.get_session()
    try:
        # 直接复用模块级 DB 单例 (``core.db.DB`` 已经是 ``Db`` 实例, 不可再 ``()`` 调用)
        print_info(f"[lark] worker db ready article_id={article_id}")
        article = session.query(Article).filter(Article.id == article_id).first()
        if not article:
            print_info(f"[lark] skip: article {article_id} not found")
            return
        # 跳过被删除或正在抓取中的文章
        from core.models.base import DATA_STATUS

        if article.status == DATA_STATUS.DELETED:
            print_info(f"[lark] skip: article {article_id} status=DELETED")
            return
        if not (article.content or "").strip():
            # 没正文不推, 避免空记录
            print_info(
                f"[lark] skip: article {article_id} content empty"
            )
            return

        mp_id = getattr(article, "mp_id", None)
        if not mp_id:
            print_info(f"[lark] skip: article {article_id} mp_id is empty")
            return

        # 一次性查全部 enabled Bitables, 在 Python 里按 mp_ids 过滤
        bitables = (
            session.query(LarkBitable)
            .filter(LarkBitable.enabled == True)  # noqa: E712
            .all()
        )
        matched = [b for b in bitables if mp_id in b.get_mp_ids()]
        if not matched:
            print_info(
                f"[lark] skip: no matched bitable for article={article_id} "
                f"mp_id={mp_id} (enabled_bitables={len(bitables)})"
            )
            return

        feed = (
            session.query(Feed).filter(Feed.id == mp_id).first() if mp_id else None
        )

        client = get_lark_client()
        if client is None:
            # 没配 app_id/secret,  整体功能不可用 — 全局只 log 一次
            print_warning(
                f"[lark] lark.enabled=True 但 lark.app_id/app_secret 未配置,"
                f"article={article_id} 跳过推送"
            )
            return

        # 已推送过的 (article_id, bitable_id) 集合, 减少 SQL 查询
        existing_rows = (
            session.query(ArticleLarkPush)
            .filter(ArticleLarkPush.article_id == article_id)
            .all()
        )
        pushed_bitable_ids = {row.bitable_id for row in existing_rows}

        print_info(
            f"[lark] dispatch article={article_id} mp_id={mp_id} "
            f"matched={len(matched)} already_pushed={len(pushed_bitable_ids)}"
        )

        for bitable in matched:
            if bitable.id in pushed_bitable_ids:
                continue
            try:
                _push_one(article, feed, bitable, client, session)
            except Exception as exc:  # noqa: BLE001
                _record_failure(bitable, session, exc)
    except Exception:
        print_warning(f"[lark] worker 异常 article_id={article_id}")
        traceback.print_exc()
    finally:
        try:
            session.close()
        except Exception:
            pass


def _push_one(
    article: Article,
    feed: Feed | None,
    bitable: LarkBitable,
    client: LarkClient,
    session,
) -> None:
    """单条 Bitable 推送;  失败抛异常由 ``_record_failure`` 收尾。"""
    mapping = bitable.get_field_mapping()
    if not mapping:
        print_warning(
            f"[lark] bitable {bitable.id}({bitable.name}) field_mapping 为空, 跳过"
        )
        return

    fields = _build_fields_for_article(article, feed, mapping)
    if not fields:
        print_warning(
            f"[lark] bitable {bitable.id}({bitable.name}) 解析后 fields 为空, 跳过"
        )
        return

    created = client.batch_create_records(
        app_token=bitable.app_token,
        table_id=bitable.table_id,
        records=[{"fields": fields}],
    )
    record_id = ""
    if created:
        record_id = str(created[0].get("record_id") or "")

    # 写 article_lark_pushes; 复合主键防并发重复
    row = ArticleLarkPush(
        article_id=article.id,
        bitable_id=bitable.id,
        record_id=record_id,
        pushed_at=int(time.time() * 1000),
    )
    try:
        session.add(row)
        session.flush()
    except IntegrityError:
        session.rollback()
        # 并发分支已写入,  跳过
        return

    # 更新 bitable 状态
    bitable.last_pushed_at = int(time.time() * 1000)
    bitable.last_error = None
    bitable.last_error_at = None
    session.commit()
    print_info(
        f"[lark] push ok article={article.id} → bitable={bitable.id}({bitable.name}) "
        f"record_id={record_id or '(none)'}"
    )


def _record_failure(bitable: LarkBitable, session, exc: Exception) -> None:
    """单条 Bitable 推送失败时, 把错误信息写到 bitable 行,  不抛回。"""
    err_text = ""
    if isinstance(exc, LarkError):
        code = getattr(exc, "code", None)
        err_text = f"[{code}] {exc}" if code else str(exc)
    else:
        err_text = f"{type(exc).__name__}: {exc}"
    err_text = err_text[:1000]
    try:
        bitable.last_error = err_text
        bitable.last_error_at = int(time.time() * 1000)
        session.commit()
    except Exception:
        session.rollback()
        # 状态写不进去也只 log,  避免循环
        print_warning(f"[lark] 写 last_error 失败 bitable={bitable.id}: {exc}")
    print_warning(
        f"[lark] push failed bitable={bitable.id}({bitable.name}): {err_text}"
    )


# ---------- 重置（测试用） ----------

def _shutdown_executor_for_tests() -> None:
    """测试用: 关闭模块级 executor,  让 ``ThreadPoolExecutor.__del__`` 不报警。"""
    global _EXECUTOR
    if _EXECUTOR is not None:
        _EXECUTOR.shutdown(wait=False)
        _EXECUTOR = None