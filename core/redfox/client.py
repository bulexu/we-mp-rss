"""Redfox 数据接口客户端(基于官方 redfox-python-sdk)

对应文档:
    docs/redfox/获取公众号账号信息__(广域库)-KUQYSQNX.md
    docs/redfox/获取公众号账号作品列表_(广域库)-8IQD0BJC.md

本文件是对 `redfox` PyPI 包(https://pypi.org/project/redfox-python-sdk/)的薄封装,
保留与早期自定义实现兼容的模块级 API 形态(`get_account_info` / `search_user`
/ `query_work_list` / `iter_work_list`),以便上层 `core/wx/base.py` 与
`core/wx/model/web.py` 不必改动一行代码。

依赖:
    * 环境变量 REDFOX_API_KEY 必须存在(也可在 config.yaml 的
      redfox.api_key 中显式配置,但请勿硬编码)。
    * pip install redfox-python-sdk(已在 requirements.txt)。
"""

from __future__ import annotations

import os
import threading
import time
from html import escape as html_escape
from typing import Any, Dict, Iterable, List, Optional, Tuple

# 官方 SDK
from redfox import RedFoxClient
from redfox.exceptions import (
    RedFoxAPIError,
    RedFoxAuthError,
    RedFoxRateLimitError,
)

from core.config import cfg
from core.print import print_error, print_warning
from core.redis_client import record_redfox_call

# ---------------------------------------------------------------------------
# 异常兼容:保留旧名 `RedfoxError` 以便外部引用不受影响。
# ---------------------------------------------------------------------------

# SDK 抛出层级:RedFoxAuthError / RedFoxRateLimitError / RedFoxAPIError。
# 我们把 SDK 的 APIError 当作通用 RedfoxError,认证/限流错误也都视为 RedfoxError 的子类。
RedfoxError = RedFoxAPIError


# ---------------------------------------------------------------------------
# 模块级常量
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://redfox.hk"
ACCOUNT_INFO_PATH = "/story/api/gzh/data/accountInfo"  # 广域库
WORK_LIST_PATH = "/story/api/gzh/data/queryWorkList"   # 广域库
SEARCH_USER_PATH = "/story/api/gzh/data/searchUser"     # 广域库
ARTICLE_CONTENT_PATH = "/story/api/gzh/ability/temp/article/content"  # 实时拉取文章正文
SUCCESS_CODE = 2000
# searchUser / queryWorkList 单页固定 20 条
PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# 文章正文响应解析工具
# ---------------------------------------------------------------------------
#
# Redfox 实时正文端点 ``ARTICLE_CONTENT_PATH`` 返回的 data 形如::
#
#     {
#         "articleContent": "<p>...</p>",   # HTML 字符串,可能不含图片
#         "imageUrls": [                       # 补充的图片 URL 列表
#             "https://mmbiz.qpic.cn/...?wx_fmt=png&from=appmsg",
#             ...
#         ]
#     }
#
# 这两个字段是互补的: ``articleContent`` 给出排版后的正文 HTML,
# ``imageUrls`` 给出该篇文章的原图列表 (正文中未必能直接引用到)。
# 为保证图片不被丢失,本模块统一在返回前把 ``imageUrls`` 拼成
# ``<img>`` 标签追加到 ``articleContent`` 末尾。
# ---------------------------------------------------------------------------


def _extract_article_payload(data: Any) -> Tuple[str, List[str]]:
    """从 Redfox 响应 data 中解出 ``(articleContent, imageUrls)``。

    容错:任一字段缺失 / 类型不符都返回空值,而不是抛异常。
    过滤掉 ``imageUrls`` 中的非字符串与空字符串元素。
    """
    if not isinstance(data, dict):
        return "", []

    content = data.get("articleContent", "") or ""
    if not isinstance(content, str):
        content = ""

    raw_urls = data.get("imageUrls", []) or []
    if not isinstance(raw_urls, list):
        return content, []

    image_urls: List[str] = []
    for item in raw_urls:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                image_urls.append(stripped)
    return content, image_urls


def _append_image_urls(content: str, image_urls: List[str]) -> str:
    """把 ``imageUrls`` 拼成 ``<img>`` 标签追加到正文末尾。

    每个 URL 一行,自闭合标签;URL 经 ``html.escape`` 防注入。
    原 content 没有换行结尾时补一个换行,保证 ``<img>`` 不会粘在
    最后一个 HTML 元素后面影响渲染。
    """
    if not image_urls:
        return content

    img_tags = "\n".join(
        f'<img src="{html_escape(url, quote=True)}" />' for url in image_urls
    )
    sep = "" if content.endswith("\n") else "\n"
    return f"{content}{sep}{img_tags}"


class _RedfoxClient:
    """Redfox 数据接口薄封装(基于官方 SDK + 自带调用日志)。

    内部类(带下划线前缀),不导出。外部只需调用模块级函数
    (get_account_info / search_user / query_work_list / iter_work_list),
    共享通过 ``_get_default_client()`` 取得的单例。

    构造时从 config.yaml 的 `redfox.api_key` / `redfox.base_url` /
    `redfox.timeout` 取值,缺省回落到环境变量。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        cfg_key = cfg.get("redfox.api_key", "") if cfg else ""
        cfg_url = cfg.get("redfox.base_url", "") if cfg else ""
        cfg_timeout = cfg.get("redfox.timeout", 15) if cfg else 15

        self._api_key = (
            api_key
            or cfg_key
            or os.getenv("REDFOX_API_KEY", "")
        )
        self._base_url = (
            base_url
            or cfg_url
            or os.getenv("REDFOX_BASE_URL", "")
            or DEFAULT_BASE_URL
        )
        self._timeout = timeout or cfg_timeout or 15

        if not self._api_key:
            raise RedfoxError(
                "REDFOX_API_KEY 未配置,请在环境变量或 config.yaml 的 "
                "redfox.api_key 中设置"
            )

        # 官方 SDK 客户端(自带重试 / 退避 / 结构化异常)
        self._sdk = RedFoxClient(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=int(self._timeout),
        )

    # ------------------------------------------------------------------
    # 私有辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_mp_id(payload: Dict[str, Any]) -> str:
        """从请求参数里提取用于日志归因的公众号标识。"""
        if not isinstance(payload, dict):
            return ""
        for k in ("account", "wxId", "bizInfo", "keyword"):
            v = payload.get(k)
            if v:
                return str(v)[:128]
        return ""

    def _record_call(
        self,
        endpoint: str,
        success: bool,
        latency_ms: int,
        mp_id: str = "",
        request: Optional[Dict[str, Any]] = None,
        error_msg: str = "",
        code: int = 0,
        http_status: int = 0,
    ) -> None:
        """把每次调用写一条 Redis 统计日志,失败仅打印告警,不影响主流程。"""
        try:
            record_redfox_call(
                endpoint=endpoint,
                code=int(code or 0),
                success=success,
                latency_ms=int(latency_ms or 0),
                mp_id=mp_id,
                request=request or {},
                error_msg=error_msg,
                http_status=int(http_status or 0),
            )
        except Exception as exc:  # noqa: BLE001
            print_warning(f"记录 redfox 调用日志失败: {exc}")

    def _sdk_call(
        self,
        endpoint: str,
        request_payload: Dict[str, Any],
        sdk_op,
    ) -> Dict[str, Any]:
        """统一的 SDK 调用入口:计时 + 异常归一 + 日志记录。"""
        started = time.time()
        mp_id = self._extract_mp_id(request_payload)
        try:
            data = sdk_op()
        except RedFoxAuthError as e:
            latency = int((time.time() - started) * 1000)
            self._record_call(
                endpoint=endpoint,
                success=False,
                latency_ms=latency,
                mp_id=mp_id,
                request=request_payload,
                error_msg=f"auth: {e}",
                code=int(getattr(e, "code", 0) or 0),
                http_status=401,
            )
            raise RedfoxError(f"Redfox 鉴权失败: {e}") from e
        except RedFoxRateLimitError as e:
            latency = int((time.time() - started) * 1000)
            self._record_call(
                endpoint=endpoint,
                success=False,
                latency_ms=latency,
                mp_id=mp_id,
                request=request_payload,
                error_msg=f"rate_limit: {e}",
                code=int(getattr(e, "code", 0) or 0),
                http_status=429,
            )
            raise RedfoxError(f"Redfox 频率限制: {e}") from e
        except RedFoxAPIError as e:
            latency = int((time.time() - started) * 1000)
            self._record_call(
                endpoint=endpoint,
                success=False,
                latency_ms=latency,
                mp_id=mp_id,
                request=request_payload,
                error_msg=str(e),
                code=int(getattr(e, "code", 0) or 0),
            )
            raise RedfoxError(f"Redfox 业务错误: {e}") from e
        except Exception as e:  # noqa: BLE001
            latency = int((time.time() - started) * 1000)
            print_error(f"Redfox 调用异常: {e}")
            self._record_call(
                endpoint=endpoint,
                success=False,
                latency_ms=latency,
                mp_id=mp_id,
                request=request_payload,
                error_msg=f"exception: {e}",
            )
            raise RedfoxError(f"Redfox 调用异常: {e}") from e

        latency = int((time.time() - started) * 1000)
        # SDK 已自动校验 code=2000 并解包 data,这里只是拿到 dict
        data_dict = data if isinstance(data, dict) else {}
        self._record_call(
            endpoint=endpoint,
            success=True,
            latency_ms=latency,
            mp_id=mp_id,
            request=request_payload,
            code=SUCCESS_CODE,
        )
        return data_dict

    # ------------------------------------------------------------------
    # 业务方法
    # ------------------------------------------------------------------

    def get_account_info(
        self,
        account: Optional[str] = None,
        wxId: Optional[str] = None,
        bizInfo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取公众号账号信息(广域库)。

        三个入参至少传入一个。优先级与 SDK 一致:
        wxId > bizInfo > account。
        """
        # SDK 严格要求至少传一个
        if not any([account, wxId, bizInfo]):
            raise RedfoxError("get_account_info: account/wxId/bizInfo 至少传一个")

        return self._sdk_call(
            endpoint=ACCOUNT_INFO_PATH,
            request_payload={
                "account": account or "",
                "wxId": wxId or "",
                "bizInfo": bizInfo or "",
            },
            sdk_op=lambda: self._sdk.wechat.get_account_wide(
                account=account,
                wx_id=wxId,
                biz_info=bizInfo,
            ),
        )

    def search_user(
        self,
        keyword: str = "",
        offset: int = 0,
    ) -> Dict[str, Any]:
        """按关键词模糊搜索公众号账号(广域库)。

        与 ``get_account_info`` 的「精确查找单个公众号」不同:本接口返回与
        关键词相关的多条结果,适合订阅前的账号发现场景。

        Returns:
            解包后的 ``data`` 字段,形如::

                {
                    "list": [
                        {
                            "account": "duhaoshu",
                            "accountName": "十点读书",
                            "avatarUrl": "...",
                            "bizInfo": "MjM5MDMyMzg2MA==",
                            "description": "...",
                            "qrcodeUrl": "...",
                            "verifyInfo": "...",
                            "wxId": "gh_5c7e8b7f586b",
                            "updateTime": "...",
                        },
                        ...
                    ],
                    "total": 941407,
                }
        """
        kw = (keyword or "").strip()
        if not kw:
            raise RedfoxError("searchUser: keyword 不能为空")
        try:
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            offset = 0

        return self._sdk_call(
            endpoint=SEARCH_USER_PATH,
            request_payload={"keyword": kw, "offset": offset},
            sdk_op=lambda: self._sdk.wechat.search_users_wide(
                keyword=kw, offset=offset
            ),
        )

    def query_work_list(
        self,
        account: Optional[str] = None,
        wxId: Optional[str] = None,
        bizInfo: Optional[str] = None,
        offset: int = 0,
        sortType: str = "2",
    ) -> Dict[str, Any]:
        """获取公众号作品列表(广域库)。

        Args:
            account/wxId/bizInfo: 公众号标识,三选一。
            offset: 分页偏移量,每页 +20。
            sortType: 排序方式,"0" 默认 / "2" 最新 / "4" 最热。
        """
        if not any([account, wxId, bizInfo]):
            raise RedfoxError("query_work_list: account/wxId/bizInfo 至少传一个")
        try:
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            offset = 0

        return self._sdk_call(
            endpoint=WORK_LIST_PATH,
            request_payload={
                "account": account or "",
                "wxId": wxId or "",
                "bizInfo": bizInfo or "",
                "offset": offset,
                "sortType": str(sortType),
            },
            sdk_op=lambda: self._sdk.wechat.get_user_works_wide(
                account=account,
                wx_id=wxId,
                biz_info=bizInfo,
                offset=offset,
                sort_type=str(sortType),
            ),
        )

    def iter_work_list(
        self,
        account: Optional[str] = None,
        wxId: Optional[str] = None,
        bizInfo: Optional[str] = None,
        max_pages: int = 1,
        sortType: str = "2",
        page_size: int = 20,
    ) -> Iterable[Dict[str, Any]]:
        """按页迭代公众号作品列表。

        Args:
            max_pages: 最多拉取的页数(每页 page_size 条)。
            page_size: 每页条数,红狐接口固定为 20,这里仅做防御性
                校验,避免外部传错值时出现意外翻页。
        """
        if page_size <= 0:
            page_size = 20
        for page in range(max(1, max_pages)):
            data = self.query_work_list(
                account=account,
                wxId=wxId,
                bizInfo=bizInfo,
                offset=page * page_size,
                sortType=sortType,
            )
            items = data.get("list") or []
            if not items:
                return
            yield from items

    def fetch_article_content(self, article_url: str) -> str:
        """通过红狐实时接口拉取公众号文章正文。

        对应端点: ``POST /story/api/gzh/ability/temp/article/content``
        请求体:   ``{"articleUrl": "<mp.weixin.qq.com/s/...>"}``

        注意:
          * 该端点不在 SDK 已封装的 ``wechat`` 端点中。
          * 响应 ``code=200`` 而非 SDK 默认校验的 ``code=2000``,
            因此 SDK 会把它当业务错误抛出。本方法捕获 ``RedFoxAPIError``,
            并对 ``exc.response.code == 200`` 这种特例按成功处理,
            不修改 SDK 本身(SDK 是三方包,改它风险大)。
          * 仍然走 SDK 的 ``post()`` -> ``request()`` 链路,享受
            自动鉴权头 / 超时 / 5xx & 429 指数退避重试。
          * 响应 data 同时含 ``articleContent`` (正文 HTML) 和
            ``imageUrls`` (补充原图列表),本方法会把后者拼成
            ``<img>`` 标签追加到正文末尾,避免图片丢失。

        Returns:
            文章正文 HTML (已 strip; ``imageUrls`` 已合并为 ``<img>``)。
            失败抛出 ``RedfoxError``。
        """
        if not article_url:
            raise RedfoxError("article_url 不能为空")
        url = str(article_url).strip()
        if not url:
            raise RedfoxError("article_url 不能为空")
        request_payload = {"articleUrl": url}

        started = time.time()
        mp_id = url[:128]  # 用于日志归因(短前缀避免 Redis 体积过大)

        try:
            # 正常情况:SDK 已解包 data(响应 code=2000 时走这里)
            data = self._sdk.post(ARTICLE_CONTENT_PATH, request_payload)
        except RedFoxAuthError as exc:
            latency = int((time.time() - started) * 1000)
            self._record_call(
                endpoint=ARTICLE_CONTENT_PATH,
                success=False,
                latency_ms=latency,
                mp_id=mp_id,
                request=request_payload,
                error_msg=f"auth: {exc}",
                code=401,
                http_status=401,
            )
            raise RedfoxError(f"Redfox 鉴权失败: {exc}") from exc
        except RedFoxRateLimitError as exc:
            latency = int((time.time() - started) * 1000)
            self._record_call(
                endpoint=ARTICLE_CONTENT_PATH,
                success=False,
                latency_ms=latency,
                mp_id=mp_id,
                request=request_payload,
                error_msg=f"rate_limit: {exc}",
                code=429,
                http_status=429,
            )
            raise RedfoxError(f"Redfox 频率限制: {exc}") from exc
        except RedFoxAPIError as exc:
            # 特例:本端点响应 code=200,SDK 当成业务错误抛出,但
            # exc.response 里有完整 payload,这里手动解出当成功处理。
            response_payload = getattr(exc, "response", None) or {}
            if isinstance(response_payload, dict) and response_payload.get("code") == 200:
                data = response_payload.get("data") or {}
            else:
                latency = int((time.time() - started) * 1000)
                self._record_call(
                    endpoint=ARTICLE_CONTENT_PATH,
                    success=False,
                    latency_ms=latency,
                    mp_id=mp_id,
                    request=request_payload,
                    error_msg=str(exc),
                    code=int(getattr(exc, "code", 0) or 0),
                )
                raise RedfoxError(f"Redfox 业务错误: {exc}") from exc

        # articleContent + imageUrls 合并:解析两个字段,把图片拼成 <img>
        # 标签追加到正文末尾(详情见模块级 _extract_article_payload / _append_image_urls)。
        content, image_urls = _extract_article_payload(data)
        content = _append_image_urls(content, image_urls)

        latency = int((time.time() - started) * 1000)
        self._record_call(
            endpoint=ARTICLE_CONTENT_PATH,
            success=True,
            latency_ms=latency,
            mp_id=mp_id,
            request=request_payload,
            code=200,
        )
        return content.strip()


# ---------------------------------------------------------------------------
# 模块级便捷函数(保留旧用法,避免改动调用方)
# ---------------------------------------------------------------------------
#
# 为什么是线程局部池而不是模块级单例:
#   ``redfox.RedFoxClient`` 内部持有 ``httpx.Client``,而 ``httpx.Client``
#   不是线程安全的(官方文档明示)。当 ``TaskQueue`` 后台线程把一次
#   MessageTask 的多个 feed 用 ``ThreadPoolExecutor`` 并发跑时,如果共用
#   一个 ``_RedfoxClient``,多个线程会同时调用 ``self._client.request``,
#   轻则请求/响应错乱,重则抛 ``RuntimeError`` / 数据损坏。
#
# 解决方案:按 ``threading.get_ident()`` 缓存客户端,每个工作线程持有
# 独立的 ``httpx.Client``,互不干扰。
# ---------------------------------------------------------------------------

_local_clients: dict[int, "_RedfoxClient"] = {}
_clients_lock = threading.Lock()


def _get_default_client() -> _RedfoxClient:
    """按线程懒初始化并缓存 ``_RedfoxClient``。

    同一线程内多次调用只初始化一次;不同线程各自持有独立实例。
    """
    tid = threading.get_ident()
    client = _local_clients.get(tid)
    if client is not None:
        return client
    with _clients_lock:
        # 双重检查:可能在上锁过程中其它线程已为本 tid 创建
        client = _local_clients.get(tid)
        if client is None:
            client = _RedfoxClient()
            _local_clients[tid] = client
    return client


def close_all_clients() -> None:
    """关闭并清空所有缓存的客户端(主要用于优雅退出 / 测试)。

    会调用每个客户端底层 ``httpx.Client.close()`` 释放连接池。
    """
    with _clients_lock:
        clients = list(_local_clients.values())
        _local_clients.clear()
    for client in clients:
        try:
            client.close()
        except Exception as exc:  # noqa: BLE001
            print_warning(f"关闭 redfox 客户端失败: {exc}")


def get_account_info(
    account: Optional[str] = None,
    wxId: Optional[str] = None,
    bizInfo: Optional[str] = None,
) -> Dict[str, Any]:
    return _get_default_client().get_account_info(
        account=account, wxId=wxId, bizInfo=bizInfo
    )


def search_user(keyword: str = "", offset: int = 0) -> Dict[str, Any]:
    return _get_default_client().search_user(keyword=keyword, offset=offset)


def query_work_list(
    account: Optional[str] = None,
    wxId: Optional[str] = None,
    bizInfo: Optional[str] = None,
    offset: int = 0,
    sortType: str = "2",
) -> Dict[str, Any]:
    return _get_default_client().query_work_list(
        account=account, wxId=wxId, bizInfo=bizInfo, offset=offset, sortType=sortType
    )


def iter_work_list(
    account: Optional[str] = None,
    wxId: Optional[str] = None,
    bizInfo: Optional[str] = None,
    max_pages: int = 1,
    sortType: str = "2",
    page_size: int = 20,
) -> Iterable[Dict[str, Any]]:
    """模块级便捷函数:按页迭代作品列表。"""
    return _get_default_client().iter_work_list(
        account=account,
        wxId=wxId,
        bizInfo=bizInfo,
        max_pages=max_pages,
        sortType=sortType,
        page_size=page_size,
    )


def fetch_article_content(article_url: str) -> str:
    """模块级便捷函数:实时拉取公众号文章正文(走 redfox SDK)。

    对应端点: ``POST /story/api/gzh/ability/temp/article/content``
    """
    return _get_default_client().fetch_article_content(article_url)


__all__ = [
    "RedfoxError",
    "get_account_info",
    "search_user",
    "query_work_list",
    "iter_work_list",
    "fetch_article_content",
    "close_all_clients",
    # 模块级常量
    "DEFAULT_BASE_URL",
    "ACCOUNT_INFO_PATH",
    "WORK_LIST_PATH",
    "SEARCH_USER_PATH",
    "ARTICLE_CONTENT_PATH",
    "SUCCESS_CODE",
    "PAGE_SIZE",
]