"""兼容层：旧的 ``MpsAppMsg`` 模型已统一到 ``MpsWeb`` (redfox 数据源)。

自 1.6 起，``gather.model`` 配置项仅保留 ``web`` 一档；保留本类仅为
兼容历史 import，避免在某些未迁移的脚本里出现 ``ImportError``。
"""

from .web import MpsWeb  # noqa: F401


class MpsAppMsg(MpsWeb):
    """历史遗留类，已重定向到 ``MpsWeb``，行为完全一致。"""

    pass
