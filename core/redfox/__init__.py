"""Redfox 数据接口封装（基于官方 redfox-python-sdk）

本目录是对 PyPI `redfox-python-sdk` 的薄封装，保留与早期自定义实现
兼容的模块级 API（`get_account_info` / `search_user` / `query_work_list` /
`iter_work_list`），以便上层调用方无感知切换。

公众号正文仍由 `driver.wxarticle` 提供，本模块只负责账号信息与
作品列表的拉取。

使用示例::

    from core.redfox import get_account_info, search_user, query_work_list
    info = get_account_info(account="duhaoshu")
    # 关键词搜索（公众号发现场景）：每页 20 条
    results = search_user(keyword="十点读书", offset=0)
    works = query_work_list(bizInfo="MjM5MDMyMzg2MA==", offset=0)
"""

from .client import (
    ACCOUNT_INFO_PATH,
    ARTICLE_CONTENT_PATH,
    DEFAULT_BASE_URL,
    PAGE_SIZE,
    SEARCH_USER_PATH,
    SUCCESS_CODE,
    WORK_LIST_PATH,
    RedfoxError,
    close_all_clients,
    fetch_article_content,
    get_account_info,
    iter_work_list,
    query_work_list,
    search_user,
)

__all__ = [
    # 模块级常量
    "DEFAULT_BASE_URL",
    "ACCOUNT_INFO_PATH",
    "WORK_LIST_PATH",
    "SEARCH_USER_PATH",
    "ARTICLE_CONTENT_PATH",
    "SUCCESS_CODE",
    "PAGE_SIZE",
    # 函数
    "RedfoxError",
    "fetch_article_content",
    "get_account_info",
    "iter_work_list",
    "query_work_list",
    "search_user",
    "close_all_clients",
]
