"""兼容层：旧的 ``MpsApi`` 模型已统一到 ``MpsWeb`` (redfox 数据源)。

保留本类仅为兼容历史 import (``from core.wx.model.api import MpsApi``)；
实际行为完全委托给 ``MpsWeb``。
"""

from .web import MpsWeb  # noqa: F401


class MpsApi(MpsWeb):
    """历史遗留类，已重定向到 ``MpsWeb``。"""

    pass
