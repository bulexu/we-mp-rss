from datetime import datetime, timedelta
from core.models.article import Article
from .article import UpdateArticle,Update_Over
import core.db as db
from core.wx import WxGather
from core.log import logger
from core.task import TaskScheduler
from core.models.feed import Feed
from core.config import cfg,DEBUG
from core.print import print_info,print_success,print_error
from core.redis_client import clear_env_exception
wx_db=db.Db(tag="任务调度")
def fetch_all_article():
    print("开始更新")
    wx=WxGather().Model()
    try:
        # 获取公众号列表
        mps=db.DB.get_all_mps()
        for item in mps:
            try:
                wx.get_Articles(item.faker_id,CallBack=UpdateArticle,Mps_id=item.id,Mps_title=item.mp_name, MaxPage=1)
            except Exception as e:
                print(e)
        print(wx.articles) 
    except Exception as e:
        print(e)         
    finally:
        logger.info(f"所有公众号更新完成,共更新{wx.all_count()}条数据")


def test(info:str):
    print("任务测试成功",info)

from core.models.message_task import MessageTask
# from core.queue import TaskQueue
from .webhook import web_hook
interval=int(cfg.get("interval",60)) # 兼容历史配置;get_Articles 已不再读取
def do_job(mp=None,task:MessageTask=None,isTest=False):
        """执行单个公众号的采集任务"""
        # TaskQueue.add_task(test,info=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        # print("执行任务", task.mps_id)
        print(f"执行任务 (测试模式: {isTest})")
        
        # 初始化变量，确保在所有分支中都有定义
        count = 0
        all_count = 0
        mock_articles = []
        success = False
        error_msg = None
        
        try:
            if isTest:
                # 测试模式使用模拟数据
                mock_articles = [{
                    "id": "test-article-001",
                    "mp_id": mp.id,
                    "title": "测试文章标题",
                    "pic_url": "https://via.placeholder.com/300x200",
                    "url": "https://example.com/test-article",
                    "description": "这是一篇测试文章的描述内容，用于测试webhook功能是否正常。",
                    "publish_time": (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
                    "content": "<p>这是测试文章的正文内容。</p>"
                }]
                count = 1
                success = True
            else:
                wx=WxGather().Model()
                try:
                    wx.get_Articles(mp.faker_id,CallBack=UpdateArticle,Mps_id=mp.id,Mps_title=mp.mp_name, MaxPage=1,Over_CallBack=Update_Over)
                    success = True
                except Exception as e:
                    print_error(f"获取文章失败 [{mp.mp_name}]: {e}")
                    error_msg = str(e)
                    # 不抛出异常，继续执行后续流程
                finally:
                    count = wx.all_count() if wx else 0
                    mock_articles = wx.articles if wx else []
                    all_count += count

            # 执行 webhook 通知
            try:
                from jobs.webhook import MessageWebHook
                tms=MessageWebHook(task=task,feed=mp,articles=mock_articles)
                web_hook(tms, is_test=isTest)
                print_success(f"任务({task.id})[{mp.mp_name}]执行成功,{count}成功条数")
                
                # 采集成功，清除该公众号的环境异常记录
                if not isTest and success and count > 0:
                    try:
                        clear_env_exception(mp_id=mp.id)
                    except Exception as e:
                        print_error(f"清除环境异常记录失败: {e}")
                        
            except Exception as e:
                print_error(f"Webhook执行失败 [{mp.mp_name}]: {e}")
                if not error_msg:
                    error_msg = f"Webhook: {str(e)}"
            
            # 级联节点：上报任务执行结果到父节点
            from jobs.cascade_sync import cascade_sync_service
            from core.loop import submit_async
            if not isTest and mock_articles:
                try:
                    result_data = [{
                        "mp_id": mp.id,
                        "mp_name": mp.mp_name,
                        "article_count": len(mock_articles) if not isTest else 1,
                        "success_count": count if not isTest else 1,
                        "timestamp": datetime.now().isoformat()
                    }]
                    # 通过主事件循环跨线程上报,不阻塞当前 worker 线程
                    submit_async(cascade_sync_service.report_task_result(task.id, result_data))
                except Exception as e:
                    print_error(f"上报任务结果失败: {str(e)}")
                    
        except Exception as e:
            error_msg = str(e)
            print_error(f"任务执行异常 [{mp.mp_name}]: {e}")
            raise  # 重新抛出，让队列的重试机制处理
        
        finally:
            # 记录执行结果到追踪器。
            # 注意:执行无异常但抓到 0 条数据(账号近期未更新)不算失败。
            # 只有 fetcher / webhook 真正抛异常才算 failed,与上方
            # ``print_success(f"任务(...)执行成功,{count}成功条数")`` 保持一致。
            if task and not isTest:
                tracker.record_mp_result(
                    task_id=task.id,
                    mp_name=mp.mp_name,
                    success=success,
                    article_count=count,
                    error=error_msg
                )

from core.queue import TaskQueue

# 任务执行追踪器
import threading
class MessageTaskTracker:
    """消息任务执行追踪器"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks = {}
                    cls._instance._task_lock = threading.Lock()
        return cls._instance
    
    def start_task(self, task_id: str, total_mps: int) -> None:
        """开始追踪一个消息任务"""
        with self._task_lock:
            self._tasks[task_id] = {
                'total': total_mps,
                'completed': 0,
                'failed': 0,
                'start_time': datetime.now().isoformat(),
                'mp_results': []
            }
    
    def record_mp_result(self, task_id: str, mp_name: str, success: bool, article_count: int = 0, error: str = None) -> None:
        """记录单个公众号的执行结果"""
        with self._task_lock:
            if task_id not in self._tasks:
                return

            task_info = self._tasks[task_id]
            if success:
                task_info['completed'] += 1
            else:
                task_info['failed'] += 1

            task_info['mp_results'].append({
                'mp_name': mp_name,
                'success': success,
                'article_count': article_count,
                'error': error,
                'time': datetime.now().isoformat()
            })

            # 打印进度
            progress = task_info['completed'] + task_info['failed']
            print_info(f"任务进度 [{task_id}]: {progress}/{task_info['total']} (成功:{task_info['completed']}, 失败:{task_info['failed']})")

            # 检查是否全部完成
            if progress >= task_info['total']:
                self._finish_task(task_id)

        # 同步更新队列子任务状态为 completed/failed(保留到 batch 结束),
        # 让前端能看到"哪些 feed 还在跑、哪些已完成/失败"。
        # 解锁后再调,避免与 _subtasks_lock 嵌套死锁。
        try:
            TaskQueue.mark_subtask_completed(
                mp_name,
                success=success,
                error=error or "",
            )
        except Exception as mark_exc:  # noqa: BLE001
            print_error(f"标记 subtask 完成态失败 [{mp_name}]: {mark_exc}")
    
    def _finish_task(self, task_id: str) -> None:
        """任务完成"""
        if task_id not in self._tasks:
            return
        
        task_info = self._tasks[task_id]
        print_success(f"\n{'='*50}")
        print_success(f"消息任务 [{task_id}] 执行完成!")
        print_success(f"总计: {task_info['total']} 个公众号")
        print_success(f"成功: {task_info['completed']} 个")
        print_error(f"失败: {task_info['failed']} 个")
        print_success(f"{'='*50}\n")
    
    def get_task_status(self, task_id: str) -> dict:
        """获取任务状态"""
        with self._task_lock:
            return self._tasks.get(task_id, {})

tracker = MessageTaskTracker()
import threading

# 并发采集上限,从配置读取。redfox 是付费 API,过大会触发限流;
# 设为 1 即恢复串行,作为安全回退点。
max_workers = int(cfg.get("queue.max_workers", 3))


def _run_batch(feeds, task, isTest, max_workers):
    """并发执行一批 feed 的采集。

    由 ``TaskQueue`` 作为单条任务调度,内部用 ``ThreadPoolExecutor`` 把
    每个 feed 派发到独立线程;``do_job`` 内部已捕获 fetcher / webhook
    异常并通过 ``tracker`` 记录结果,这里只在出现未预期异常时打印告警,
    不抛出 —— 避免 TaskQueue 整体重试造成已成功的公众号重复采集。

    为支持"并行子任务"前端展示,每个 feed 实际执行前后会通过
    :meth:`TaskQueue.add_subtask` / :meth:`remove_subtask` 注册 / 注销
    一条 ``mp_name`` 子任务;batch 结束时 ``clear_subtasks`` 清干净。

    Args:
        feeds: 待采集 feed 列表(可能为空)。
        task: 关联的 ``MessageTask``,``None`` 表示临时批量入队(如添加公众号
              时的首次采集)。
        isTest: 测试模式——仍只跑 1 个 feed 以快速验证。
        max_workers: 并发线程数上限;测试模式强制改写为 1。
    """
    if not feeds:
        return

    target = feeds
    effective_workers = max(1, int(max_workers or 1))
    if isTest:
        target = feeds[:1]
        effective_workers = 1

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 清掉上一批可能残留的子任务(理论上不会发生,因为 TaskQueue 串行调度
    # 单条 _run_batch,但防御性调用避免 stale)。
    TaskQueue.clear_subtasks()

    def _run_with_subtask(feed):
        """包一层:每个 feed 实际执行前注册,结束后标记完成/失败。

        不在 ``finally`` 里 ``remove_subtask`` —— 因为 :func:`do_job` 内部
        已通过 :class:`MessageTaskTracker` 调用 :meth:`TaskQueue.mark_subtask_completed`,
        把 subtask 状态切到 ``completed`` / ``failed`` 并保留到 batch 结束。
        这里再 remove 会立即把刚标记的状态擦掉,前端看不到完成态。

        ``do_job`` 通常不抛异常(fetcher 错误已在内部捕获);万一真抛出来,
        这里兜底标 failed 后再 rethrow,让外层 :func:`_run_batch` 记录。
        """
        TaskQueue.add_subtask(feed.mp_name)
        try:
            do_job(feed, task, isTest)
        except Exception as unhandled_exc:  # noqa: BLE001
            TaskQueue.mark_subtask_completed(
                feed.mp_name,
                success=False,
                error=f"unhandled: {unhandled_exc}",
            )
            raise

    try:
        with ThreadPoolExecutor(
            max_workers=effective_workers,
            thread_name_prefix="fe-fetch",
        ) as executor:
            futures = {
                executor.submit(_run_with_subtask, feed): feed
                for feed in target
            }
            for fut in as_completed(futures):
                feed = futures[fut]
                try:
                    fut.result()
                except Exception as exc:  # noqa: BLE001
                    print_error(
                        f"并发采集未捕获异常 [{feed.mp_name}]: {exc}"
                    )
    finally:
        # 整个 batch 结束后,无论是否中途异常,确保子任务列表清空。
        TaskQueue.clear_subtasks()


def add_job(feeds: list[Feed] = None, task: MessageTask = None, isTest=False):
    """把整批 feed 作为单个 TaskQueue 任务入队,由 ``_run_batch`` 内部并发执行。

    之前是逐个 feed 入队(每个 feed 一条 TaskQueue 任务),导致 TaskQueue
    的 in-flight 状态被大量细粒度任务填满,且无法利用 redfox HTTP IO
    等待空隙做并行。改造后:一次 MessageTask 触发的整批采集 = 1 条
    TaskQueue 任务,内部由线程池并行处理。
    """
    if isTest:
        TaskQueue.clear_queue()

    # 动态获取公众号列表:如果 feeds 为 None 且 task 不为 None,则动态获取
    if feeds is None and task is not None:
        feeds = get_feeds(task)

    # 初始化任务追踪(按整批的 feed 数)
    if task and not isTest and feeds:
        tracker.start_task(task.id, len(feeds))

    if not feeds:
        print_success(TaskQueue.get_queue_info())
        return

    # 任务显示名称(用于 TaskQueue 前端 / 日志)
    name = task.name if task else "batch"
    prefix = "[测试]" if isTest else ""
    task_label = f"{prefix}{name}({len(feeds)} feeds)"

    TaskQueue.add_task(
        _run_batch,
        list(feeds),
        task,
        isTest,
        max_workers,
        task_name=task_label,
    )
    print(f"{task_label},加入队列成功(并发上限 {max_workers})")
    print_success(TaskQueue.get_queue_info())
import json
def get_feeds(task:MessageTask=None):
     mps = json.loads(task.mps_id)
     ids=",".join([item["id"]for item in mps])
     mps=wx_db.get_mps_list(ids)
     if len(mps)==0:
        mps=wx_db.get_all_mps()
     return mps
scheduler=TaskScheduler()
def reload_job():
    print_success("重载任务")
    scheduler.clear_all_jobs()
    TaskQueue.clear_queue()
    start_job()

def run(job_id:str=None,isTest=False):
    from .taskmsg import get_message_task
    tasks=get_message_task(job_id)
    if not tasks:
        print("没有任务")
        return None
    for task in tasks:
            #添加测试任务
            from core.print import print_warning
            print_warning(f"{task.name} 添加到队列运行")
            # 修改：只传递 task，在 add_job 中动态获取 feeds
            add_job(task=task,isTest=isTest)
            pass
    return tasks
def start_job(job_id:str=None):
    from .taskmsg import get_message_task
    tasks=get_message_task(job_id)
    if not tasks:
        print("没有任务")
        return
    tag="定时采集"
    for task in tasks:
        cron_exp=task.cron_exp
        if not cron_exp:
            print_error(f"任务[{task.id}]没有设置cron表达式")
            continue

        # 修改：使用关键字参数传递 task，避免与 feeds 混淆
        job_id=scheduler.add_cron_job(add_job,cron_expr=cron_exp,kwargs={'task': task},job_id=str(task.id),tag="定时采集")
        print(f"已添加任务: {job_id}")
    scheduler.start()
    print("启动任务")
def start_fix_article():
      #开启自动同步未同步 文章任务
    from jobs.fetch_no_article import start_sync_content
    start_sync_content()

def start_article_stats_refresh():
    """启动文章统计定时刷新任务"""
    from core.article_lax import refresh_article_info
    from core.config import cfg
    
    # 获取刷新间隔,默认5分钟
    refresh_interval = int(cfg.get("server.article_stats_refresh_interval", 3600))
    
    # 添加定时任务,每隔指定时间刷新一次文章统计
    scheduler.add_cron_job(
        refresh_article_info,
        cron_expr=f"*/{refresh_interval // 60} * * * *",  # 每 N 分钟执行一次
        job_id="article_stats_refresh",
        tag="文章统计刷新"
    )
    print_success(f"文章统计定时刷新任务已启动,间隔: {refresh_interval}秒")

if __name__ == '__main__':
    # do_job()
    # start_all_task()
    pass