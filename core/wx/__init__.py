"""公众号采集器入口。

自 1.6 起，本项目已移除对微信公众平台扫码授权的依赖。账号信息与作品
列表改由 ``core.redfox`` 提供的数据接口完成；公众号正文仍沿用
``driver.wxarticle``。

* ``WxGather``: 采集基类，封装 ``get_Articles`` 与 ``FillBack`` 行为。
* ``search_Biz``: 基于 redfox 的公众号账号信息查询。
"""

from .base import WxGather
from .model import *  # noqa: F401,F403


ga = WxGather()


def search_Biz(kw: str = "", limit: int = 5, offset: int = 0):
    """公众号账号信息查询的便捷封装。

    Args:
        kw: 公众号名称或微信号。
        limit: 返回条数上限（redfox 单次最多返回 1 条）。
        offset: 兼容旧接口语义，redfox 接口暂不支持 offset。

    Returns:
        与旧 ``searchbiz`` 兼容的字典结构。
    """
    return ga.search_Biz(kw, limit, offset)


if __name__ == "__main__":
    pass
