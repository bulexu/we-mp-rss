"""公众号采集模型集合。

自 1.6 起，``MpsWeb`` 即基于 redfox 数据接口的采集器；``MpsAppMsg``、
``MpsApi`` 为历史兼容别名，等价于 ``MpsWeb``。
"""

from .app import MpsAppMsg  # noqa: F401
from .api import MpsApi  # noqa: F401
from .web import MpsWeb  # noqa: F401

__all__ = ["MpsWeb", "MpsAppMsg", "MpsApi"]
