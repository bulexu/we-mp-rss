"""Redfox 数据接口封装

本目录封装了 redfox.hk 提供的新媒体数据接口，用以替代原项目对
微信公众号公众平台 (mp.weixin.qq.com) 扫码授权 + cgi-bin/* 内部接口的
依赖。公众号正文仍由 `driver.wxarticle` 提供，本模块只负责账号信息与
作品列表的拉取。

使用示例::

    from core.redfox import get_account_info, query_work_list
    info = get_account_info(account="duhaoshu")
    works = query_work_list(bizInfo="MjM5MDMyMzg2MA==", offset=0)
"""

from .client import (
    RedfoxClient,
    RedfoxError,
    get_account_info,
    query_work_list,
)

__all__ = [
    "RedfoxClient",
    "RedfoxError",
    "get_account_info",
    "query_work_list",
]
