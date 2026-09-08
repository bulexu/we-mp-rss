"""redfox 数据源驱动的公众号采集器。

自 1.6 起，本模型取代了原先依赖微信公众号公众平台 (mp.weixin.qq.com)
扫码授权 + ``appmsgpublish`` / ``appmsg`` 的实现：

* 公众号信息与作品列表改由 ``core.redfox`` 提供的 redfox 接口拉取；
* 文章正文仍沿用 ``driver.wxarticle.Web.get_article_content``，
  保持原有 Playwright / 反爬虫栈不变。

本模块保留了旧 ``MpsWeb`` 类名与 ``get_Articles`` 方法签名，
因此调用方 (apis/mps.py、jobs/mps.py 等) 无需改动。
"""

import asyncio
import json
import re
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from core.log import logger
from core.print import print_error, print_info, print_success, print_warning
from core.redfox import RedfoxError, query_work_list
from core.wx.base import WxGather

if TYPE_CHECKING:
    from core.db import Db


class MpsWeb(WxGather):
    """基于 redfox 数据接口的公众号采集器。"""

    # 红狐接口固定每页 20 条，从 core.redfox 统一引用，避免重复定义。
    from core.redfox import PAGE_SIZE as _PAGE_SIZE  # noqa: F811
    PAGE_SIZE = _PAGE_SIZE

    # ------------------------------------------------------------------
    # 正文抓取:旧路径,保留同步接口给一次性场景使用(如人工测试)。
    # 主流程 ``get_Articles`` 已切到 PlaywrightPool 异步后台抓取,
    # 列表抓取不再因正文而阻塞。
    # ------------------------------------------------------------------
    def content_extract(self, url: str) -> str:
        try:
            from driver.wxarticle import Web as App

            r = App.get_article_content(url)
            if r is not None:
                text = r.get("content", "")
                text = self.remove_common_html_elements(text)
                return text
        except Exception as e:  # noqa: BLE001
            logger.error(e)
        return ""

    # ------------------------------------------------------------------
    # 标识解析
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_identifier(faker_id: str) -> Dict[str, Optional[str]]:
        """根据 ``faker_id`` 推断 redfox 查询参数。

        优先顺序：bizInfo > wxId > account。
        """
        faker_id = (faker_id or "").strip()
        if not faker_id:
            return {"account": None, "wxId": None, "bizInfo": None}
        if faker_id.startswith("gh_"):
            return {"account": None, "wxId": faker_id, "bizInfo": None}
        # 形如 MjM5MDMyMzg2MA== 即 bizInfo（Base64）
        if re.fullmatch(r"[A-Za-z0-9+/=]+", faker_id or "") and len(faker_id) % 4 == 0:
            return {"account": None, "wxId": None, "bizInfo": faker_id}
        # 默认按微信号处理
        return {"account": faker_id, "wxId": None, "bizInfo": None}

    @staticmethod
    def _parse_publish_time(value: Any) -> int:
        """把 ``publishTime`` 转成 unix 秒；解析失败时返回当前时间。"""
        if not value:
            return int(time.time())
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return int(datetime.strptime(text, fmt).timestamp())
            except ValueError:
                continue
        return int(time.time())

    @staticmethod
    def _work_uuid_to_aid(work_uuid: str) -> str:
        """将 redfox ``workUuid`` 转为 ``aid``（去掉连字符保证兼容旧代码）。"""
        if not work_uuid:
            return ""
        return work_uuid.replace("-", "").replace(" ", "")

    def _map_work_item(self, raw: Dict[str, Any], Mps_id: str) -> Dict[str, Any]:
        """把 redfox 单条作品数据映射为旧 FillBack 期待的字段。"""
        work_uuid = raw.get("workUuid") or ""
        aid = self._work_uuid_to_aid(work_uuid) or work_uuid
        publish_ts = self._parse_publish_time(raw.get("publishTime"))
        return {
            "id": aid,
            "aid": aid,
            "appmsgid": aid,
            "mp_id": Mps_id,
            "title": raw.get("title") or "",
            "link": raw.get("workUrl") or "",
            "url": raw.get("workUrl") or "",
            "cover": raw.get("coverUrl") or "",
            "pic_url": raw.get("coverUrl") or "",
            "digest": raw.get("summary") or "",
            "description": raw.get("summary") or "",
            "update_time": publish_ts,
            "create_time": publish_ts,
            "publish_time": publish_ts,
            # 状态/类型
            "is_deleted": False,
            "copyright_stat": int(raw.get("isOriginal") or 0),
            "item_show_type": 0,
            "show_type": 0,
            "art_type": 0,
            "publish_type": 0,
            "publish_src": 0,
            "publish_status": "200",
            "service_type": 0,
            "pre_publish_status": 0,
            "original_check_type": 0,
            "in_profile": 1,
            "has_red_packet_cover": 0,
            # redfox 扩展字段
            "redfox_work_uuid": work_uuid,
            "read_count": raw.get("readCount"),
            "like_count": raw.get("likeCount"),
            "watch_count": raw.get("watchCount"),
            "comment_count": raw.get("commentCount"),
            "share_count": raw.get("shareCount"),
            "collect_count": raw.get("collectCount"),
            "original_author": raw.get("originalAuthor"),
            "source_url": raw.get("sourceUrl"),
            "order_num": raw.get("orderNum"),
        }

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def get_Articles(
        self,
        faker_id: str = "",
        Mps_id: str = "",
        Mps_title: str = "",
        CallBack=None,
        start_page: int = 0,
        MaxPage: int = 1,
        Gather_Content: bool = False,
        Item_Over_CallBack=None,
        Over_CallBack=None,
    ):
        try:
            super().Start(mp_id=Mps_id)
        except Exception as e:  # noqa: BLE001
            print_error(f"初始化采集任务失败: {e}")
            return

        if self.Gather_Content:
            Gather_Content = True
        print(f"Redfox数据接口模式,是否采集[{Mps_title}]内容:{Gather_Content}\n")

        if not faker_id:
            print_error("未提供 faker_id（公众号标识），无法拉取作品列表")
            super().Over(CallBack=Over_CallBack)
            return

        identifier = self._resolve_identifier(faker_id)
        if not any(identifier.values()):
            print_error(f"无法解析公众号标识: {faker_id}")
            super().Over(CallBack=Over_CallBack)
            return

        page = max(0, int(start_page))
        max_pages = max(1, int(MaxPage))
        # 本批待补抓正文的 (article_id, url) 列表,循环结束后统一投到 PlaywrightPool。
        # 列表抓取不再因正文抓取而阻塞,显著降低单 feed 耗时。
        pending_content: list[tuple[str, str]] = []
        for _ in range(max_pages):
            offset = page * self.PAGE_SIZE
            try:
                data = query_work_list(
                    account=identifier["account"],
                    wxId=identifier["wxId"],
                    bizInfo=identifier["bizInfo"],
                    offset=offset,
                    sortType="2",
                )
            except RedfoxError as e:
                print_error(f"redfox 拉取 {Mps_title} 作品列表失败: {e}")
                break
            except Exception as e:  # noqa: BLE001
                print_error(f"redfox 拉取 {Mps_title} 作品列表异常: {e}")
                break

            items = data.get("list") or []
            if not items:
                print_info(f"[{Mps_title}] 第 {page + 1} 页无数据，提前结束")
                break

            print_info(f"[{Mps_title}] 第 {page + 1} 页共 {len(items)} 条")

            for item in items:
                try:
                    mapped = self._map_work_item(item, Mps_id)
                    aid = mapped.get("aid", "")
                    link = mapped.get("link", "")
                    if Gather_Content and link and not super().HasGathered(aid):
                        # 不再就地抓正文 —— 列表先入库,正文交给后台 PlaywrightPool。
                        # 抓完后由 ``_schedule_content_gather`` 异步写回 DB。
                        mapped["content"] = ""
                        pending_content.append((aid, link))
                    else:
                        mapped["content"] = ""
                    if CallBack is not None:
                        super().FillBack(
                            CallBack=CallBack,
                            data=mapped,
                            Ext_Data={"mp_title": Mps_title, "mp_id": Mps_id},
                        )
                except Exception as e:  # noqa: BLE001
                    print_warning(f"单条作品处理失败: {e}")
                # 注意:此处原对 mp.weixin.qq.com 写有随机 sleep 反爬;
                # 改用 redfox 付费接口后已无频率限制,移除 sleep 提升并发吞吐。

            total = int(data.get("total") or 0)
            page += 1
            if (page) * self.PAGE_SIZE >= total:
                break

            # 原页面间 sleep 同样已移除,见上方注释。

            try:
                super().Item_Over(
                    item={"mps_id": Mps_id, "mps_title": Mps_title},
                    CallBack=Item_Over_CallBack,
                )
            except Exception as e:  # noqa: BLE001
                print_warning(f"Item_Over 回调异常: {e}")

        # 列表抓取完成,后台异步抓正文。
        # 不等待结果 —— PlaywrightPool 完成后会调用 ``_on_content_extracted`` 写库。
        if pending_content:
            self._schedule_content_gather(Mps_id, pending_content)

        super().Over(CallBack=Over_CallBack)

    def _schedule_content_gather(
        self,
        Mps_id: str,
        pending: list[tuple[str, str]],
    ) -> None:
        """把本批正文抓取投到 PlaywrightPool,后台异步执行。

        调用线程立即返回。

        完成回调分两条路径:
          * **成功**:走 :meth:`Db.update_article_content` 快速写库 + 重置
            ``web_fetch_fail_count``;
          * **失败**:走 :func:`core.article_content.sync_article_content`,
            由它读 ``web_fetch_fail_count``,``>= WEB_FAIL_THRESHOLD (3)``
            时自动尝试 redfox SDK 兜底。失败路径在回调里 ``run_in_executor``
            切到独立线程,避免在 playwright-pool 的事件循环线程里
            ``asyncio.new_event_loop`` 嵌套报错。
        """
        if not pending:
            return
        try:
            from core.db import Db
            from core.wx.playwright_pool import PlaywrightPool

            pool = PlaywrightPool.instance()
            db = Db(tag="正文回写")
            print_info(
                f"[{Mps_id}] 调度 {len(pending)} 篇文章正文异步抓取"
            )

            for aid, link in pending:
                try:
                    future = pool.submit_extract(link)
                except Exception as exc:  # noqa: BLE001
                    print_error(f"提交正文抓取任务失败 [{aid}]: {exc}")
                    continue

                future.add_done_callback(
                    lambda fut, _aid=aid, _link=link, _db=db, _mid=Mps_id:
                        MpsWeb._on_content_extracted(
                            fut, _aid, _link, _mid, _db
                        )
                )
        except Exception as exc:  # noqa: BLE001
            print_error(f"_schedule_content_gather 异常: {exc}")

    @staticmethod
    def _on_content_extracted(
        fut,
        aid: str,
        link: str,
        Mps_id: str,
        db: "Db",
    ) -> None:
        """PlaywrightPool 单篇正文抓取完成后的回调。

        在 playwright-pool 的事件循环线程里被触发;
        DB 写操作通过 ``loop.run_in_executor`` 切到独立线程,
        避免在已有 loop 的线程里再 ``new_event_loop``(sync_article_content
        的 web 兜底走 ``Web.get_article_content`` 同步包装)。
        """
        # 把 info 解析放到回调线程(纯字典访问,无副作用),
        # 把 DB 操作切到独立线程。
        try:
            info = fut.result() or {}
        except Exception as exc:  # noqa: BLE001
            print_error(f"正文抓取回调异常 [{aid}]: {exc}")
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        def _handle() -> None:
            content = (info.get("content", "") or "").strip()
            fetch_error = (info.get("fetch_error", "") or "").strip()
            # DB 主键 ID 走 ``add_article`` 同样的前缀规则。
            db_id = f"{Mps_id}-{aid}".replace("MP_WXS_", "")

            if content and not fetch_error:
                # 成功:快速通道直接写库,并重置 web 失败计数,
                # 与 ``sync_article_content`` 行为保持一致。
                try:
                    db.update_article_content(db_id, content)
                    _reset_web_fail_count(db_id)
                except Exception as exc:  # noqa: BLE001
                    print_error(f"正文回写异常 [{db_id}]: {exc}")
                return

            # 失败:走 ``sync_article_content``,它会按 ``web_fetch_fail_count``
            # 决定是否走 redfox 兜底,并自动累加 / 重置计数。
            if fetch_error:
                print_warning(
                    f"PlaywrightPool 抓取失败 [{aid}]: {fetch_error}, "
                    f"走 sync_article_content 兜底"
                )
            try:
                _fallback_via_sync(db_id, link)
            except Exception as exc:  # noqa: BLE001
                print_error(f"sync_article_content 兜底异常 [{db_id}]: {exc}")

        if loop is not None and loop.is_running():
            loop.run_in_executor(None, _handle)
        else:
            _handle()


def _reset_web_fail_count(db_id: str) -> None:
    """重置 ``web_fetch_fail_count`` 到 0(成功的奖励)。

    与 :func:`sync_article_content` 在 success 分支里的行为一致 ———
    任意模式成功都让 web 重新被信任。
    """
    try:
        from core.db import Db
        from core.models.article import Article

        db = Db(tag="正文回写")
        session = db.get_session()
        article = session.query(Article).filter(Article.id == db_id).first()
        if article is not None and (article.web_fetch_fail_count or 0) > 0:
            article.web_fetch_fail_count = 0
            session.commit()
    except Exception as exc:  # noqa: BLE001
        print_warning(f"重置 web 失败计数异常 [{db_id}]: {exc}")


def _fallback_via_sync(db_id: str, link: str) -> None:
    """PlaywrightPool 失败后,复用 ``sync_article_content`` 的全套降级链。

    触发条件:web 抓取抛异常 / ``fetch_error`` 非空 / ``content`` 为空。
    行为:
      1. 读 ``web_fetch_fail_count``;
      2. ``>= WEB_FAIL_THRESHOLD (3)`` 时直接走 redfox SDK;
      3. 否则按 ``gather.content_mode``(默认 web)+ 兜底 api;
      4. 成功清零,失败 +1。

    注意:此函数被 ``_on_content_extracted`` 通过 ``run_in_executor`` 切到
    独立线程调用,因为 :func:`sync_article_content` 内的 ``_fetch_with_web``
    会走 ``Web.get_article_content`` 同步包装器,会在当前线程
    ``asyncio.new_event_loop()`` —— 如果当前线程已有 loop 会报错。
    """
    from core.config import cfg
    from core.db import Db
    from core.article_content import sync_article_content
    from core.models.article import Article

    db = Db(tag="正文兜底")
    session = db.get_session()
    try:
        article = session.query(Article).filter(Article.id == db_id).first()
        if article is None:
            print_warning(f"文章不存在,跳过降级 [{db_id}]")
            return
        # 已有 content 的(并发场景下另一个 worker 已写)直接跳过
        if (article.content or "").strip():
            print_info(f"文章已有 content,跳过 [{db_id}]")
            return

        updated, mode = sync_article_content(
            session=session,
            article=article,
            preferred_mode=cfg.get("gather.content_mode", "web"),
        )
        if updated:
            print_success(f"降级通道成功 [{db_id}], mode={mode}")
        else:
            print_warning(f"降级通道也失败 [{db_id}], mode={mode}")
    except Exception as exc:  # noqa: BLE001
        print_error(f"_fallback_via_sync 异常 [{db_id}]: {exc}")
