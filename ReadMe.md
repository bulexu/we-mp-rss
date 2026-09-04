<div align=center>
<img src="static/logo.svg" alt="We-MP-RSS Logo" width="20%">
<h1>WeRSS — WeChat Official Account RSS Subscription Assistant</h1>

[![Python](https://img.shields.io/badge/python-3.13.1+-red.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Version](https://img.shields.io/badge/version-v2.0.0-blue.svg)]()

[中文](README.zh-CN.md) | [English](ReadMe.md)

A self-hosted tool for subscribing to and managing WeChat Official Account
content and generating RSS feeds. Since v1.6 the data layer is decoupled from
the WeChat public platform — no QR-code scanning session is required, and the
service can be run unattended on a server.
</div>

---

## Quick Start (Docker)

The image is published to the Aliyun personal registry.

```bash
docker run -d --name we-mp-rss \
  -p 8001:8001 \
  -v ./data:/app/data \
  --env-file ./.env \
  crpi-qp8hiqijfnilf93t.cn-hangzhou.personal.cr.aliyuncs.com/bulexu/we-mp-rss:v2.0.0
```

Then visit `http://<your-ip>:8001/`. Default credentials: `admin` / `admin@123`
— **change them on first login** (top-right user menu → Change Password).

The image does **not** bundle a `REDFOX_API_KEY`. Pass it via `.env`:

```bash
# .env (one line per key, no quotes)
REDFOX_API_KEY=ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Upgrade

```bash
docker stop we-mp-rss && docker rm we-mp-rss
docker pull crpi-qp8hiqijfnilf93t.cn-hangzhou.personal.cr.aliyuncs.com/bulexu/we-mp-rss:v2.0.0
# re-run the docker run command above (data/ is on a host volume — preserved)
```

## v2.0.0 — Redfox Migration (since v1.6)

The WeChat data layer was rewritten to use the stateless
[redfox.hk](https://redfox.hk) REST API. The old QR-code-scan flow
(`mp.weixin.qq.com/cgi-bin/searchbiz` + `appmsgpublish` + cookie/token
management) is fully removed.

| Concern | Endpoint | Method |
| --- | --- | --- |
| Search an account by keyword | `/story/api/gzh/data/searchUser` | `search_user` |
| Get an account by ID | `/story/api/gzh/data/accountInfo` | `get_account_info` |
| Get article list for an account | `/story/api/gzh/data/queryWorkList` | `query_work_list` |
| Article body (HTML) | `driver.wxarticle.Web.get_article_content` | Playwright scrape (unchanged) |

Configuration:

- `REDFOX_API_KEY` (env) or `redfox.api_key` (config) — required. Get a key at
  [redfox.hk/settings/api-keys](https://redfox.hk/settings/api-keys).
- `REDFOX_BASE_URL` (env, default `https://redfox.hk`) — override the host.

Every redfox call is recorded in Redis and viewable under
**System → Redfox 日志** in the admin UI. Failed calls and their error messages
are kept for debugging.

See [docs/redfox/INTEGRATION.md](docs/redfox/INTEGRATION.md) for the full
module map.

## Features

- WeChat Official Account content scraping and parsing
- RSS feed generation (RSS 2.0 with optional CDATA / full-text / cover)
- Web admin UI (Vue 3 + Arco Design + Vite)
- Scheduled auto-update with configurable interval
- SQLite (default) / MySQL / PostgreSQL backends
- Configurable scraping model (`app` / `web` / `api`) — `core/wx/model/`
- Custom RSS title, description, cover, pagination size
- Custom notification channels (DingTalk / WeChat work-bot / Feishu / Custom Webhook)
- HTML content filtering rules (global + per-account)
- Article export: Markdown / DOCX / PDF / JSON
- 13 UI themes (light / dark / sepia)
- Responsive pagination (PC click-nav / Mobile load-more)
- **Cascade System** — parent-child node architecture for distributed collection
- **Environment Exception Statistics** — automatic per-feed failure tracking
- **Headers and Cookies Authentication** — for authenticated webhook calls
- **Configuration Cache** — Redis / Memcached / in-memory
- **Access Key (AK) auth** — programmatic API access via `Authorization: AK-SK {ak}:{sk}`
- **Redfox Data API** — stateless account/article fetching, no login session

## Screenshots

- Login Interface  
  <img src="docs/登录.png" alt="Login" width="80%"/><br/>
- Main Interface  
  <img src="docs/主界面.png" alt="Main Interface" width="80%"/><br/>
- Add Subscription (now powered by redfox search)  
  <img src="docs/添加订阅.png" alt="Add Subscription" width="80%"/><br/>

## System Architecture

Front-end / back-end separation, with the backend serving the prebuilt
frontend as static files:

- Backend: Python 3.13 + FastAPI + Uvicorn
- Frontend: Vue 3 + Vite 8 + rolldown
- Database: SQLite (default) / MySQL / PostgreSQL
- Cache: Redis (optional, required for "Redfox 日志" / multi-worker sessions)
- Task queue: in-process for default, Redis-backed for cascade workers

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

## Installation (Development)

### Requirements

- Python ≥ 3.13.1
- Node ≥ 20.18.3

### Backend

```bash
git clone <your-fork-url> we-mp-rss
cd we-mp-rss
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp .env.example .env       # then fill in REDFOX_API_KEY
python main.py -job True -init True
```

The `-init` flag creates the SQLite DB and the default `admin` user.
The `-job` flag enables the scheduler. `main.py` auto-loads `.env` via
`load_dotenv()` for direct dev runs; in Docker the key is injected via
`env_file:` (see `compose/*.yaml`).

The backend serves the frontend at `/` from the `static/` directory.

### Frontend

```bash
cd web_ui
npm install --legacy-peer-deps
npm run dev          # http://localhost:3000
```

### Production build (static/ sync)

The backend serves the **prebuilt** frontend from `static/`. The Dockerfile
header reminds: "前端编译非常占用工作流时间 ,可以 编译后复制到static目录再
提交pull request". The build sequence is therefore:

```bash
# 1. Build the SPA
cd web_ui && npm run build && cd ..

# 2. Sync dist/ → static/ (the directory the backend actually serves)
rsync -a --delete web_ui/dist/ static/

# 3. Build the Docker image
docker buildx build --platform=linux/amd64 \
  -f ./Dockerfile \
  -t crpi-qp8hiqijfnilf93t.cn-hangzhou.personal.cr.aliyuncs.com/bulexu/we-mp-rss:v2.0.0 \
  .
```

> The image does **not** carry `.env` — `.dockerignore` excludes it. Inject
> the `REDFOX_API_KEY` at runtime via `env_file:` or `-e`.

## Environment Variables

All variables are read by `core/config.py` and can be set in `config.yaml`
(via the `${VAR:-default}` syntax) or as OS env vars.

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `we-mp-rss` | Application name |
| `SERVER_NAME` | `we-mp-rss` | Server name |
| `WEB_NAME` | `WeRSS微信公众号订阅助手` | Frontend display name |
| `ENABLE_JOB` | `True` | Whether to enable scheduled tasks |
| `AUTO_RELOAD` | `False` | uvicorn `--reload` for dev |
| `THREADS` | `2` | uvicorn worker count |
| `DB` | `sqlite:///data/db.db` | Database URL |
| `REDFOX_API_KEY` | — | **Required**. redfox.hk API key |
| `REDFOX_BASE_URL` | `https://redfox.hk` | redfox API base URL |
| `DINGDING_WEBHOOK` | empty | DingTalk notification webhook |
| `WECHAT_WEBHOOK` | empty | WeChat work-bot webhook |
| `FEISHU_WEBHOOK` | empty | Feishu webhook |
| `CUSTOM_WEBHOOK` | empty | Custom webhook |
| `SECRET_KEY` | `we-mp-rss` | JWT signing key — **change in production** |
| `USER_AGENT` | `Mozilla/...` | User-Agent for outbound requests |
| `SPAN_INTERVAL` | `10` | Scheduler tick interval (seconds) |
| `WEBHOOK.CONTENT_FORMAT` | `html` | Article body format for webhooks |
| `PORT` | `8001` | API port |
| `DEBUG` | `False` | Debug mode |
| `MAX_PAGE` | `5` | Max pages per scraping run |
| `RSS_BASE_URL` | empty | Public RSS domain |
| `RSS_LOCAL` | `False` | Use local RSS links instead of `RSS_BASE_URL` |
| `RSS_TITLE` | empty | Override feed title |
| `RSS_DESCRIPTION` | empty | Override feed description |
| `RSS_COVER` | empty | Override feed cover image |
| `RSS_FULL_CONTEXT` | `True` | Include full article body in feed |
| `RSS_ADD_COVER` | `True` | Include cover image in feed items |
| `RSS_CDATA` | `False` | Wrap content in `<![CDATA[]]>` |
| `RSS_PAGE_SIZE` | `30` | Feed item count per page |
| `TOKEN_EXPIRE_MINUTES` | `4320` | Login session validity (minutes) |
| `CACHE.DIR` | `./data/cache` | Cache directory |
| `ARTICLE.TRUE_DELETE` | `False` | Hard-delete vs. soft-delete articles |
| `GATHER.CONTENT` | `True` | Fetch full article body |
| `GATHER.MODEL` | `app` | Collection model (`app` / `web` / `api`) |
| `GATHER.CONTENT_AUTO_CHECK` | `False` | Periodically backfill missing bodies |
| `GATHER.CONTENT_AUTO_INTERVAL` | `59` | Backfill interval (minutes) |
| `GATHER.CONTENT_MODE` | `web` | Content correction mode |
| `SAFE_HIDE_CONFIG` | `db,secret,token,notice.wechat,notice.feishu,notice.dingding` | Keys hidden in the System Info page |
| `LOG_FILE` | empty | Log file path (stdout if empty) |
| `LOG_LEVEL` | `INFO` | Log level |
| `EXPORT_PDF` | `False` | Enable PDF export |
| `EXPORT_PDF_DIR` | `./data/pdf` | PDF output directory |
| `EXPORT_MARKDOWN` | `False` | Enable markdown export |
| `EXPORT_MARKDOWN_DIR` | `./data/markdown` | Markdown output directory |

## Access Key Authentication

For programmatic API access without exposing the admin password.

### Create an AK

1. Login → **Access Key Management** in the left menu
2. Click **Create Access Key**
3. Fill in name, description, permissions, expiry
4. Save both the Access Key and the Secret (the Secret is shown **only once**)

### Use the AK

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

Full guide: [docs/AK_Authentication_Guide.md](docs/AK_Authentication_Guide.md).

## HTML Content Filtering Rules

Filter unwanted elements (ads, recommendation blocks) from scraped article
bodies at the global or per-account level.

- **Scope** — Global (when no `mp_id` is set) or per-account
- **Priority** — 0-100; higher runs first
- **Methods**:
  - Remove by HTML `id`
  - Remove by CSS `class`
  - Remove by CSS selector
  - Remove by attribute (e.g. `data-type="ad"`)
  - Remove by regex
  - Strip common elements (`<script>`, `<style>`, comments)

```bash
# List
GET    /api/filter-rules

# Create
POST   /api/filter-rules
{
  "mp_id": "[]",                  # "[]" for global
  "rule_name": "Global Ad Filter",
  "priority": 10,
  "remove_ids": ["ad-banner"],
  "remove_classes": ["ad-container"]
}

# Update / Delete
PUT    /api/filter-rules/{id}
DELETE /api/filter-rules/{id}
```

## FAQ

**Default credentials?** `admin` / `admin@123` — change on first login.

**`/mps/search` returns empty?** The redfox.hk public library only indexes
"hot" accounts. For unindexed accounts, paste the `fakeid` (Base64 `bizInfo`)
or `wxId` directly when adding a subscription.

**Where do I get a `REDFOX_API_KEY`?** Register at
[redfox.hk](https://redfox.hk?source=redfox_api_md) and create one in
[API Keys](https://redfox.hk/settings/api-keys?source=redfox_api_md).

**Why doesn't the admin UI show my changes after pulling a new image?**
The backend serves the prebuilt frontend from `static/`. If you only pulled
a new image but did not rebuild + sync `web_ui/dist/ → static/`, the UI will
be stale. Re-run the build sequence in **Production build** above.

**The /mps/search logs are empty even when search returns nothing?** A
`REDFOX_API_KEY 未配置` error is raised in `_headers()` *before* `_post()`, so
the call is not recorded. Check the uvicorn stdout log or the **System Info**
page for the redfox status block.

**How do I change the database?** Set the `DB` env var or edit `db:` in
`config.yaml`:

```ini
# SQLite
DB=sqlite:///data/db.db
# MySQL
DB=mysql+pymysql://<user>:<password>@<host>/<db>?charset=utf8mb4
# PostgreSQL
DB=postgresql://<user>:<password>@<host>/<db>
```

## License

MIT
