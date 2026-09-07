"""主事件循环引用与跨线程异步任务提交工具。

FastAPI/uvicorn 在主线程启动时把 ``asyncio.get_running_loop()`` 通过
:func:`set_main_loop` 保存到这里;任何后台线程(如 ``TaskQueue`` 后台 worker)
需要调度异步协程时,调用 :func:`submit_async` 把协程提交到主 loop 上执行。

为什么需要这个模块:
    * TaskQueue 的 worker 线程与 uvicorn 的事件循环不在同一线程。
    * 在该线程里直接 ``asyncio.create_task(coro)`` 会失败 ——
      没有 loop 被绑定到当前线程,创建出来的 task 永远不会被调度。
    * 跨线程提交的标准做法是 ``asyncio.run_coroutine_threadsafe``,
      它接受目标 loop 作为参数。

设计要点:
    * 主 loop 通过 :func:`set_main_loop` 注册,缺失时 :func:`submit_async`
      打印告警并返回 ``None``,不抛出 ——
      避免污染纯后台任务(如 cron 调度)的主流程。
    * 模块级全局变量受 ``threading.Lock`` 保护,
      写少读多场景下不会成为热点。
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, Optional

from core.print import print_error, print_warning

_main_loop: Optional[asyncio.AbstractEventLoop] = None
_main_loop_lock = threading.Lock()


def set_main_loop(loop: Optional[asyncio.AbstractEventLoop]) -> None:
    """注册主事件循环(由 FastAPI lifespan startup 阶段调用)。

    Args:
        loop: ``asyncio.get_running_loop()`` 在主线程中拿到的 loop。
              传 ``None`` 表示注销(用于测试 / 重启场景)。
    """
    global _main_loop
    with _main_loop_lock:
        _main_loop = loop


def get_main_loop() -> Optional[asyncio.AbstractEventLoop]:
    """获取已注册的主事件循环;未注册返回 ``None``。"""
    return _main_loop


def submit_async(coro: Coroutine[Any, Any, Any]) -> Optional[asyncio.Future]:
    """从任意后台线程向主事件循环提交协程。

    Args:
        coro: 要在主 loop 上执行的协程对象。注意:此处传入的是协程本身,
              ``run_coroutine_threadsafe`` 会负责包装它。

    Returns:
        ``concurrent.futures.Future``(由 ``run_coroutine_threadsafe`` 返回),
        调用方可以选择 ``.result(timeout=...)`` 同步等待,或直接丢弃。

        主 loop 不可用时返回 ``None``,并打印一行 warning —— 不抛出异常。
    """
    loop = get_main_loop()
    if loop is None:
        print_warning(
            "主事件循环未注册,跳过异步任务提交"
            "(纯后台任务调度场景可忽略;FastAPI 启动后会正常生效)"
        )
        return None
    try:
        return asyncio.run_coroutine_threadsafe(coro, loop)
    except RuntimeError as exc:
        # loop 已关闭等场景
        print_error(f"跨线程提交协程失败: {exc}")
        return None


__all__ = ["set_main_loop", "get_main_loop", "submit_async"]