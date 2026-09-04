"""Redfox 数据接口客户端

对应文档：
    docs/redfox/获取公众号账号信息__(广域库)-KUQYSQNX.md
    docs/redfox/获取公众号账号作品列表_(广域库)-8IQD0BJC.md

提供以下能力：
    * get_account_info(account|wxId|bizInfo)         → 公众号账号信息
    * query_work_list(account|wxId|bizInfo, offset)  → 公众号作品列表

依赖：
    * 环境变量 REDFOX_API_KEY 必须存在（也可在 config.yaml 的
      redfox.api_key 中显式配置，但请勿硬编码）。
"""

from __future__ import annotations

import json
import os
import random
import time
from typing import Any, Dict, Iterable, Optional

import requests

from core.config import cfg
from core.print import print_error, print_warning
from core.redis_client import record_redfox_call


class RedfoxError(RuntimeError):
    """Redfox 接口返回非 2000 状态码时抛出。"""


# 简单浏览器 UA，避免被目标站点直接拒掉。
_REDFOX_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class RedfoxClient:
    """Redfox 数据接口薄封装。"""

    DEFAULT_BASE_URL = "https://redfox.hk"
    ACCOUNT_INFO_PATH = "/story/api/gzh/data/accountInfo"
    WORK_LIST_PATH = "/story/api/gzh/data/queryWorkList"
    SUCCESS_CODE = 2000

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = (
            api_key
            or cfg.get("redfox.api_key", "")
            or os.getenv("REDFOX_API_KEY", "")
            or ""
        ).strip()

        self.base_url = (
            base_url
            or cfg.get("redfox.base_url", "")
            or os.getenv("REDFOX_BASE_URL", "")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")

        try:
            self.timeout = float(
                timeout if timeout is not None else cfg.get("redfox.timeout", 15)
            )
        except (TypeError, ValueError):
            self.timeout = 15.0

        self.session = session or requests.Session()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise RedfoxError(
                "REDFOX_API_KEY 未配置，请在环境变量或 config.yaml 的 redfox.api_key 中设置"
            )
        return {
            "REDFOX_API_KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _REDFOX_UA,
        }

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None
        # 最多重试 1 次，避免瞬时网络抖动导致整个采集任务失败。
        started_at = time.monotonic()
        mp_id = self._extract_mp_id(payload)
        for attempt in range(2):
            try:
                resp = self.session.post(
                    url,
                    headers=self._headers(),
                    data=json.dumps(payload, ensure_ascii=False),
                    timeout=(5, self.timeout),
                )
            except requests.RequestException as exc:
                last_error = exc
                print_warning(f"Redfox 请求失败（attempt={attempt + 1}）: {exc}")
                time.sleep(random.uniform(0.5, 1.5))
                continue

            try:
                data = resp.json()
            except ValueError:
                print_error(
                    f"Redfox 返回非 JSON 响应: status={resp.status_code} body={resp.text[:300]}"
                )
                latency_ms = int((time.monotonic() - started_at) * 1000)
                self._record_call(
                    path=path,
                    mp_id=mp_id,
                    payload=payload,
                    code=0,
                    success=False,
                    latency_ms=latency_ms,
                    http_status=resp.status_code,
                    error_msg="non-json response",
                )
                raise RedfoxError("redfox 接口返回了非 JSON 数据")

            if resp.status_code >= 500:
                last_error = RedfoxError(
                    f"redfox 服务端错误 status={resp.status_code}"
                )
                print_warning(str(last_error))
                time.sleep(random.uniform(0.5, 1.5))
                continue

            latency_ms = int((time.monotonic() - started_at) * 1000)
            code = int(data.get("code", 0)) if isinstance(data, dict) else 0
            success = (
                isinstance(data, dict) and code == self.SUCCESS_CODE
            )
            if not success and isinstance(data, dict):
                err_msg = (
                    str(data.get("msg") or data.get("message") or "未知错误")
                )[:200]
            else:
                err_msg = ""
            self._record_call(
                path=path,
                mp_id=mp_id,
                payload=payload,
                code=code,
                success=success,
                latency_ms=latency_ms,
                http_status=resp.status_code,
                error_msg=err_msg,
            )
            return data

        # 全部重试失败
        latency_ms = int((time.monotonic() - started_at) * 1000)
        self._record_call(
            path=path,
            mp_id=mp_id,
            payload=payload,
            code=0,
            success=False,
            latency_ms=latency_ms,
            http_status=0,
            error_msg=str(last_error)[:200] if last_error else "unknown",
        )
        raise RedfoxError(f"redfox 请求失败: {last_error}")

    @staticmethod
    def _extract_mp_id(payload: Dict[str, Any]) -> str:
        """从请求体中尽量提取一个公众号标识，用于统计维度。"""
        if not isinstance(payload, dict):
            return ""
        for key in ("bizInfo", "wxId", "account"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _record_call(
        self,
        path: str,
        mp_id: str,
        payload: Dict[str, Any],
        code: int,
        success: bool,
        latency_ms: int,
        http_status: int,
        error_msg: str,
    ) -> None:
        """写入调用日志。失败不影响主流程。"""
        try:
            request_summary: Dict[str, Any] = {}
            for key in ("account", "wxId", "bizInfo", "offset", "sortType"):
                if key in payload and payload[key] is not None:
                    val = payload[key]
                    if isinstance(val, str) and len(val) > 200:
                        val = val[:200] + "..."
                    request_summary[key] = val
            record_redfox_call(
                endpoint=path,
                code=code,
                success=success,
                latency_ms=latency_ms,
                mp_id=mp_id,
                request=request_summary,
                error_msg=error_msg,
                http_status=http_status,
            )
        except Exception as exc:  # noqa: BLE001
            # 记录失败不应影响 redfox 调用本身。
            print_warning(f"记录 redfox 调用日志失败: {exc}")

    @staticmethod
    def _ensure_payload(
        account: Optional[str] = None,
        wxId: Optional[str] = None,
        bizInfo: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        payload = {
            "account": (account or "").strip() or None,
            "wxId": (wxId or "").strip() or None,
            "bizInfo": (bizInfo or "").strip() or None,
        }
        # 三个标识都为空时立即报错，避免无意义请求。
        if not any(payload.values()):
            raise RedfoxError(
                "必须提供 account / wxId / bizInfo 中的至少一个标识"
            )
        return payload

    @staticmethod
    def _unwrap(payload: Dict[str, Any]) -> Dict[str, Any]:
        """统一处理接口返回结构，失败时抛错。"""
        code = payload.get("code")
        if code != RedfoxClient.SUCCESS_CODE:
            msg = payload.get("msg") or payload.get("message") or "未知错误"
            raise RedfoxError(f"redfox 接口错误 code={code} msg={msg}")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise RedfoxError("redfox 接口 data 字段格式异常")
        return data

    # ------------------------------------------------------------------
    # 对外方法
    # ------------------------------------------------------------------
    def get_account_info(
        self,
        account: Optional[str] = None,
        wxId: Optional[str] = None,
        bizInfo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取公众号账号信息。

        三个入参至少传入一个。优先级与 redfox 服务端一致：
        wxId > bizInfo > account。
        """
        payload = self._ensure_payload(account=account, wxId=wxId, bizInfo=bizInfo)
        resp = self._post(self.ACCOUNT_INFO_PATH, payload)
        return self._unwrap(resp)

    def query_work_list(
        self,
        account: Optional[str] = None,
        wxId: Optional[str] = None,
        bizInfo: Optional[str] = None,
        offset: int = 0,
        sortType: str = "2",
    ) -> Dict[str, Any]:
        """获取公众号作品列表。

        Args:
            account/wxId/bizInfo: 公众号标识，三选一。
            offset: 分页偏移量，每页 +20。
            sortType: 排序方式，"0" 默认 / "2" 最新 / "4" 最热。
        """
        payload = self._ensure_payload(account=account, wxId=wxId, bizInfo=bizInfo)
        payload.update({"offset": int(offset), "sortType": str(sortType)})
        resp = self._post(self.WORK_LIST_PATH, payload)
        return self._unwrap(resp)

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
            max_pages: 最多拉取的页数（每页 page_size 条）。
            page_size: 每页条数，红狐接口固定为 20，这里仅做防御性
                校验，避免外部传错值时出现意外翻页。
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
            for item in items:
                yield item
            total = int(data.get("total") or 0)
            # 已读完所有数据，提前退出。
            if (page + 1) * page_size >= total:
                return


# ---------------------------------------------------------------------------
# 模块级便捷函数（避免到处实例化客户端）
# ---------------------------------------------------------------------------
_default_client: Optional[RedfoxClient] = None


def _get_default_client() -> RedfoxClient:
    global _default_client
    if _default_client is None:
        _default_client = RedfoxClient()
    return _default_client


def get_account_info(
    account: Optional[str] = None,
    wxId: Optional[str] = None,
    bizInfo: Optional[str] = None,
) -> Dict[str, Any]:
    return _get_default_client().get_account_info(
        account=account, wxId=wxId, bizInfo=bizInfo
    )


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
