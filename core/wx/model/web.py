"""redfox 数据源驱动的公众号采集器。

自 1.6 起，本模型取代了原先依赖微信公众号公众平台 (mp.weixin.qq.com)
扫码授权 + ``appmsgpublish`` / ``appmsg`` 的实现：

* 公众号信息与作品列表改由 ``core.redfox`` 提供的 redfox 接口拉取；
* 文章正文仍沿用 ``driver.wxarticle.Web.get_article_content``，
  保持原有 Playwright / 反爬虫栈不变。

本模块保留了旧 ``MpsWeb`` 类名与 ``get_Articles`` 方法签名，
因此调用方 (apis/mps.py、jobs/mps.py 等) 无需改动。
"""

import json
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, Optional

from core.log import logger
from core.print import print_error, print_info, print_warning
from core.redfox import RedfoxError, query_work_list
from core.wx.base import WxGather


class MpsWeb(WxGather):
    """基于 redfox 数据接口的公众号采集器。"""

    # 红狐接口固定每页 20 条，从 core.redfox 统一引用，避免重复定义。
    from core.redfox import PAGE_SIZE as _PAGE_SIZE  # noqa: F811
    PAGE_SIZE = _PAGE_SIZE

    # ------------------------------------------------------------------
    # 正文抓取：与旧版保持一致，沿用 driver.wxarticle
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
        interval: int = 10,
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
                print_error(f"redfox 拉取作品列表失败: {e}")
                break
            except Exception as e:  # noqa: BLE001
                print_error(f"redfox 拉取作品列表异常: {e}")
                break

            items = data.get("list") or []
            if not items:
                print_info(f"[{Mps_title}] 第 {page + 1} 页无数据，提前结束")
                break

            print_info(f"[{Mps_title}] 第 {page + 1} 页共 {len(items)} 条")

            for item in items:
                try:
                    mapped = self._map_work_item(item, Mps_id)
                    if Gather_Content:
                        if not super().HasGathered(mapped["aid"]):
                            mapped["content"] = self.content_extract(mapped["link"])
                            super().Wait(3, 10, tips=f"{mapped['title']} 采集完成")
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
                finally:
                    # 单条之间的随机等待，避免请求过快
                    time.sleep(random.randint(0, max(1, interval // 2)))

            total = int(data.get("total") or 0)
            page += 1
            if (page) * self.PAGE_SIZE >= total:
                break

            # 页面间等待
            time.sleep(random.randint(0, interval))

            try:
                super().Item_Over(
                    item={"mps_id": Mps_id, "mps_title": Mps_title},
                    CallBack=Item_Over_CallBack,
                )
            except Exception as e:  # noqa: BLE001
                print_warning(f"Item_Over 回调异常: {e}")

        super().Over(CallBack=Over_CallBack)
