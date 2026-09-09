from sqlalchemy import and_, create_engine, Engine, event, inspect, or_, text, Text
from sqlalchemy.orm import sessionmaker, declarative_base,scoped_session
from sqlalchemy import Column, Integer, String, DateTime
from typing import Optional, List
import re
from .models import Feed, Article
from .config import cfg
from core.models.base import Base, DATA_STATUS
from core.print import print_warning,print_info,print_error,print_success
# 声明基类
# Base = declarative_base()


# ---------------------------------------------------------------------------
# mid 提取工具 (用于第三道去重,见 Db.add_article)
# ---------------------------------------------------------------------------
#
# 背景:``Article.id`` 主键由 ``{mp_id}-{workUuid}`` 拼出,而 ``workUuid``
# 是 redfox 内部标识,在 redfox 后台重算 metadata 时可能变化;
# ``workUrl`` 里的 ``sn=`` 参数也会变。两者都不稳定。
# mp.weixin.qq.com URL 里的 ``mid=`` 是微信侧文章全局 ID,跨 redfox
# 调用稳定,因此作为第三道去重依据。
# ---------------------------------------------------------------------------

_MID_RE = re.compile(r"[?&]mid=(\d+)")


def _extract_wechat_mid(url: str) -> str:
    """从 mp.weixin.qq.com 类 URL 中提取 ``mid`` 参数。

    失败 (空 URL / 非 mp URL / 缺 mid) 返回空字符串,调用方据此跳过
    mid 这条 dedup 路径。
    """
    if not url:
        return ""
    m = _MID_RE.search(url)
    return m.group(1) if m else ""

class Db:
    connection_str: str=""
    def __init__(self,tag:str="默认",User_In_Thread=True):
        self.Session= None
        self.engine = None
        self.User_In_Thread=User_In_Thread
        self.tag=tag
        print_success(f"[{tag}]连接初始化")
        self.init(cfg.get("db","")) # type: ignore
    def get_engine(self) -> Engine:
        """Return the SQLAlchemy engine for this database connection."""
        if self.engine is None:
            raise ValueError("Database connection has not been initialized.")
        return self.engine
    def get_session_factory(self):
        return sessionmaker(bind=self.engine, autoflush=True, expire_on_commit=True, future=True)
    def init(self, con_str: str) -> None:
        """Initialize database connection and create tables"""
        try:
            self.connection_str=con_str
            # 检查SQLite数据库文件是否存在
            if con_str.startswith('sqlite:///'):
                import os
                db_path = con_str[10:]  # 去掉'sqlite:///'前缀
                if not os.path.exists(db_path):
                    try:
                        os.makedirs(os.path.dirname(db_path), exist_ok=True)
                    except Exception as e:
                        pass
                    open(db_path, 'w').close()
            
            # SQLite 连接参数
            connect_args = {}
            if con_str.startswith('sqlite:///'):
                connect_args = {"check_same_thread": False}
            
            self.engine = create_engine(con_str,
                                     pool_size=2,          # 最小空闲连接数
                                     max_overflow=20,      # 允许的最大溢出连接数
                                     pool_timeout=30,      # 获取连接时的超时时间（秒）
                                     echo=False,
                                     pool_recycle=60,  # 连接池回收时间（秒）
                                     isolation_level="AUTOCOMMIT",  # 设置隔离级别
                                    #  isolation_level="READ COMMITTED",  # 设置隔离级别
                                    #  query_cache_size=0,
                                     connect_args=connect_args
                                     )
            
            # 添加SQL执行事件监听器，打印执行的SQL语句
            @event.listens_for(self.engine, "before_cursor_execute")
            def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                print_info(f"[SQL] {statement}")
                if parameters:
                    print_info(f"[参数] {parameters}")
            
            # 为 SQLite 设置 text_factory 处理无效 UTF-8 字符
            if con_str.startswith('sqlite:///'):
                @event.listens_for(self.engine, "connect")
                def set_sqlite_text_factory(dbapi_conn, connection_record):
                    # 将无效 UTF-8 字符替换为 �
                    dbapi_conn.text_factory = lambda x: x.decode('utf-8', errors='replace')
            
            self.session_factory=self.get_session_factory()
            self.ensure_article_columns()
        except Exception as e:
            print(f"Error creating database connection: {e}")
            raise
    def ensure_article_columns(self):
        """Ensure required columns exist for legacy articles tables."""
        try:
            inspector = inspect(self.engine)
            if "articles" not in inspector.get_table_names(): # type: ignore
                return

            columns = {column["name"] for column in inspector.get_columns("articles")} # type: ignore
            alter_statements = []
            if "is_favorite" not in columns:
                alter_statements.append("ALTER TABLE articles ADD COLUMN is_favorite INTEGER DEFAULT 0")

            if "has_content" not in columns:
                alter_statements.append("ALTER TABLE articles ADD COLUMN has_content INTEGER DEFAULT 0")

            if not alter_statements:
                return

            with self.engine.begin() as conn: # type: ignore
                for stmt in alter_statements:
                    conn.execute(text(stmt))

            print_info(f"[{self.tag}] 文章表结构已自动更新: {', '.join(alter_statements)}")
        except Exception as e:
            print_warning(f"[{self.tag}] 检查/更新 articles 表结构失败: {e}")
    def create_tables(self):
        """Create all tables defined in models"""
        from core.models.base import Base as B # 导入所有模型
        try:
            B.metadata.create_all(self.engine)
        except Exception as e:
            print_error(f"Error creating tables: {e}")

        print('All Tables Created Successfully!')    
        
    def close(self) -> None:
        """Close the database connection"""
        if self.Session:
            self.Session.close() # type: ignore
            self.Session.remove() # type: ignore
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    def delete_article(self,article_data:dict)->bool:
        try:
            art = Article(**article_data)
            if art.id: # type: ignore
               art.id=f"{str(art.mp_id)}-{art.id}".replace("MP_WXS_","") # type: ignore
            session=DB.get_session()
            article = session.query(Article).filter(Article.id == art.id).first()
            if article is not None:
                session.delete(article)
                session.commit()
                return True
        except Exception as e:
            print_error(f"delete article:{str(e)}")
            pass      
        return False
     
    def add_article(self, article_data: dict,check_exist=True) -> bool:
        try:
            session=self.get_session()
            from datetime import datetime
            art = Article(**article_data)
            if art.id: # type: ignore
               art.id=f"{str(art.mp_id)}-{art.id}".replace("MP_WXS_","") # type: ignore
            if check_exist:
                # 三道去重 (任一命中视为同一篇):
                #   1. 主键 id 相等       —— 老 workUuid 命中
                #   2. url 完全相等       —— workUrl 没变
                #   3. mp_id + URL 含 mid —— workUuid 和 sn 都变了时兜底
                # 第 3 道解决 redfox 后台重算 metadata 导致同一文章以不同
                # workUuid/sn 二次入库的问题 (生产环境截图重现过)。
                dedup_filters = [
                    Article.id == art.id,
                    Article.url == art.url,
                ]
                mid = _extract_wechat_mid(art.url or "")
                if mid:
                    # LIKE 模式两侧各加 & 防止误匹配:
                    #   - 前置 &: 排除 __biz 等参数 (防御,mp URL 无 mid 子串)
                    #   - 后置 &: 排除 mid=1234 误匹配 mid=12345 (123456&)
                    # 注:mid 在 URL 末尾 (后面跟 #rd) 的边界情况极为罕见,
                    # 99%+ 的真实 mp URL 都是 mid=&idx=&sn= 的格式,这里暂不覆盖。
                    dedup_filters.append(
                        and_(
                            Article.mp_id == art.mp_id,
                            Article.url.like(f"%&mid={mid}&%"),
                        )
                    )
                existing_article = session.query(Article.id,Article.publish_time,Article.status,Article.show_type,Article.description,Article.title).filter(
                    or_(*dedup_filters)
                ).first()
                if existing_article is not None:
                    # 当更新时间和状态都相同时，不需要更新
                    if art.status == existing_article.status and existing_article.publish_time==art.publish_time \
                    and existing_article.show_type==art.show_type\
                    and existing_article.status!=DATA_STATUS.DELETED \
                    and art.title==existing_article.title: # type: ignore
                        return False

                    if art.content is None:
                        from tools.fix import fix_html
                        art.content_html = fix_html(art.content) # type: ignore
                        # 设置 has_content 字段
                        art.has_content = 1 if (art.content and art.content.strip()) else 0 # type: ignore

                    # 第 3 道 (mid) 命中时,art.id 与 existing.id 不同 (workUuid 已变),
                    # 直接 merge 会按新 id 再插一条重复。把 art.id 改成 existing.id,
                    # merge 就会更新老行 (该 id 被 FK / RSS / 文章详情等引用)。
                    if art.id != existing_article.id:
                        print_warning(
                            f"Article dedup via mid: rewriting id {art.id} -> {existing_article.id}"
                        )
                        art.id = existing_article.id

                    session.merge(art)  # 使用 merge 来更新现有记录
                    session.commit()
                    print_warning(f"Article already exists: {art.id}")
                    print_info(f"Updated article (CHECK_EXIST): {art.id} (newer publish_time)")
                    return False
                
            if art.created_at is None:
                art.created_at=datetime.now() # type: ignore
            if isinstance(art.created_at, str):
                art.created_at=datetime.strptime(art.created_at ,'%Y-%m-%d %H:%M:%S') # type: ignore
            # 先处理毫秒，用原始值作为fallback，再转换秒
            original_updated_at = art.updated_at
            from core.timestamp import _to_unix_millis, _to_unix_seconds
            art.updated_at_millis = _to_unix_millis(art.updated_at_millis, original_updated_at) # type: ignore
            art.updated_at = _to_unix_seconds(art.updated_at) # type: ignore
            
            # 清理编码问题，确保存储的数据是合法的UTF-8
            from tools.fix import sanitize_utf8
            art.content = sanitize_utf8(art.content) if art.content else None # type: ignore
            art.content_html = sanitize_utf8(art.content_html) if art.content_html else None # type: ignore

            if art.content is not None:
                from tools.fix import fix_html
                art.content_html = fix_html(art.content) # type: ignore

            # 设置 has_content 字段
            art.has_content = 1 if (art.content and art.content.strip()) else 0 # type: ignore

            session.add(art)
            print_info(f"Added article: {art.id}")
            sta=session.commit()
            # 回调: 异步推送到关联飞书多维表。
            # 仅在「首次入库且带正文」时推,避免重复推送 (merge 去重路径不推)。
            if (art.content or "").strip() and getattr(art, "status", None) != DATA_STATUS.DELETED:
                try:
                    from core.lark_push import lark_maybe_push

                    lark_maybe_push(art.id)
                except Exception as hook_exc:  # noqa: BLE001
                    print_warning(f"add_article lark push hook failed: {hook_exc}")
        except Exception as e:
            session.rollback()  # 回滚事务，确保session状态正常
            if "UNIQUE" in str(e) or "Duplicate entry" in str(e):
                print_warning(f"Article already exists: {art.id}")
            else:
                print_error(f"Failed to add article: {e}")
            return False
        return True

    def update_article_content(self, article_id: str, content: str) -> bool:
        """只更新文章正文相关字段,供 PlaywrightPool 后台回写。

        与 ``add_article`` 走 ``session.merge`` 不同,这里直接走 SQLAlchemy
        ``update``,避免触发 ``add_article`` 里 metadata 不变的 early-return
        导致 content 写不进 DB。

        Args:
            article_id: 主键 ID(经过 ``add_article`` 前缀规则调整后的最终值)。
            content: 抓到的 HTML 正文,空字符串 / ``"DELETED"`` 视为特殊值。

        Returns:
            True 表示成功写入,False 表示失败或文章不存在。
        """
        if not article_id:
            return False
        session = None
        try:
            session = self.get_session()
            # 查一下文章是否存在,顺便拿到 url 用于 description 兜底
            existing = session.query(Article).filter(Article.id == article_id).first()
            if existing is None:
                print_warning(f"update_article_content: article {article_id} 不存在")
                return False

            from core.models.base import DATA_STATUS
            from tools.fix import fix_html, sanitize_utf8

            updates = {}
            if content == "DELETED":
                updates["content"] = ""
                updates["content_html"] = ""
                updates["has_content"] = 0
                updates["status"] = DATA_STATUS.DELETED
            elif content:
                clean = sanitize_utf8(content) or ""
                updates["content"] = clean
                updates["content_html"] = fix_html(clean)
                updates["has_content"] = 1
                # 状态恢复为 ACTIVE(若之前被误标为 DELETED)
                if existing.status == DATA_STATUS.DELETED:
                    updates["status"] = DATA_STATUS.ACTIVE

            if not updates:
                return True  # 空内容,不写

            # 自动补 description(若原值为空)
            if content and content != "DELETED" and not (existing.description or "").strip():
                try:
                    from driver.wxarticle import Web
                    updates["description"] = Web.get_description(content)
                except Exception:
                    pass

            session.query(Article).filter(Article.id == article_id).update(updates)
            session.commit()
            return True
        except Exception as exc:  # noqa: BLE001
            if session is not None:
                try:
                    session.rollback()
                except Exception:
                    pass
            print_error(f"update_article_content 失败 [{article_id}]: {exc}")
            return False

        
    def get_articles(self, id:str=None, limit:int=30, offset:int=0) -> List[Article]: # type: ignore
        try:
            data = self.get_session().query(Article).limit(limit).offset(offset)
            return data
        except Exception as e:
            print(f"Failed to fetch Feed: {e}")
            return e # type: ignore   
             
    def get_all_mps(self) -> List[Feed]:
        """Get all Feed records"""
        try:
            return self.get_session().query(Feed).all()
        except Exception as e:
            print(f"Failed to fetch Feed: {e}")
            return e # type: ignore
            
    def get_mps_list(self, mp_ids:str) -> List[Feed]:
        try:
            ids=mp_ids.split(',')
            data =  self.get_session().query(Feed).filter(Feed.id.in_(ids)).all()
            return data
        except Exception as e:
            print(f"Failed to fetch Feed: {e}")
            return e # type: ignore
    def get_mps(self, mp_id:str) -> Optional[Feed]:
        try:
            ids=mp_id.split(',')
            data =  self.get_session().query(Feed).filter_by(id= mp_id).first()
            return data
        except Exception as e:
            print(f"Failed to fetch Feed: {e}")
            return e # type: ignore

    def get_faker_id(self, mp_id:str):
        data = self.get_mps(mp_id)
        return data.faker_id # type: ignore
    def expire_all(self):
        if self.Session:
            self.Session.expire_all()    
    def bind_event(self,session):
        # Session Events
        @event.listens_for(session, 'before_commit')
        def receive_before_commit(session):
            print("Transaction is about to be committed.")

        @event.listens_for(session, 'after_commit')
        def receive_after_commit(session):
            print("Transaction has been committed.")

        # Connection Events
        @event.listens_for(self.engine, 'connect')
        def connect(dbapi_connection, connection_record):
            print("New database connection established.")

        @event.listens_for(self.engine, 'close')
        def close(dbapi_connection, connection_record):
            print("Database connection closed.")
    def get_session(self):
        """获取新的数据库会话"""
        UseInThread=self.User_In_Thread
        def _session():
            if UseInThread:
                self.Session=scoped_session(self.session_factory)
                # self.Session=self.session_factory
            else:
                self.Session=self.session_factory
            # self.bind_event(self.Session)
            return self.Session
        
        
        if self.Session is None:
            _session()
        
        session = self.Session()  # type: ignore
        # session.expire_all()
        # session.expire_on_commit = True  # 确保每次提交后对象过期
        # 检查会话是否已经关闭
        if not session.is_active:
            from core.print import print_info
            print_info(f"[{self.tag}] Session is already closed.")
            _session()
            return self.Session() # type: ignore
        # 检查数据库连接是否已断开
        try:
            from core.models import User
            # 尝试执行一个简单的查询来检查连接状态
            session.query(User.id).count()
        except Exception as e:
            from core.print import print_warning
            print_warning(f"[{self.tag}] Database connection lost: {e}. Reconnecting...")
            self.init(self.connection_str)
            _session()
            return self.Session() # type: ignore
        return session
    def auto_refresh(self):
        # 定义一个事件监听器，在对象更新后自动刷新
        def receive_after_update(mapper, connection, target):
            print(f"Refreshing object: {target}")
        from core.models import MessageTask,Article
        event.listen(Article,'after_update', receive_after_update)
        event.listen(MessageTask,'after_update',receive_after_update)
        
    def session_dependency(self):
        """FastAPI依赖项，用于请求范围的会话管理"""
        session = self.get_session()
        try:
            yield session
        finally:
            session.remove()

# 全局数据库实例
DB = Db(User_In_Thread=True)
DB.init(cfg.get("db")) # type: ignore
