from __future__ import annotations

import time
from typing import Any, Tuple

from core.config import cfg
from core.models.base import DATA_STATUS
from core.print import print_info, print_warning

# Playwright (web 模式) 单篇文章的重试次数 (含首次)。
# 重试此值仍空时,降级走 redfox SDK。
WEB_RETRY_TIMES = 3

# web 重试之间的退避基数 (秒),实际 sleep = _WEB_RETRY_BACKOFF * attempt。
_WEB_RETRY_BACKOFF = 2.0

# 历史兼容别名:旧版「连续失败 N 次切换兜底」的语义常量。
# 现已与 WEB_RETRY_TIMES 同义,保留供外部 import。
WEB_FAIL_THRESHOLD = WEB_RETRY_TIMES


def normalize_content_mode(mode: str | None = None) -> str:
    normalized = (mode or cfg.get("gather.content_mode", "web") or "web").strip().lower()
    if normalized not in {"web", "api"}:
        return "web"
    return normalized


def extract_origin_article_id(article_id: str, mp_id: str | None = None) -> str:
    if not article_id:
        return ""

    mp_prefix = (mp_id or "").replace("MP_WXS_", "").strip()
    if mp_prefix:
        prefixed = f"{mp_prefix}-"
        if article_id.startswith(prefixed):
            return article_id[len(prefixed):]

    return article_id


def build_article_url(article: Any) -> str:
    article_url = (getattr(article, "url", "") or "").strip()
    if article_url:
        return article_url

    origin_id = extract_origin_article_id(
        getattr(article, "id", ""),
        getattr(article, "mp_id", ""),
    )
    if not origin_id:
        return ""

    return f"https://mp.weixin.qq.com/s/{origin_id}"


def _fetch_with_web(url: str) -> str:
    from driver.wxarticle import Web

    result = Web.get_article_content(url) or {}
    return (result.get("content") or "").strip()


def _fetch_with_redfox(url: str) -> str:
    """通过 redfox SDK 实时接口拉取文章正文。"""
    from core.redfox import fetch_article_content as _redfox_fetch

    return _redfox_fetch(url)


def fetch_article_content(
    url: str,
    preferred_mode: str | None = None,  # noqa: ARG001 历史参数,不再用于切换
    web_fail_count: int = 0,  # noqa: ARG001 历史参数,不再用于切换
) -> Tuple[str, str, bool]:
    """按层级抓取公众号文章正文。

    抓取层级:
      * Tier 1: playwright (web 模式) 重试 ``WEB_RETRY_TIMES`` 次,
        每次失败做线性退避再重试,容忍偶发的网络/反爬抖动。
      * Tier 2: web 重试仍空时,降级走 redfox SDK 实时接口。
        这是当前唯一与 Playwright 无关的通道,可绕过微信反爬。
        当 ``gather.content_redfox_fallback=False`` 时此层跳过,
        直接返回 web 模式失败 (用于不想消耗 redfox 额度的场景)。

    旧版曾有 Tier 3 提前切 redfox 的逻辑 (依赖 ``web_fetch_fail_count``
    历史计数),但实测 Playwright 失败原因与计数相关性弱,
    且计数要等 3 次才升级,前两次会浪费在已知失败的通道上。
    故简化为「每篇文章都按 web→redfox 走到底」,不再用
    ``web_fail_count`` 切换逻辑。``web_failed_this_call`` 仍按
    本次是否实际尝试过 web 失败返回,供调用方累加计数用。

    Args:
        url: 文章 URL。
        preferred_mode: 历史参数保留,当前实现只走 web → redfox。
        web_fail_count: 历史参数保留,当前实现不再用于切换逻辑。

    Returns:
        ``(content, mode, web_failed_this_call)``:
          * ``content``: 正文(空字符串表示失败)。
          * ``mode``: 实际生效的抓取模式 (``web`` / ``redfox``)。
          * ``web_failed_this_call``: 本次调用是否实际尝试过 web 且失败
            (用于调用方决定是否累加 ``web_fetch_fail_count``)。
    """
    web_failed = False

    # Tier 1: playwright 重试 WEB_RETRY_TIMES 次
    for attempt in range(1, WEB_RETRY_TIMES + 1):
        try:
            content = _fetch_with_web(url)
        except Exception as exc:  # noqa: BLE001
            print_warning(
                f"fetch article content failed in web mode "
                f"(attempt {attempt}/{WEB_RETRY_TIMES}): {exc}"
            )
            content = ""
            web_failed = True
        else:
            if content == "DELETED":
                # DELETED 是有效信号,不计入失败
                return content, "web", web_failed
            if content:
                return content, "web", web_failed
            # 空内容 → 本次 web 失败
            web_failed = True

        # 最后一次失败不再 sleep
        if attempt < WEB_RETRY_TIMES:
            time.sleep(_WEB_RETRY_BACKOFF * attempt)

    # Tier 1 全部失败;是否降级 redfox 由配置项 ``gather.content_redfox_fallback``
    # 控制 (默认 True)。关闭时直接返回 web 模式失败,不消耗 redfox 额度。
    if not cfg.get("gather.content_redfox_fallback", True):
        print_warning(
            f"web 重试 {WEB_RETRY_TIMES} 次均失败,且 "
            f"gather.content_redfox_fallback=False,放弃: {url}"
        )
        return "", "web", web_failed

    # 降级 redfox
    print_warning(
        f"web 重试 {WEB_RETRY_TIMES} 次均失败,降级 redfox: {url}"
    )
    try:
        content = _fetch_with_redfox(url)
    except Exception as exc:  # noqa: BLE001
        print_warning(f"fetch article content failed in redfox mode: {exc}")
        return "", "redfox", web_failed

    if content == "DELETED":
        return content, "redfox", web_failed
    if content:
        return content, "redfox", web_failed
    return "", "redfox", web_failed


def sync_article_content(
    session,
    article: Any,
    preferred_mode: str | None = None,
    force: bool = False,
) -> Tuple[bool, str]:
    existing_content = (getattr(article, "content", "") or "").strip()
    if existing_content and not force:
        if getattr(article, "has_content", 0) == 0:
            print_info(f"article {article.id} already has content, skipping fetch")
            article.has_content = 1
            session.commit()
            session.refresh(article)
            return True, "cached"
        return False, "cached"

    article_url = build_article_url(article)
    if not article_url:
        print_warning(f"article {getattr(article, 'id', '')} has no valid url")
        return False, "missing_url"

    # 读取历史 web 失败次数;现在仅用于失败时累加计数,
    # 是否走 redfox 兜底完全由 ``fetch_article_content`` 内
    # ``gather.content_redfox_fallback`` 配置决定。
    web_fail_count = int(getattr(article, "web_fetch_fail_count", 0) or 0)
    content, mode, web_failed_this_call = fetch_article_content(
        article_url, preferred_mode, web_fail_count
    )

    if not content:
        # 抓取失败:仅当本次确实尝试过 web 时累加计数
        if web_failed_this_call and hasattr(article, "web_fetch_fail_count"):
            try:
                article.web_fetch_fail_count = web_fail_count + 1
                session.commit()
            except Exception:
                session.rollback()
        return False, mode

    try:
        if content == "DELETED":
            article.content = ""
            article.content_html = ""
            article.status = DATA_STATUS.DELETED
            article.has_content = 0
            session.commit()
            session.refresh(article)
            print_info(f"article {article.id} marked as deleted via {mode}")
            return True, mode

        from driver.wxarticle import Web
        from tools.fix import fix_html

        article.content = content
        article.content_html = fix_html(content)
        article.status = DATA_STATUS.ACTIVE
        article.has_content = 1
        if not (getattr(article, "description", "") or "").strip():
            article.description = Web.get_description(content)
        # 修正成功,重置失败计数
        if hasattr(article, 'fix_fail_count'):
            article.fix_fail_count = 0
        # 任意模式成功都重置 web 失败计数,给 web 一个"重新被信任"的机会
        if web_fail_count > 0 and hasattr(article, "web_fetch_fail_count"):
            article.web_fetch_fail_count = 0
        session.commit()
        session.refresh(article)
        print_info(f"article {article.id} content synced via {mode}")
        # 回调: 异步推到关联飞书多维表 (worker 内部检查 mp_id / enabled / 幂等)。
        # 这里 session 即将让出,  worker 会开自己的 session, 不冲突。
        try:
            from core.lark_push import lark_maybe_push

            lark_maybe_push(article.id)
        except Exception as exc:  # noqa: BLE001
            print_warning(f"submit lark push hook failed: {exc}")
        return True, mode
    except Exception:
        # 修正失败,增加失败计数
        if hasattr(article, 'fix_fail_count'):
            article.fix_fail_count = (article.fix_fail_count or 0) + 1
            try:
                session.commit()
            except Exception:
                session.rollback()
        session.rollback()
        raise
