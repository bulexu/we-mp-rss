import os
import requests
import json
import re
import time
from typing import Any, Dict, List
from core.models import Feed
from core.db import DB
from core.models.base import DATA_STATUS
from core.models.feed import Feed
from core.config import cfg
from core.print import print_error,print_info, print_warning, print_success
from core.rss import RSS
from driver.wxarticle import Web
from core.wait import Wait
from core.redfox import PAGE_SIZE
import random


def _map_account_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """把 redfox accountInfo 返回的数据映射为旧 searchbiz 字段。

    保留 ``fakeid``、``nickname``、``round_head_img``、``signature`` 等旧字段，
    以便 ``AddSubscription.vue`` 等前端代码无须改动即可继续工作。
    """
    biz_info = data.get("bizInfo") or ""
    return {
        "fakeid": biz_info,
        "nickname": data.get("accountName") or "",
        "round_head_img": data.get("avatarUrl") or "",
        "signature": data.get("description") or "",
        "alias": data.get("account") or "",
        # 新增字段，便于后续业务使用
        "wxId": data.get("wxId") or "",
        "qrcodeUrl": data.get("qrcodeUrl") or "",
        "verifyInfo": data.get("verifyInfo") or "",
        "account": data.get("account") or "",
        "accountName": data.get("accountName") or "",
        "avatarUrl": data.get("avatarUrl") or "",
        "bizInfo": biz_info,
        "description": data.get("description") or "",
    }
# 定义一些常见的 User-Agent
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 11; Mobile; rv:89.0) Gecko/89.0 Firefox/89.0",
    # Chrome 桌面端
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    # Firefox 桌面端
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.4; rv:109.0) Gecko/20100101 Firefox/114.0",
    # Safari 桌面端
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    # Edge 桌面端
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.67",
    # Android 移动端 Chrome
    "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    # Android 移动端 Firefox
    "Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/109.0 Firefox/114.0",
    # iOS 移动端 Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
]
# 定义基类
class WxGather:
    articles=[]
    aids=[]
    def all_count(self):
        if getattr(self, 'articles', None) is not None:
            return len(self.articles)
        return 0
    def RecordAid(self,aid:str):
        self.aids.append(aid)
        pass
    def HasGathered(self,aid:str):
        if aid in self.aids:
            return True
        self.RecordAid(aid)
        return False
    def Model(self,type=None):
        type=type or cfg.get("gather.model","web")
        print(f"采集模式:{type}")
        if type=="app":
            from core.wx.model.app import MpsAppMsg
            wx=MpsAppMsg()
        elif type=="web":
            from core.wx.model.web import MpsWeb
            wx=MpsWeb()
        else:
            from core.wx.model.api import MpsApi
            wx=MpsApi()
        return wx
    def __init__(self,is_add:bool=False):
        self.articles=[]
        self.is_add=is_add
        self._cookies={}
        self.start_time = None  # 记录开始时间
        session=  requests.Session()
        timeout = (5, 10)
        session.timeout = timeout # type: ignore
        self.session=session
        self.get_token()
    def get_token(self):
        """加载基础采集配置。

        注意：自 1.6 起，本项目已不再依赖微信公众平台的扫码授权（不再
        读取 cookie / token），公众号信息与作品列表改由 redfox 数据
        接口提供。本方法保留仅为兼容历史调用，请勿再依赖 ``self.token``
        或 ``self.cookies`` 字段。
        """
        cfg.reload()
        self.Gather_Content=cfg.get('gather.content',False)
        # 兼容旧代码：保留同名属性，但已不再使用
        self.cookies = ""
        self.token = ""
        # 随机选择一个 User-Agent
        self.user_agent = cfg.get('user_agent', '')
        user_agent = random.choice(USER_AGENTS)
        self.user_agent=user_agent
        self.headers = {
            "User-Agent": user_agent
        }
        # 加载代理配置
        self.proxy_enabled = cfg.get('proxy.enabled', False)
        self.deno_proxy_url = cfg.get('proxy.deno_url', '')
        self.http_proxy_url = cfg.get('proxy.http_url', '')
        
    def _get_proxies(self):
        """获取代理配置"""
        if not self.proxy_enabled:
            return None
        if self.http_proxy_url:
            return {
                "http": self.http_proxy_url,
                "https": self.http_proxy_url
            }
        return None
    
    def _proxy_request(self, url: str) -> str:
        """通过代理请求URL内容
        
        Args:
            url: 目标URL
            
        Returns:
            响应内容
        """
        import urllib.parse
        
        # 如果启用了Deno Deploy代理
        if self.proxy_enabled and self.deno_proxy_url:
            proxy_url = f"{self.deno_proxy_url}?url={urllib.parse.quote(url, safe='')}"
            print_info(f"使用Deno代理请求: {proxy_url}")
            try:
                response = self.session.get(proxy_url, headers=self.headers, timeout=(10, 30))
                if response.status_code == 200:
                    return response.text
                else:
                    print_warning(f"Deno代理请求失败: {response.status_code}")
            except Exception as e:
                print_error(f"Deno代理请求异常: {e}")
        
        # 使用HTTP代理或直连
        proxies = self._get_proxies()
        try:
            response = self.session.get(url, headers=self.headers, proxies=proxies, timeout=(10, 30))
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print_error(f"请求失败: {e}")
        
        return ""
    def fix_header(self,url):
         user_agent = random.choice(USER_AGENTS)
          # 更新请求头
         headers = self.headers.copy()
         headers.update({
                "User-Agent": user_agent,
                "Refer": url,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive"
            })
         return headers
    def content_extract(self,  url):
        text=""
        try:
            session=self.session
            # 更新请求头
            headers = self.fix_header(url)
            
            # 优先使用代理
            if self.proxy_enabled and self.deno_proxy_url:
                text = self._proxy_request(url)
                if text:
                    text = self.remove_common_html_elements(text)
                    return text
            
            # 使用HTTP代理或直连
            proxies = self._get_proxies()
            r = session.get(url, headers=headers, proxies=proxies) #type: ignore
            if r.status_code == 200:
                text = r.text
                text=self.remove_common_html_elements(text)
        except:
            pass
        return text
    def Wait(self,min=10,max=60,tips:str=""):
        wait=random.randint(min,max)
        print_warning(f"{tips}等待{wait}秒后继续...")
        time.sleep(wait)

    def FillBack(self,CallBack=None,data=None,Ext_Data=None):
        if CallBack is not None:
            if data is not  None:
                from core.models import Article
                from datetime import datetime
                # 文章基础属性
                # title：文章标题（例如文档中的"测试无图"、"测试"）
                # aid：文章全局唯一ID（App Message ID）
                # link：文章的永久链接（URL），用户点击阅读的地址
                # digest：文章摘要（如果为空则显示为空字符串）
                # cover / cover_img：封面图片的URL地址
                # update_time / create_time：文章的更新时间和创建时间（Unix时间戳格式，需转换）
                # is_deleted：删除状态标记（false 表示未删除）
                # 状态与类型标识
                # copyright_stat：原创状态（0通常表示非原创，1表示原创）
                # is_pay_subscribe：是否为付费订阅内容
                # item_show_type：展示类型（0通常为普通图文，10可能为特定的无图或特殊样式）
                # has_red_packet_cover：封面是否有红包挂件（0为无）
                
                # 处理 publish_info 字段（Text类型，JSON字符串）
                publish_data=data.get("publish_info",{}) or {}
                publish_info_value = publish_data 
                if publish_info_value is not None:
                    if isinstance(publish_info_value, dict):
                        publish_info_str = json.dumps(publish_info_value)
                    else:
                        publish_info_str = str(publish_info_value)
                else:
                    publish_info_str = ""
                
                art={
                    "id":str(data['id']),  # 文章唯一标识ID
                    "mp_id":data['mp_id'],  # 公众号ID
                    "title":data['title'],  # 文章标题
                    "url":data['link'],  # 文章链接地址
                    "pic_url":data['cover'],  # 封面图片URL
                    "content":data.get("content",""),  # 文章正文内容
                    "publish_type":data.get("publish_type",0),  # 发布类型(1=普通发布, 101=群发消息)
                    "art_type":data.get("type",0),  # 展示类型(0=图文, 5=视频, 7=音频, 10=贴图)
                    "show_type": data.get("show_type",0) or data.get("item_show_type",0),  # 展示类型(0=图文, 5=视频, 7=音频, 10=贴图)
                    "publish_src":data.get("publish_src",0) or publish_data.get('publish_src',0),  # 发布来源
                    "publish_status":data.get("publish_status","200") or publish_data.get("publish_status",0),  # 发布状态码
                    "publish_time":data.get("update_time",""),  # 发布/更新时间
                    "create_time":data.get("create_time",""),  # 创建时间
                    "original_check_type":data.get("original_check_type",0),  # 原创检测类型
                    "in_profile":data.get("in_profile",0),  # 是否在公众号主页显示
                    "pre_publish_status":data.get("pre_publish_status",0),  # 预发布状态
                    "service_type":data.get("service_type",0) or publish_data.get("service_type",0),  # 服务类型
                    "item_show_type":data.get("item_show_type",0),  # 展示类型标识
                    "copyright_stat":data.get("copyright_stat",0) or publish_data.get("copyright_stat",0),  # 版权/原创状态(0非原创,1原创)
                    "has_red_packet_cover":data.get("has_red_packet_cover",0),  # 封面是否有红包挂件
                    "status": DATA_STATUS.DELETED if data.get("is_deleted",False) else DATA_STATUS.ACTIVE,  # 数据状态(已删除/正常)
                    "publish_info": publish_info_str,  # 发布信息（JSON格式字符串）
                }
                if 'digest' in data:
                    art['description']=data['digest']
                if CallBack(art):
                    art["ext"]=Ext_Data
                    # art.pop("content")
                    self.articles.append(art)

    #通过 redfox 数据接口查询公众号
    # 自 1.6 起，不再依赖微信公众平台的 searchbiz 接口；
    # 改为通过 redfox.hk 的 /story/api/gzh/data/searchUser 按关键词搜索账号
    # （广域库，单页 20 条），通过 /story/api/gzh/data/queryWorkList 拉取
    # 作品列表。
    def search_Biz(self, kw: str = "", limit: int = 10, offset: int = 0):
        """搜索公众号账号信息（关键词模糊匹配）。

        Args:
            kw: 搜索关键词，匹配公众号名 / 描述 / 微信号等。
            limit: 返回条数上限，超出 redfox 单页（20 条）时按需自动翻页
                （最多 5 页 = 100 条），避免单次请求过重。
            offset: 分页偏移量，每页 +20。

        Returns:
            与旧 searchbiz 兼容的字典::

                {
                    "list": [
                        {
                            "fakeid": ...,          # 来自 bizInfo（Base64）
                            "nickname": ...,        # 来自 accountName
                            "round_head_img": ...,  # 来自 avatarUrl
                            "signature": ...,       # 来自 description
                            "alias": ...,           # 来自 account
                            "wxId": ...,
                            "qrcodeUrl": ...,
                            "verifyInfo": ...,
                            # searchUser 额外字段
                            "updateTime": ...,
                        },
                        ...
                    ],
                    "total": int,                # redfox 报告的全网命中数
                    "base_resp": {"ret": int, "err_msg": str},
                }

            失败时 ``base_resp.ret`` 为非 0，``list`` 为空。
        """
        self.get_token()
        kw = (kw or "").strip()
        if not kw:
            return {
                "list": [],
                "total": 0,
                "base_resp": {"ret": 0, "err_msg": ""},
            }

        try:
            limit = int(limit) if limit else 10
        except (TypeError, ValueError):
            limit = 10
        try:
            offset = int(offset) if offset else 0
        except (TypeError, ValueError):
            offset = 0
        if limit <= 0:
            limit = 10
        if offset < 0:
            offset = 0

        from core.redfox import RedfoxError, search_user

        base_resp = {"ret": 0, "err_msg": ""}
        items: List[Dict[str, Any]] = []
        total: int = 0
        page_size = PAGE_SIZE
        # 单次最多拉 5 页（= 100 条），防止外部传超大 limit 时把 redfox 打爆。
        max_pages = min(5, max(1, (limit + page_size - 1) // page_size))
        try:
            for page in range(max_pages):
                page_offset = offset + page * page_size
                data = search_user(keyword=kw, offset=page_offset)
                if page == 0:
                    total = int(data.get("total", 0) or 0)
                page_list = data.get("list") or []
                if not isinstance(page_list, list):
                    page_list = []
                for raw in page_list:
                    if not isinstance(raw, dict):
                        continue
                    items.append(_map_account_info(raw))
                    if len(items) >= limit:
                        break
                # 当前页不足一整页说明已经到尾，没有下一页了。
                if len(page_list) < page_size or len(items) >= limit:
                    break
        except RedfoxError as e:
            base_resp = {"ret": -1, "err_msg": str(e)}
        except Exception as e:  # noqa: BLE001
            print_error(f"redfox 账号搜索异常: {e}")
            base_resp = {"ret": -1, "err_msg": str(e)}

        return {
            "list": items,
            "total": total,
            "base_resp": base_resp,
        }



    def Start(self,mp_id=None):
        try:
            self.articles=[]
            self.get_token()
            # 自 1.6 起不再校验 token；redfox 接口由各子模型按需调用。
            import time
            self.start_time = time.time()  # 记录开始执行时间
            self.update_mps(
                mp_id, #type: ingnore
                            Feed(
            sync_time=int(time.time()),
            update_time=int(time.time()),
            ))
        except Exception as e:
            print_error(f"开始采集失败: {e}")

    def Item_Over(self,item=None,CallBack=None):
        print(f"item end")
        _cookies=[{'name': c.name, 'value': c.value, 'domain': c.domain,'expiry':c.expires,'expires':c.expires} for c in self._cookies]
        if CallBack is not None:
            CallBack(item)
        self.Wait(tips=f"{item['mps_title']} 处理完成",min=3,max=10) #type: ignore
        pass
    def Error(self,error:str,code=None):
        self.Over()
        if code=="Invalid Session":
            # 兼容旧调用方：redfox 接口理论上不会返回该值，但保留分支以免破坏上层 try/except。
            raise Exception(error)
        # 默认仅打印错误，不再抛出，避免中断后续公众号的采集。
        print_error(error)

    def Over(self,CallBack=None):
        import time
        end_time = time.time()
        execution_time = 0
        if self.start_time is not None:
            execution_time = end_time - self.start_time
        
        if getattr(self, 'articles', None) is not None:
            print(f"成功{len(self.articles)}条")
            rss=RSS()
            mp_id=""
            try:
                mp_id=self.articles[0]['mp_id']
            except:
                pass
            rss.clear_cache(mp_id=mp_id)  
        
        # 输出执行时间统计
        if execution_time > 0:
            if execution_time < 60:
                print(f"执行耗时: {execution_time:.2f}秒")
            elif execution_time < 3600:
                minutes = int(execution_time // 60)
                seconds = execution_time % 60
                print(f"执行耗时: {minutes}分{seconds:.2f}秒")
            else:
                hours = int(execution_time // 3600)
                minutes = int((execution_time % 3600) // 60)
                seconds = execution_time % 60
                print(f"执行耗时: {hours}小时{minutes}分{seconds:.2f}秒")
        
        if CallBack is not None:
            CallBack(self.articles)

    def dateformat(self,timestamp:any):
        from datetime import datetime, timezone
        # UTC时间对象
        utc_dt = datetime.fromtimestamp(int(timestamp), timezone.utc)
        t=(utc_dt.strftime("%Y-%m-%d %H:%M:%S")) 

        # UTC转本地时区
        local_dt = utc_dt.astimezone()
        t=(local_dt.strftime("%Y-%m-%d %H:%M:%S"))
        return t


    def remove_common_html_elements(self, html_content: str) -> str:
        if "当前环境异常，完成验证后即可继续访问" in html_content:
                Wait(tips="当前环境异常，完成验证后即可继续访问")
                html_content=""
        else:
            html_content=Web.clean_article_content(html_content)
        return html_content

    # 更新公众号更新状态
    def update_mps(self,mp_id:str, mp:Feed):
        """更新公众号同步状态和时间信息
        Args:
            mp_id: 公众号ID
            mp: Feed对象，包含公众号信息
        """
        from datetime import datetime
        import time
        try:
            
            # 更新同步时间为当前时间
            current_time = int(time.time())
            update_data = {
                'sync_time': current_time,
                # 'updated_at': dateformat(current_time)
                'updated_at': datetime.now(),
            }
            
            # 如果有新文章时间，也更新update_time
            if hasattr(mp, 'update_time') and mp.update_time:
                update_data['update_time'] = mp.update_time
            if hasattr(mp,'status') and mp.status is not None:
                update_data['status']=mp.status

            # 获取数据库会话并执行更新
            session = DB.get_session()
            try:
                feed = session.query(Feed).filter(Feed.id == mp_id).first()
                if feed:
                    for key, value in update_data.items():
                        print(f"更新公众号{mp_id}的{key}为{value}")
                        setattr(feed, key, value)
                    session.commit()
                else:
                    print_error(f"未找到ID为{mp_id}的公众号记录")
            finally:
                pass
                
        except Exception as e:
            print_error(f"更新公众号状态失败: {e}")
            raise NotImplementedError(f"更新公众号状态失败:{str(e)}")