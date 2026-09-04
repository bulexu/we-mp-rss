<div align=center>
<img src="static/logo.svg" alt="We-MP-RSS Logo" width="20%">
<h1>WeRSS — 微信公众号订阅助手</h1>

[![Python](https://img.shields.io/badge/python-3.13.1+-red.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Version](https://img.shields.io/badge/version-v2.0.0-blue.svg)]()

[中文](README.zh-CN.md) | [English](ReadMe.md)

自托管的微信公众号内容订阅与 RSS 生成工具。自 1.6 起数据层已脱离微信公众平台
—— 无需扫码授权、可无人值守运行。
</div>

---

## 快速开始（Docker）

镜像发布在阿里云个人版仓库：

```bash
docker run -d --name we-mp-rss \
  -p 8001:8001 \
  -v ./data:/app/data \
  --env-file ./.env \
  crpi-qp8hiqijfnilf93t.cn-hangzhou.personal.cr.aliyuncs.com/bulexu/we-mp-rss:v2.0.0
```

浏览器访问 `http://<你的 IP>:8001/`。默认账号 `admin` / `admin@123`，**首次
登录后请立即修改密码**（右上角用户菜单 → 修改密码）。

镜像**不**携带 `REDFOX_API_KEY`，通过 `.env` 注入：

```bash
# .env（一行一个 key，不要加引号）
REDFOX_API_KEY=ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 升级

```bash
docker stop we-mp-rss && docker rm we-mp-rss
docker pull crpi-qp8hiqijfnilf93t.cn-hangzhou.personal.cr.aliyuncs.com/bulexu/we-mp-rss:v2.0.0
# 重新执行上面那条 docker run（data/ 挂在宿主机，数据不会丢）
```

## v2.0.0 — Redfox 迁移（自 1.6 起）

微信公众号的数据层已重写为调用 [redfox.hk](https://redfox.hk) 无状态 REST
接口。原扫码会话链路（`mp.weixin.qq.com/cgi-bin/searchbiz` + `appmsgpublish`
+ cookie/token 管理）已完全移除。

| 用途 | 端点 | 对应方法 |
| --- | --- | --- |
| 按关键词搜索公众号 | `/story/api/gzh/data/searchUser` | `search_user` |
| 按 ID 精确查询公众号 | `/story/api/gzh/data/accountInfo` | `get_account_info` |
| 拉取公众号作品列表 | `/story/api/gzh/data/queryWorkList` | `query_work_list` |
| 文章正文（HTML） | `driver.wxarticle.Web.get_article_content` | Playwright 抓取（未变） |

**配置**：

- `REDFOX_API_KEY`（环境变量）或 `redfox.api_key`（配置文件）— 必填。
  在 [redfox.hk/settings/api-keys](https://redfox.hk/settings/api-keys) 申请。
- `REDFOX_BASE_URL`（环境变量，默认 `https://redfox.hk`）— 覆盖 redfox 入口。

每一次 redfox 调用都会记录到 Redis，可通过后台 **系统 → Redfox 日志** 查看
（含响应码、耗时、错误信息），便于排查。

完整模块映射见 [docs/redfox/INTEGRATION.md](docs/redfox/INTEGRATION.md)。

## 功能特性

- 微信公众号内容抓取与解析
- RSS 订阅源生成（RSS 2.0，支持 CDATA / 全文 / 封面）
- Web 管理后台（Vue 3 + Arco Design + Vite）
- 定时自动更新（间隔可配）
- SQLite（默认）/ MySQL / PostgreSQL 数据库
- 多种抓取模型（`app` / `web` / `api`）—— 见 `core/wx/model/`
- 自定义 RSS 标题、描述、封面、分页大小
- 自定义通知渠道（钉钉 / 微信群机器人 / 飞书 / 自定义 Webhook）
- HTML 内容过滤规则（全局 + 公众号专属）
- 导出 Markdown / DOCX / PDF / JSON
- 13 套主题（含深色 / 护眼模式）
- 响应式分页（PC 翻页、移动端加载更多）
- **级联系统** — 父子节点架构，分布式采集
- **环境异常统计** — 自动追踪各订阅的抓取失败
- **Headers / Cookies 认证** — 用于需要鉴权的 Webhook 调用
- **配置缓存** — Redis / Memcached / 内存三级
- **Access Key (AK) 认证** — 程序化 API 访问（`Authorization: AK-SK {ak}:{sk}`）
- **Redfox 数据接口** — 无状态获取公众号信息与作品列表

## 界面截图

- 登录界面  
  <img src="docs/登录.png" alt="登录" width="80%"/><br/>
- 主界面  
  <img src="docs/主界面.png" alt="主界面" width="80%"/><br/>
- 添加订阅（已切换为 redfox 搜索）  
  <img src="docs/添加订阅.png" alt="添加订阅" width="80%"/><br/>

## 系统架构

前后端分离，后端将预编译的前端作为静态资源提供：

- 后端：Python 3.13 + FastAPI + Uvicorn
- 前端：Vue 3 + Vite 8 + rolldown
- 数据库：SQLite（默认）/ MySQL / PostgreSQL
- 缓存：Redis（可选，Redfox 日志 / 多 worker 会话需要）
- 任务队列：进程内默认，级联场景走 Redis

```
┌──────────────┐    ┌────────────────────────────────────┐
│  Vue 3 SPA   │    │  FastAPI (uvicorn, port 8001)      │
│  (static/)   │◄──►│  ├─ /api/v1/wx  (article/feed/...) │
└──────────────┘    │  ├─ /api/v1/wx/redfox  (stats/logs)│
                    │  └─ /story/api/gzh/data/... (redfox)│
                    └────────────┬───────────────────────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
           SQLite/MySQL     Redis (logs,    redfox.hk
                            cache, queue)
```

## 安装（开发环境）

### 环境要求

- Python ≥ 3.13.1
- Node ≥ 20.18.3

### 后端

```bash
git clone <你的 fork 仓库> we-mp-rss
cd we-mp-rss
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp .env.example .env       # 填入 REDFOX_API_KEY
python main.py -job True -init True
```

`-init` 标志会创建 SQLite 数据库与默认 admin 账号；`-job` 开启定时任务。
`main.py` 通过 `load_dotenv()` 自动加载 `.env`（方便本地直接运行）；在
Docker 部署中应通过 compose 的 `env_file:` 注入。

后端通过 `static/` 目录为前端页面提供静态资源。

### 前端

```bash
cd web_ui
npm install --legacy-peer-deps
npm run dev          # http://localhost:3000
```

### 生产构建（同步 static/）

后端实际服务的是 `static/` 目录里的**预编译产物**。Dockerfile 头部的注释也
写明：「前端编译非常占用工作流时间 ,可以 编译后复制到static目录再提交pull
request」。标准构建顺序：

```bash
# 1. 编译前端
cd web_ui && npm run build && cd ..

# 2. 同步 dist/ → static/（这是后端实际服务的目录）
rsync -a --delete web_ui/dist/ static/

# 3. 构建 Docker 镜像
docker buildx build --platform=linux/amd64 \
  -f ./Dockerfile \
  -t crpi-qp8hiqijfnilf93t.cn-hangzhou.personal.cr.aliyuncs.com/bulexu/we-mp-rss:v2.0.0 \
  .
```

> 镜像**不**包含 `.env` —— `.dockerignore` 已排除。运行时通过 `env_file:`
> 或 `-e` 注入 `REDFOX_API_KEY`。

## 环境变量

所有变量由 `core/config.py` 解析，支持 `config.yaml` 中的 `${VAR:-default}`
语法或操作系统环境变量。

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `APP_NAME` | `we-mp-rss` | 应用名 |
| `SERVER_NAME` | `we-mp-rss` | 服务名 |
| `WEB_NAME` | `WeRSS微信公众号订阅助手` | 前端显示名 |
| `ENABLE_JOB` | `True` | 是否启用定时任务 |
| `AUTO_RELOAD` | `False` | uvicorn `--reload`（开发用） |
| `THREADS` | `2` | uvicorn worker 数 |
| `DB` | `sqlite:///data/db.db` | 数据库连接串 |
| `REDFOX_API_KEY` | — | **必填**。redfox.hk API Key |
| `REDFOX_BASE_URL` | `https://redfox.hk` | redfox API 入口 |
| `DINGDING_WEBHOOK` | 空 | 钉钉通知 Webhook |
| `WECHAT_WEBHOOK` | 空 | 微信群机器人 Webhook |
| `FEISHU_WEBHOOK` | 空 | 飞书 Webhook |
| `CUSTOM_WEBHOOK` | 空 | 自定义 Webhook |
| `SECRET_KEY` | `we-mp-rss` | JWT 签名密钥 —— **生产环境务必修改** |
| `USER_AGENT` | `Mozilla/...` | 出站请求的 User-Agent |
| `SPAN_INTERVAL` | `10` | 定时任务执行间隔（秒） |
| `WEBHOOK.CONTENT_FORMAT` | `html` | 通知中文章正文的格式 |
| `PORT` | `8001` | API 端口 |
| `DEBUG` | `False` | 调试模式 |
| `MAX_PAGE` | `5` | 单次抓取最大页数 |
| `RSS_BASE_URL` | 空 | RSS 公网域名 |
| `RSS_LOCAL` | `False` | 使用本地 RSS 链接而非 `RSS_BASE_URL` |
| `RSS_TITLE` | 空 | 覆盖 feed 标题 |
| `RSS_DESCRIPTION` | 空 | 覆盖 feed 描述 |
| `RSS_COVER` | 空 | 覆盖 feed 封面 |
| `RSS_FULL_CONTEXT` | `True` | 是否在 feed 中包含全文 |
| `RSS_ADD_COVER` | `True` | 是否在 feed item 中插入封面 |
| `RSS_CDATA` | `False` | 正文用 `<![CDATA[]]>` 包裹 |
| `RSS_PAGE_SIZE` | `30` | feed 单页条数 |
| `TOKEN_EXPIRE_MINUTES` | `4320` | 登录会话有效期（分钟） |
| `CACHE.DIR` | `./data/cache` | 缓存目录 |
| `ARTICLE.TRUE_DELETE` | `False` | 物理删除 vs 软删除 |
| `GATHER.CONTENT` | `True` | 是否采集正文 |
| `GATHER.MODEL` | `app` | 采集模型（`app` / `web` / `api`） |
| `GATHER.CONTENT_AUTO_CHECK` | `False` | 定期回填缺失的正文 |
| `GATHER.CONTENT_AUTO_INTERVAL` | `59` | 回填间隔（分钟） |
| `GATHER.CONTENT_MODE` | `web` | 内容修正模式 |
| `SAFE_HIDE_CONFIG` | `db,secret,token,notice.wechat,notice.feishu,notice.dingding` | 系统信息页中隐藏的 key |
| `LOG_FILE` | 空 | 日志文件路径（空则输出到 stdout） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `EXPORT_PDF` | `False` | 是否启用 PDF 导出 |
| `EXPORT_PDF_DIR` | `./data/pdf` | PDF 输出目录 |
| `EXPORT_MARKDOWN` | `False` | 是否启用 Markdown 导出 |
| `EXPORT_MARKDOWN_DIR` | `./data/markdown` | Markdown 输出目录 |

## Access Key 认证

用于程序化访问 API，避免暴露管理员密码。

### 创建 AK

1. 登录后台，左侧菜单 → **Access Key 管理**
2. 点击 **创建 Access Key**
3. 填写名称、描述、权限、过期时间
4. **妥善保存 Access Key 与 Secret**（Secret 仅展示一次）

### 使用 AK

```bash
curl -H "Authorization: AK-SK {access_key}:{secret_key}" \
     http://localhost:8001/api/feeds
```

```python
import requests
r = requests.get(
    "http://localhost:8001/api/feeds",
    headers={"Authorization": f"AK-SK {access_key}:{secret_key}"},
)
print(r.json())
```

详细文档：[docs/AK_Authentication_Guide.md](docs/AK_Authentication_Guide.md)。

## HTML 内容过滤规则

抓取正文时按规则清理广告、推荐位等无用元素，支持全局或按公众号粒度配置。

- **作用域**：全局（不指定 `mp_id`）或公众号专属
- **优先级**：0-100，数值越大越先执行
- **过滤方式**：
  - 按 HTML `id` 移除
  - 按 CSS `class` 移除
  - 按 CSS 选择器移除
  - 按属性过滤（如 `data-type="ad"`）
  - 按正则表达式移除
  - 剥离常见元素（`<script>`、`<style>`、注释等）

```bash
# 列表
GET    /api/filter-rules

# 新建
POST   /api/filter-rules
{
  "mp_id": "[]",                  # "[]" 表示全局
  "rule_name": "全局广告清理",
  "priority": 10,
  "remove_ids": ["ad-banner"],
  "remove_classes": ["ad-container"]
}

# 更新 / 删除
PUT    /api/filter-rules/{id}
DELETE /api/filter-rules/{id}
```

## 常见问题

**默认账号密码？** `admin` / `admin@123`，首次登录后请立即修改。

**`/mps/search` 没结果？** redfox.hk 公共库只收录热门公众号。冷门账号请在添加
订阅时直接粘贴 `fakeid`（Base64 编码的 `bizInfo`）或 `wxId`。

**去哪里申请 `REDFOX_API_KEY`？** 在
[redfox.hk](https://redfox.hk?source=redfox_api_md) 注册后到
[API Keys](https://redfox.hk/settings/api-keys?source=redfox_api_md) 创建。

**拉了新镜像后后台界面没变化？** 后端服务的是 `static/` 里的预编译产物，如果
只更新镜像但没重建 `web_ui/dist/ → static/`，UI 仍是旧版。请按上文
**生产构建** 一节重新执行三步。

**搜索返回空但 Redfox 日志也是空的？** `REDFOX_API_KEY 未配置` 是在
`_headers()` 阶段抛出的（在 `_post()` 之前），不会写日志。请看 uvicorn
stdout 或后台「系统信息」页里的 redfox 状态块。

**怎么改数据库？** 设置 `DB` 环境变量或编辑 `config.yaml` 的 `db:`：

```ini
# SQLite
DB=sqlite:///data/db.db
# MySQL
DB=mysql+pymysql://<user>:<password>@<host>/<db>?charset=utf8mb4
# PostgreSQL
DB=postgresql://<user>:<password>@<host>/<db>
```

## 许可

MIT
