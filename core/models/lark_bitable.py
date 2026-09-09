"""飞书多维表（Lark Bitable）配置 + 推送追踪模型。

两张表:
  * LarkBitable       — 每个 Bitable 一行,  字段映射 + 关联公众号
  * ArticleLarkPush   — 「已推送」追踪表, 复合主键 (article_id, bitable_id)

两张表都通过 SQLAlchemy ``Base.metadata.create_all()`` 自动建表,
与现有 AccessKey / CascadeNode 一致。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import BigInteger
from sqlalchemy.exc import SQLAlchemyError

from .base import Base, Column, String, Integer, DateTime, Boolean, Text


class LarkBitable(Base):
    """一个飞书多维表 (Bitable) 的推送配置。

    字段映射 ``field_mapping`` 存为 JSON 字符串,
    形如 ``{"title":"标题","url":"链接",...}``。

    关联 Feed id 列表 ``mp_ids`` 也是字符串,  存 JSON 数组,  形如
    ``["MP_WXS_abc","MP_WXS_xyz"]``。
    """
    __tablename__ = "lark_bitables"

    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    app_token = Column(String(255), nullable=False)
    table_id = Column(String(255), nullable=False)
    mp_ids = Column(Text, default="[]", nullable=False)
    field_mapping = Column(Text, default="{}", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    last_pushed_at = Column(BigInteger, nullable=True)
    last_error = Column(Text, nullable=True)
    last_error_at = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_mp_ids(self) -> List[str]:
        try:
            data = json.loads(self.mp_ids or "[]")
            return [str(x) for x in data] if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_mp_ids(self, ids: List[str]) -> None:
        cleaned = [str(x) for x in (ids or []) if x]
        self.mp_ids = json.dumps(cleaned, ensure_ascii=False)

    def get_field_mapping(self) -> Dict[str, str]:
        try:
            data = json.loads(self.field_mapping or "{}")
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_field_mapping(self, mapping: Dict[str, str]) -> None:
        if not mapping:
            self.field_mapping = "{}"
            return
        self.field_mapping = json.dumps(
            {str(k): str(v) for k, v in mapping.items()},
            ensure_ascii=False,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "app_token": self.app_token,
            "table_id": self.table_id,
            "mp_ids": self.get_mp_ids(),
            "field_mapping": self.get_field_mapping(),
            "enabled": bool(self.enabled),
            "last_pushed_at": self.last_pushed_at,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ArticleLarkPush(Base):
    """「这篇文章已推给该 Bitable」追踪记录。

    复合主键 ``(article_id, bitable_id)`` 保证一对一幂等,
    worker 命中即跳过推送。
    """
    __tablename__ = "article_lark_pushes"

    article_id = Column(String(255), primary_key=True)
    bitable_id = Column(String(255), primary_key=True)
    record_id = Column(String(255), nullable=True)
    pushed_at = Column(BigInteger, nullable=False)


# LHS 白名单: 字段映射允许的左侧 key 集合 (来自 Article / Feed)。
# 不在此白名单内的 key 在保存时直接 400 拒绝, 避免配置错时静默推送。
ALLOWED_FIELD_KEYS: frozenset = frozenset({
    "id",
    "title",
    "url",
    "description",
    "content",
    "pic_url",
    "publish_time",
    "mp_id",
    "mp_name",
    "art_type",
})


def validate_field_mapping(mapping: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """校验字段映射, 返回规范化后的 ``{LHS:RHS}`` 字典。

    抛出 ``ValueError`` 表示配置不合法;  ``ValueError`` 内携带明确原因。
    """
    if mapping is None:
        return {}
    if not isinstance(mapping, dict):
        raise ValueError("field_mapping 必须是对象 (dict)")
    normalized: Dict[str, str] = {}
    for lhs, rhs in mapping.items():
        if lhs not in ALLOWED_FIELD_KEYS:
            raise ValueError(
                f"field_mapping 包含不支持的 key: {lhs!r};"
                f"允许的 key: {sorted(ALLOWED_FIELD_KEYS)}"
            )
        if not isinstance(rhs, str) or not rhs.strip():
            raise ValueError(f"field_mapping[{lhs}] 必须是非空字符串")
        if lhs in normalized:
            raise ValueError(f"field_mapping 存在重复 key: {lhs}")
        normalized[lhs] = rhs.strip()
    return normalized