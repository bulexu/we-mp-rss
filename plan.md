# 文章采集队列并发改造计划

## 目标

将一次 `MessageTask` 触发的多公众号采集从**串行**改造为**可配置并发**，充分利用 redfox API 的 HTTP IO 等待空隙。

- 串行 → 并发，对调用方透明（`TaskQueue` API 不变）
- 并发数**可配置**，默认保守 3
- 失败隔离：单 feed 失败不影响其他
- 最小化对 content_queue / 系统状态接口 / ws 广播的影响

---

## 背景与关键约束

| 项 | 现状 | 并发可行性 | 备注 |
|---|---|---|---|
| redfox SDK | `redfox-python-sdk` 内部用 `httpx.Client` | ❌ `httpx.Client` 官方明示**非线程安全** | 必须做线程局部化 |
| 数据库 `core.db.Db` | SQLAlchemy + `scoped_session(User_In_Thread=True)` + 连接池 `pool_size=2, max_overflow=20` | ✅ 已就绪 | 多线程各拿独立 session |
| `asyncio.create_task(cascade_sync_service.report_task_result(...))` ([jobs/mps.py:133](jobs/mps.py#L133)) | 当前 silently noop（TaskQueue 线程没绑 loop） | ⚠️ 并发后会真正报错 | 必须改成跨线程调度 |
| `MessageTaskTracker.record_mp_result` | 已在 `with self._task_lock:` 下 | ✅ 线程安全 | 无需改 |
| `TaskQueue` (主队列) | 单线程 while 循环 | 本次**不动** | 保持 status / Redis / ws 语义不变 |
| `ContentTaskQueue` (补抓队列) | 单线程 | 本次**不动** | 用户只关心采集队列；补抓有人为 `Wait` 放慢 |
| `apis/mps.py:498` 添加公众号时的单次入队 | 直接 `TaskQueue.add_task(do_job, ...)` | 顺手统一走 `_run_batch` | 单 feed 也走相同入口 |

**主事件循环来源**：[main.py:133](main.py#L133) `asyncio.run(server.serve())`，需在 FastAPI 启动时把 loop 引用存到模块级。

---

## 改造方案（方案 B+）

保持 `TaskQueue` 串行语义不变，把"一次 MessageTask 触发的整批 feed 采集"在调度入口处用 `ThreadPoolExecutor` fan-out。

### 文件 1：`core/redfox/client.py` — redfox client 线程安全化

**改动**：

1. 删掉模块级单例 `_default_client`。
2. 引入按 `threading.get_ident()` 缓存的客户端池：
   ```python
   _local_clients: dict[int, "_RedfoxClient"] = {}
   _clients_lock = threading.Lock()

   def _get_default_client() -> "_RedfoxClient":
       tid = threading.get_ident()
       with _clients_lock:
           client = _local_clients.get(tid)
           if client is None:
               client = _RedfoxClient()
               _local_clients[tid] = client
           return client
   ```
3. 新增 `close_all_clients()`，遍历关闭所有客户端（用于关闭时清理，可选调用）。

**理由**：`httpx.Client` 实例不能跨线程共享，必须每线程一个。缓存池避免每请求重复初始化。`threading.Lock` 只在缓存 miss 时短暂竞争，热路径无锁。

### 文件 2：`core/loop.py`（新建）— 主事件循环引用 + 跨线程提交

```python
"""主事件循环引用与跨线程异步任务提交工具。

主线程（uvicorn）启动时通过 ``set_main_loop(asyncio.get_running_loop())``
保存 loop。任何后台线程需要调度异步协程时，调用 ``submit_async(coro)``。
"""
import asyncio
import threading
from typing import Optional, Coroutine, Any
from core.print import print_error, print_warning

_main_loop: Optional[asyncio.AbstractEventLoop] = None
_main_loop_lock = threading.Lock()


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    with _main_loop_lock:
        _main_loop = loop


def get_main_loop() -> Optional[asyncio.AbstractEventLoop]:
    return _main_loop


def submit_async(coro: Coroutine[Any, Any, Any]) -> Optional[asyncio.Future]:
    """从任意线程向主事件循环提交协程。
    
    主 loop 不可用时打印告警并返回 None,不抛出(避免污染主流程)。
    """
    loop = get_main_loop()
    if loop is None:
        print_warning("主事件循环未注册,跳过异步任务提交(常见于纯后台任务调度)")
        return None
    try:
        return asyncio.run_coroutine_threadsafe(coro, loop)
    except RuntimeError as exc:
        print_error(f"跨线程提交协程失败: {exc}")
        return None
```

### 文件 3：`web.py` — 启动 hook 保存主 loop

在 [web.py:54](web.py#L54) `app = FastAPI(...)` 后注册 lifespan：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _capture_main_loop(_app: FastAPI):
    from core.loop import set_main_loop
    set_main_loop(asyncio.get_running_loop())
    yield

# 在 app = FastAPI(...) 时挂入:
app = FastAPI(..., lifespan=_capture_main_loop)
```

### 文件 4：`core/config.py` + `config.yaml` — 新增配置项

```yaml
queue:
  max_workers: 3   # 文章采集并发数,推荐 2~5;1 等同串行
```

读取：`max_workers = int(cfg.get("queue.max_workers", 3))`，对老配置无破坏（缺省回退 3）。

### 文件 5：`jobs/mps.py` — 核心 fan-out

**改动 1：构造 `_run_batch`**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

max_workers = int(cfg.get("queue.max_workers", 3))  # 模块级常量


def _run_batch(feeds: list, task, isTest: bool, max_workers: int):
    """在 TaskQueue 单任务内并发跑整批 feed。"""
    if not feeds:
        return
    # 测试模式仍只跑 1 个(保留原有 break 语义)
    if isTest:
        target = feeds[:1]
        max_workers = 1
    else:
        target = feeds

    with ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="fe-fetch",
    ) as executor:
        futures = {
            executor.submit(do_job, feed, task, isTest): feed
            for feed in target
        }
        # 等待全部完成;do_job 内部已捕获 fetcher / webhook 异常,
        # 这里只在出现未预期异常时记录,但不抛出(避免整批被 TaskQueue 重试)
        for fut in as_completed(futures):
            feed = futures[fut]
            try:
                fut.result()
            except Exception as exc:
                print_error(
                    f"并发采集未捕获异常 [{feed.mp_name}]: {exc}"
                )
```

**改动 2：`add_job` 替换逐个入队为单批入队**

[add_job](jobs/mps.py#L231-L251) 当前循环 `for feed in feeds: TaskQueue.add_task(do_job, ...)`，替换为：

```python
def add_job(feeds=None, task=None, isTest=False):
    if isTest:
        TaskQueue.clear_queue()
    if feeds is None and task is not None:
        feeds = get_feeds(task)
    if task and not isTest and feeds:
        tracker.start_task(task.id, len(feeds))

    if not feeds:
        return

    task_label = (
        f"[测试]{task.name if task else 'batch'}"
        if isTest
        else f"{task.name if task else 'batch'}({len(feeds)} feeds)"
    )
    TaskQueue.add_task(
        _run_batch,
        feeds, task, isTest, max_workers,
        task_name=task_label,
    )
    print_success(TaskQueue.get_queue_info())
```

**改动 3：修复 cascade 跨线程上报**

[do_job](jobs/mps.py#L121-L135) 里的 `asyncio.create_task(...)` 改为：

```python
from core.loop import submit_async
# ...
result_data = [{
    "mp_id": mp.id,
    "mp_name": mp.mp_name,
    "article_count": len(mock_articles),
    "success_count": count,
    "timestamp": datetime.now().isoformat()
}]
submit_async(cascade_sync_service.report_task_result(task.id, result_data))
```

**注意**：`do_job` 的语义保持不变——它仍然接受单 feed，仍然调用 webhook / tracker。变化只在 `_run_batch` 包装层。

### 文件 6：`apis/mps.py:498-503` — 添加公众号时也走 `_run_batch`

```python
# 原:
TaskQueue.add_task(WxGather().Model().get_Articles, ..., task_name=mp_name)

# 改为:
from jobs.mps import _run_batch, max_workers as _mp_workers
TaskQueue.add_task(_run_batch, [feed], task=None, isTest=False,
                   _mp_workers, task_name=f"首次采集:{mp_name}")
```

或者更干净的方式：在 `apis/mps.py` 顶部加一个公共入口函数 `enqueue_fetch(feeds, task=None)`，所有调用方都用它。

### 文件 7：`jobs/fetch_no_article.py`（**保持不变**）

补抓队列不在本次范围。但要确认没有把 `ContentTaskQueue.add_task` 误改。

---

## 验证与回退

### 验证清单（手动 / 测试）

1. **并发生效**：跑一个 ≥ 5 个公众号的 MessageTask，日志时间戳应重叠（不再严格递增）。
2. **失败隔离**：手动让一个 feed 的 `faker_id` 写错，确认其它 feed 仍采集成功；`tracker` 进度计数对。
3. **数据库无重复**：`Article` 表的 `UNIQUE` 约束在并发下偶尔冲突——现有 `add_article` 已捕获 `Duplicate entry` 并降级为 warning，OK。
4. **redfox SDK 线程安全**：监控日志中无 `RuntimeError: Event loop is closed` / httpx 内部 state 错乱；观察一段时间内存。
5. **cascade 上报**：启用 cascade 模式后，上报任务结果没有报错；`core.loop.submit_async` 在 `get_main_loop() is None` 时打印 warning 不抛出。
6. **状态接口**：`/api/task_queue` / `/api/sys_info` 显示"批采"作为单条任务，pending/history 不爆炸。

### 回退

把 `queue.max_workers` 设为 `1` 即恢复串行，无需改代码。

---

## 风险与决策记录

| 风险 | 处理 |
|---|---|
| redfox SDK 线程不安全 → 并发错乱 | 每线程一个 `_RedfoxClient` 实例(线程局部缓存池) |
| asyncio.create_task 在非主线程调用 | 替换为 `submit_async` + `run_coroutine_threadsafe` |
| 默认并发过大触发 redfox 限流 | 默认 3，配置项 + 文档明确"推荐 2~5" |
| 并发下数据库连接耗尽 | `pool_size=2, max_overflow=20` 已足够；监控 |
| WebSocket 广播卡顿 | 现有广播已异步,TaskQueue 层不变,不影响 |
| 主事件循环未注册(纯后台 cron 场景) | `submit_async` 容错返回 None,主流程不抛 |
| `gc.collect()` 每任务调一次的成本 | 保留,单 batch 内多 feed 时一次性回收影响小 |
| 现有 `_run_batch` 模块级常量 `max_workers` 在 cron 触发时被 import 一次 | OK,`cfg` 读取时即时生效(无需重启) |

---

## 改动文件汇总

| 文件 | 性质 | 工作量 |
|---|---|---|
| `core/redfox/client.py` | 改造线程局部化 | 小 |
| `core/loop.py` | 新建 | 小 |
| `web.py` | 加 lifespan hook | 小 |
| `config.yaml` (+ `.example`) | 新增 `queue.max_workers` | 小 |
| `jobs/mps.py` | 增 `_run_batch`，改 `add_job`，改 cascade 上报 | 中 |
| `apis/mps.py:498` | 改用统一入口 | 小 |
| `README.md` / `config.yaml.example` | 文档更新 | 小 |

**预计总计 6 文件改动 + 1 新建 + 1 文档**。