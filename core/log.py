import os
import logging
from logging.handlers import RotatingFileHandler

try:
    import colorlog
except ImportError:
    colorlog = None

from core.config import cfg


_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "FATAL": logging.CRITICAL,
}


def _resolve_level() -> int:
    """根据 ``LOG_LEVEL`` 环境变量 / ``log.level`` 配置解析日志级别。

    优先级:
      1. 进程环境变量 ``LOG_LEVEL``（便于本地调试，无需改配置文件）
      2. ``config.yaml`` 的 ``log.level``
      3. 默认 ``INFO``
    """
    raw = (
        os.getenv("LOG_LEVEL")
        or cfg.get("log.level", "")
        or "INFO"
    )
    return _LEVELS.get(str(raw).strip().upper(), logging.INFO)


def get_log_level() -> int:
    """供其它模块（``core.print`` 等）查询当前生效的日志级别。

    每次调用都重新解析环境变量，便于在调试过程中临时调整 ``LOG_LEVEL``。
    """
    return _resolve_level()


def is_enabled_for(level: int) -> bool:
    """``level``（``logging.DEBUG/INFO/...``）是否会被当前 logger 输出。"""
    return get_log_level() <= level


def _build_formatters():
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if colorlog:
        console_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s  - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )
    else:
        console_formatter = file_formatter
    return file_formatter, console_formatter


def configure_logging() -> logging.Logger:
    """根据当前 ``LOG_LEVEL`` 重新创建 logger 及其 handlers。"""
    level = _resolve_level()
    log_file = (cfg.get("log.file", "") or "").strip()

    logger = logging.getLogger("we_mp_rss")
    logger.setLevel(level)
    # 避免 reload / 多次调用 configure_logging 时重复挂 handler
    logger.handlers.clear()
    logger.propagate = False

    # 文件 handler（即便暂未指定文件，也保留 DEBUG 级别以便后续切换）
    if log_file:
        file_handler = RotatingFileHandler(
            f"{log_file}.log", maxBytes=1024 * 1024, backupCount=7
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_build_formatters()[0])
        logger.addHandler(file_handler)

    # 控制台 handler —— 关键修复：跟随 LOG_LEVEL，而不是写死 INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(_build_formatters()[1])
    logger.addHandler(console_handler)

    logger.debug(
        "日志初始化完成 level=%s file=%s",
        logging.getLevelName(level),
        log_file or "<stdout-only>",
    )
    return logger


# 进程启动时立即生效
logger = configure_logging()
