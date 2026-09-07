from __future__ import annotations

from typing import Any, Tuple

from core.config import cfg
from core.models.base import DATA_STATUS
from core.print import print_info, print_warning

# web 抓取连续失败此值后,降级走 redfox 接口
# (Article.web_fetch_fail_count >= WEB_FAIL_THRESHOLD 触发)
WEB_FAIL_THRESHOLD = 3


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


def _fetch_with_api(url: str) -> str:
    from core.wx.model.api import MpsApi

    fetcher = MpsApi()
    return (fetcher.content_extract(url) or "").strip()


def _fetch_with_redfox(url: str) -> str:
    """通过 redfox SDK 实时接口拉取文章正文。"""
    from core.redfox import fetch_article_content as _redfox_fetch

    return _redfox_fetch(url)


def fetch_article_content(
    url: str,
    preferred_mode: str | None = None,
    web_fail_count: int = 0,
) -> Tuple[str, str, bool]:
    """按层级抓取公众号文章正文。

    抓取层级:
      * Tier 3 (NEW): 当 ``web_fail_count >= WEB_FAIL_THRESHOLD`` 时,先走
        redfox SDK,失败再降级 web/api。
      * Tier 1+2: ``preferred_mode`` (默认 ``web``) + 兜底(另一个),与旧逻辑一致。

    Args:
        url: 文章 URL。
        preferred_mode: 首选抓取模式 (``web`` / ``api``),None 取
            ``gather.content_mode`` 配置。
        web_fail_count: 该文章 web 抓取历史失败次数。>= ``WEB_FAIL_THRESHOLD``
            触发 Tier 3 降级。

    Returns:
        ``(content, mode, web_failed_this_call)``:
          * ``content``: 正文(空字符串表示失败)。
          * ``mode``: 实际生效的抓取模式 (``web`` / ``api`` / ``redfox``)。
          * ``web_failed_this_call``: 本次调用是否实际尝试过 web 且失败
            (用于调用方决定是否累加 ``web_fetch_fail_count``)。
    """
    web_failed = False

    # Tier 3: web 连续失败达到阈值时,先走 redfox 实时接口
    if web_fail_count >= WEB_FAIL_THRESHOLD:
        try:
            content = _fetch_with_redfox(url)
            if content == "DELETED":
                return content, "redfox", web_failed
            if content:
                return content, "redfox", web_failed
        except Exception as exc:
            print_warning(f"fetch article content failed in redfox mode: {exc}")
        # redfox 没拿到,继续走下面的 web/api 兜底(也会把 web_failed 算上)

    mode = normalize_content_mode(preferred_mode)
    modes = [mode] + [item for item in ("web", "api") if item != mode]

    for current_mode in modes:
        try:
            if current_mode == "api":
                content = _fetch_with_api(url)
            else:
                content = _fetch_with_web(url)
        except Exception as exc:
            print_warning(f"fetch article content failed in {current_mode} mode: {exc}")
            if current_mode == "web":
                web_failed = True
            continue

        if content == "DELETED":
            # DELETED 是有效信号,不计入失败
            return content, current_mode, web_failed
        if content:
            return content, current_mode, web_failed
        # 空内容 -> 视为本模式抓取失败
        if current_mode == "web":
            web_failed = True

    return "", mode, web_failed


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

    # 读取历史 web 失败次数,用于决定本次是否走 redfox 兜底
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
