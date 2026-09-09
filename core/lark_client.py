"""飞书 OpenAPI 客户端（最小可用版）。

只覆盖本项目需要的 3 个接口:
  1. ``POST /open-apis/auth/v3/tenant_access_token/internal`` — 拿 tenant_access_token
  2. ``POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create`` — 批量建记录
  3. ``GET  /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields`` — 拉表字段清单 (用于「验证可达」)

tenant_access_token 在进程内按 app_id 缓存,  剩余有效期 < 60s 时强制刷新。
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.config import cfg
from core.print import print_warning, print_info

DEFAULT_TIMEOUT = 15
LARK_BASE_URL = "https://open.feishu.cn"
TOKEN_URL = f"{LARK_BASE_URL}/open-apis/auth/v3/tenant_access_token/internal"
BITABLE_BASE = f"{LARK_BASE_URL}/open-apis/bitable/v1/apps"


class LarkError(RuntimeError):
    """飞书 OpenAPI 调用失败时抛出。"""

    def __init__(self, message: str, code: Optional[int] = None, raw: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.raw = raw or {}


class LarkClient:
    """飞书 OpenAPI 客户端。

    用法::

        client = LarkClient(app_id, app_secret)
        client.list_fields(app_token, table_id)
        client.batch_create_records(app_token, table_id, [{"fields": {...}}, ...])

    ``app_id`` / ``app_secret`` 取自 ``cfg.lark``。
    """

    def __init__(self, app_id: str, app_secret: str, timeout: Optional[int] = None):
        self.app_id = (app_id or "").strip()
        self.app_secret = (app_secret or "").strip()
        self.timeout = int(timeout or cfg.get("lark.timeout", DEFAULT_TIMEOUT) or DEFAULT_TIMEOUT)
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._token_lock = threading.Lock()

    # ---------- 鉴权 ----------

    def _fetch_tenant_access_token(self) -> Tuple[str, int]:
        """调一次 /tenant_access_token/internal, 返回 ``(token, expires_at_unix)``。"""
        resp = requests.post(
            TOKEN_URL,
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=self.timeout,
        )
        data = _parse_json(resp)
        if not isinstance(data, dict):
            raise LarkError("飞书返回非 JSON 或非 dict", raw={"body": resp.text[:200]})
        if data.get("code") != 0:
            raise LarkError(
                f"获取 tenant_access_token 失败: {data.get('msg') or data.get('code')}",
                code=data.get("code"),
                raw=data,
            )
        token = data.get("tenant_access_token") or ""
        expire = int(data.get("expire") or 7200)
        if not token:
            raise LarkError("飞书返回空 tenant_access_token", raw=data)
        return token, time.time() + expire

    def get_tenant_access_token(self) -> str:
        """拿当前可用的 tenant_access_token, 过期自动刷新。"""
        with self._token_lock:
            if self._token and time.time() < self._token_expires_at - 60:
                return self._token
            token, expires_at = self._fetch_tenant_access_token()
            self._token = token
            self._token_expires_at = expires_at
            return token

    # ---------- Bitable ----------

    def _bitable_request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        token = self.get_tenant_access_token()
        url = f"{BITABLE_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        resp = requests.request(
            method=method,
            url=url,
            json=json_body,
            headers=headers,
            timeout=self.timeout,
        )
        data = _parse_json(resp)
        if not isinstance(data, dict):
            raise LarkError(f"飞书返回非 JSON 或非 dict ({path})", raw={"body": resp.text[:200]})
        if data.get("code") != 0:
            raise LarkError(
                f"飞书接口失败 ({method} {path}): {data.get('msg') or data.get('code')}",
                code=data.get("code"),
                raw=data,
            )
        return data

    def list_fields(self, app_token: str, table_id: str) -> List[Dict[str, Any]]:
        """列出 Bitable 表里所有字段定义。

        返回 ``[{"field_id":..., "field_name":..., "type":..., ...}, ...]``。
        """
        items: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        while True:
            path = f"/{app_token}/tables/{table_id}/fields"
            qs = f"?page_size=100" + (f"&page_token={page_token}" if page_token else "")
            data = self._bitable_request("GET", path + qs)
            payload = data.get("data") or {}
            items.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break
        return items

    def batch_create_records(
        self,
        app_token: str,
        table_id: str,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """``batch_create`` 创建多条记录。

        ``records`` 每项形如 ``{"fields": {"标题": "...", "摘要": "..."}}``。
        返回 Lark 返回的 ``records`` 数组 (含每条的 ``record_id`` 等)。
        """
        if not records:
            return []
        path = f"/{app_token}/tables/{table_id}/records/batch_create"
        data = self._bitable_request("POST", path, json_body={"records": records})
        return (data.get("data") or {}).get("records") or []


def _parse_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None


# ---- 模块级单例 ----

_client: Optional[LarkClient] = None
_client_lock = threading.Lock()


def get_lark_client() -> Optional[LarkClient]:
    """根据 ``cfg.lark`` 拿到（或惰性构造）模块级 LarkClient。

    若 ``app_id`` 或 ``app_secret`` 缺失，返回 ``None``。
    """
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        app_id = (cfg.get("lark.app_id", "") or "").strip()
        app_secret = (cfg.get("lark.app_secret", "") or "").strip()
        if not app_id or not app_secret:
            return None
        timeout = cfg.get("lark.timeout", DEFAULT_TIMEOUT)
        _client = LarkClient(app_id=app_id, app_secret=app_secret, timeout=timeout)
        return _client


def reset_lark_client() -> None:
    """测试用：重置模块级客户端单例。"""
    global _client
    with _client_lock:
        _client = None