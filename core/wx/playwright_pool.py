"""Playwright 单例池:进程内只启一次浏览器,正文抓取在后台事件循环里跑。

背景:
  旧实现 [driver/wxarticle.py:649] 每次采集一篇正文都
  ``asyncio.new_event_loop + async with PlaywrightController``,
  即每篇文章启停一次 Chromium(3-8 秒),且全程阻塞调用线程。
  38 feeds 单 worker 跑下来数小时。

改造:
  - 单例池:进程内只起一次 Playwright 浏览器;
  - 后台线程跑独立事件循环,正文抓取不阻塞列表抓取的主线程;
  - 同浏览器内通过信号量限制并发页面数,避免 Chromium OOM。
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from typing import Any, Dict, Optional

from core.config import cfg
from core.log import logger
from core.print import print_error, print_info
from driver.playwright_driver import PlaywrightController


class PlaywrightPool:
    """进程级单例 Playwright 池。

    使用方式::

        pool = PlaywrightPool.instance()
        future = pool.submit_extract(url)
        info = future.result()  # {"content": "...", "fetch_error": ""}
    """

    _instance: Optional["PlaywrightPool"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._start_lock = threading.Lock()
        self._started = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._controller: Optional[PlaywrightController] = None
        self._sem: Optional[asyncio.Semaphore] = None
        self._ready = threading.Event()
        self._failed: Optional[str] = None
        # 同浏览器内并发页面数上限。Chromium 每页 ~100-300MB,
        # 默认 2 个并发,2U4G 服务器留 ~1GB 给浏览器比较稳。
        self._max_concurrent = int(cfg.get("gather.content_concurrency", 2))

    @classmethod
    def instance(cls) -> "PlaywrightPool":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def ensure_started(self) -> None:
        """惰性启动:首次调用时拉起后台线程 + 浏览器。

        多次调用安全;启动失败会把异常抛给调用方。
        """
        with self._start_lock:
            if self._started:
                return
            self._started = True
            self._thread = threading.Thread(
                target=self._run_loop,
                name="playwright-pool",
                daemon=True,
            )
            self._thread.start()

        if not self._ready.wait(timeout=45):
            raise RuntimeError(
                f"PlaywrightPool 启动超时(45s);错误: {self._failed}"
            )
        if self._failed:
            raise RuntimeError(f"PlaywrightPool 启动失败: {self._failed}")

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._sem = asyncio.Semaphore(self._max_concurrent)
        try:
            self._loop.run_until_complete(self._init_controller())
            print_info(f"PlaywrightPool 已就绪 (并发上限 {self._max_concurrent})")
            self._ready.set()
            self._loop.run_forever()
        except Exception as exc:  # noqa: BLE001
            self._failed = str(exc)
            self._ready.set()
            logger.error(f"PlaywrightPool 异常退出: {exc}")
        finally:
            try:
                if self._controller is not None:
                    self._loop.run_until_complete(self._controller.Close())
            except Exception:  # noqa: BLE001
                pass
            try:
                self._loop.close()
            except Exception:  # noqa: BLE001
                pass

    async def _init_controller(self) -> None:
        proxy_url = ""
        if cfg.get("proxy.enabled", False):
            proxy_url = cfg.get("proxy.http_url", "")
        self._controller = PlaywrightController(
            proxy_url=proxy_url, mobile_mode=True
        )
        await self._controller.start_browser()

    def submit_extract(self, url: str) -> "Future[Dict[str, Any]]":
        """把单篇正文抓取投到池子,返回 concurrent.futures.Future。

        调用方在后台线程/异步路径里 ``future.result()`` 即可;
        返回 dict 含 ``content`` (HTML 字符串)、``fetch_error`` (失败原因)。
        """
        self.ensure_started()
        assert self._loop is not None
        return asyncio.run_coroutine_threadsafe(
            self._extract_one(url), self._loop
        )

    async def _extract_one(self, url: str) -> Dict[str, Any]:
        """池内单次采集:在已有 context 上开新页面,抓完即关。"""
        assert self._controller is not None
        assert self._sem is not None
        async with self._sem:
            try:
                from driver.wxarticle import WXArticleFetcher
                return await WXArticleFetcher.get_article_content_with_controller(
                    self._controller, url
                )
            except Exception as exc:  # noqa: BLE001
                print_error(f"PlaywrightPool 抓取失败 [{url}]: {exc}")
                return {"content": "", "fetch_error": str(exc)}
