"""公众号采集器入口。

自 1.6 起，本项目已移除对微信公众平台扫码授权的依赖。账号信息与作品
列表改由 ``core.redfox`` 提供的数据接口完成；公众号正文仍沿用
``driver.wxarticle``。

* ``WxGather``: 采集基类，封装 ``get_Articles`` 与 ``FillBack`` 行为。
* ``search_Biz``: 基于 redfox ``/searchUser`` 关键词搜索的公众号发现接口。
"""

from .base import WxGather
from .model import *  # noqa: F401,F403


ga = WxGather()


def search_Biz(kw: str = "", limit: int = 5, offset: int = 0):
    """公众号账号搜索的便捷封装。

    Args:
        kw: 搜索关键词（公众号名 / 描述 / 微信号）。
        limit: 返回条数上限（最多 100 条）。
        offset: 分页偏移量，每页 20 条。

    Returns:
        与旧 ``searchbiz`` 兼容的字典结构，包含 ``list`` / ``total`` / ``base_resp``。
    """
    return ga.search_Biz(kw, limit, offset)


if __name__ == "__main__":
    pass
