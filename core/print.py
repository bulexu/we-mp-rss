"""统一的彩色打印工具，日志级别受 ``LOG_LEVEL`` / ``log.level`` 控制。

级别映射（与 Python ``logging`` 对齐）:
    * ``print_debug``   -> DEBUG
    * ``print_info``    -> INFO
    * ``print_success`` -> INFO（业务成功事件视作普通信息）
    * ``print_warning`` -> WARNING
    * ``print_error``   -> ERROR
    * ``print_critical``-> CRITICAL

通过 ``LOG_LEVEL`` 环境变量或 ``config.yaml`` 的 ``log.level`` 字段控制：

    LOG_LEVEL=DEBUG    # 看全部
    LOG_LEVEL=INFO     # 默认
    LOG_LEVEL=WARNING  # 只看警告/错误
    LOG_LEVEL=ERROR    # 只看错误
    LOG_LEVEL=CRITICAL # 几乎全部静默
"""

import logging
import os
import sys

from colorama import init, Fore, Back, Style

if os.name == "posix":
    os.environ["TERM"] = "xterm-256color"
init()


# 延迟导入，避免在 import 阶段就要求 ``cfg`` 已初始化
_LOG_LEVEL_GETTER = None


def _get_level() -> int:
    """惰性获取当前日志级别，避免 ``core.print`` 早于 ``core.config`` 加载。"""
    global _LOG_LEVEL_GETTER
    if _LOG_LEVEL_GETTER is None:
        try:
            from core.log import get_log_level
            _LOG_LEVEL_GETTER = get_log_level
        except Exception:
            # 配置尚未加载完成时退回 INFO，保证早期日志不会丢
            _LOG_LEVEL_GETTER = lambda: logging.INFO  # noqa: E731
    return _LOG_LEVEL_GETTER()


def _is_enabled(threshold: int) -> bool:
    """``threshold`` 是否达到当前 LOG_LEVEL。"""
    # 当 LOG_LEVEL 未设置或解析失败时，_get_level 也会回退到 INFO
    return _get_level() <= threshold


class ColorPrinter:
    """带颜色输出的打印工具类"""

    def __init__(self):
        self._fore_color = ""
        self._back_color = ""
        self._style = ""
        self._text = ""

    def _reset(self):
        self._fore_color = ""
        self._back_color = ""
        self._style = ""
        return self

    def red(self):
        self._fore_color = Fore.RED
        return self

    def green(self):
        self._fore_color = Fore.GREEN
        return self

    def yellow(self):
        self._fore_color = Fore.YELLOW
        return self

    def blue(self):
        self._fore_color = Fore.BLUE
        return self

    def magenta(self):
        self._fore_color = Fore.MAGENTA
        return self

    def cyan(self):
        self._fore_color = Fore.CYAN
        return self

    def white(self):
        self._fore_color = Fore.WHITE
        return self

    def black(self):
        self._fore_color = Fore.BLACK
        return self

    def bg_red(self):
        self._back_color = Back.RED
        return self

    def bg_green(self):
        self._back_color = Back.GREEN
        return self

    def bg_yellow(self):
        self._back_color = Back.YELLOW
        return self

    def bg_blue(self):
        self._back_color = Back.BLUE
        return self

    def bg_white(self):
        self._back_color = Back.WHITE
        return self

    def bold(self):
        self._style = Style.BRIGHT
        return self

    def dim(self):
        self._style = Style.DIM
        return self

    def normal(self):
        self._style = Style.NORMAL
        return self

    def print(self, text, end="\n", file=sys.stdout):
        formatted = (
            f"{self._style}{self._back_color}{self._fore_color}"
            f"{text}{Style.RESET_ALL}"
        )
        print(formatted, end=end, file=file)
        self._reset()
        return self

    # ---- 快捷方法（不绑定日志级别，永远输出）----
    def print_red(self, text, **kwargs):
        self.red().print(text, **kwargs)

    def print_green(self, text, **kwargs):
        self.green().print(text, **kwargs)

    def print_yellow(self, text, **kwargs):
        self.yellow().print(text, **kwargs)

    def print_blue(self, text, **kwargs):
        self.blue().print(text, **kwargs)

    def print_magenta(self, text, **kwargs):
        self.magenta().print(text, **kwargs)

    def print_cyan(self, text, **kwargs):
        self.cyan().print(text, **kwargs)

    # ---- 绑定日志级别的方法（受 LOG_LEVEL 控制）----
    def print_debug(self, text, **kwargs):
        if not _is_enabled(logging.DEBUG):
            return
        self.cyan().print(text, **kwargs)

    def print_info(self, text, **kwargs):
        if not _is_enabled(logging.INFO):
            return
        self.blue().print(text, **kwargs)

    def print_success(self, text, **kwargs):
        # 业务成功事件视作 INFO 级别
        if not _is_enabled(logging.INFO):
            return
        self.green().bold().print(text, **kwargs)

    def print_warning(self, text, **kwargs):
        if not _is_enabled(logging.WARNING):
            return
        self.yellow().bold().print(text, **kwargs)

    def print_error(self, text, **kwargs):
        if not _is_enabled(logging.ERROR):
            return
        self.red().bold().print(text, **kwargs)

    def print_critical(self, text, **kwargs):
        # CRITICAL 永远输出，避免关键错误被静默
        self.red().bold().bg_white().print(text, **kwargs)


printer = ColorPrinter()


def print_debug(text, **kwargs):
    printer.print_debug(text, **kwargs)


def print_info(text, **kwargs):
    printer.print_info(text, **kwargs)


def print_success(text, **kwargs):
    printer.print_success(text, **kwargs)


def print_warning(text, **kwargs):
    printer.print_warning(text, **kwargs)


def print_error(text, **kwargs):
    printer.print_error(text, **kwargs)


def print_critical(text, **kwargs):
    printer.print_critical(text, **kwargs)
