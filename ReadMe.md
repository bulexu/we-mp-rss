<div align=center>
<img src="static/logo.svg" alt="WeRSS Logo" width="20%">
<h1>WeRSS — WeChat Official Account RSS Subscription Assistant (bulexu fork)</h1>

[![Python](https://img.shields.io/badge/python-3.13.1+-red.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Version](https://img.shields.io/badge/version-v2.0.0-blue.svg)]()
[![Upstream](https://img.shields.io/badge/upstream-rachelos/we--mp--rss-orange.svg)](https://github.com/rachelos/we-mp-rss)

[中文](README.zh-CN.md) | [English](ReadMe.md)

A self-hosted tool for subscribing to and managing WeChat Official Account
content and generating RSS feeds. **Since v2 the data layer runs against
[redfox.hk](https://redfox.hk) stateless REST** — no QR-code session, run
unattended on a server; **Feishu Bitable archiving is new** — scraped
articles can be pushed into designated Bitable tables by account, enabling
zero-ops archiving and team collaboration.
</div>

---

## About This Project

This repository is a **bulexu-maintained fork**. Upstream is
[rachelos/we-mp-rss](https://github.com/rachelos/we-mp-rss) (original
author: Rachel / RachelOS). This branch builds on top of the upstream and
focuses on **two core scenarios**: **unattended collection (redfox data
layer)** and **Bitable archiving (Feishu Bitable)**.

### Upstream & Acknowledgements

> This project is based on **<https://github.com/rachelos/we-mp-rss>**
> Thanks to RachelOS and the following contributors (in no particular order):
>
> **cyChaos, 子健MeLift, 晨阳, 童总, 胜宇, 军亮, 余光, 一路向北,
> 水煮土豆丝, 人可, 须臾, 澄明, 五梭, Jarvis, 三三, 哈基米, 苹果**

Upstream README and acknowledgements:
[rachelos/we-mp-rss](https://github.com/rachelos/we-mp-rss). Copyright for
upstream features belongs to the original authors; copyright for new
features and fixes in this branch belongs to bulexu and its contributors.

---

## Core Capabilities

### 🆕 Differences vs. Upstream

| Module | Upstream (rachelos) | This branch (bulexu) |
| --- | --- | --- |
| Data layer | QR-code scan session (`mp.weixin.qq.com/cgi-bin/searchbiz` + cookie) | **[redfox.hk](https://redfox.hk) stateless REST** (since v2) |
| Archiving | Webhook push only | **Webhook + Feishu Bitable auto-archiving** |

### ✅ Capability Overview

#### Content production & distribution

- **Article list**: fetched via [redfox.hk](https://redfox.hk) stateless
  REST (search / ID lookup / article list)
- **Article body**: in-system auto-degrade — **Playwright → optional
  Redfox** (gated by `GATHER.CONTENT_REDFOX_FALLBACK`); **out-of-band
  manual fallback** — Bazhuayu RPA (runs independently, configured inside
  the Bazhuayu client). See "Article Scraping Strategy" below.
- RSS feed generation (RSS 2.0 with optional CDATA / full-text / cover /
  custom page size)
- Scheduled auto-update (configurable interval, default 10s)
- Custom RSS title, description, cover, pagination size
- Custom notification channels (DingTalk / WeChat work-bot / Feishu /
  Custom Webhook)
- HTML content filtering rules (global + per-account, priority 0-100)
- **Markdown / DOCX / PDF / JSON** export

#### Feishu Bitable archiving (new in this branch)

- Visual configuration of push targets under `/lark/bitables` in the admin
- Each Bitable row can be associated with multiple accounts (`mp_ids`
  whitelist)
- Field-mapping whitelist (`title` / `url` / `content` / `publish_time` /
  `mp_name` etc.)
- Idempotent dedup via `article_lark_pushes` composite primary key
- Fully async — never blocks the scraping main loop
- Failure is recoverable: each row keeps `last_error` / `last_error_at`

#### Web admin UI

- 13 themes (dark / sepia / purple / blue / green / orange / rose / teal /
  pink / indigo / violet / coffee / navy)
- Responsive pagination (PC click-nav / mobile load-more)
- System Info page (redfox call log, redfox status, DB info, cache state)
- HTML filter rule editor
- Bitable configuration UI
- Error capture with graceful fallback

#### Security & auth

- JWT login sessions (default 4320 minutes)
- `SAFE_HIDE_CONFIG` masks sensitive config in the System Info page

#### Extensibility & ops

- **Environment Exception Statistics** — automatic per-feed failure
  tracking (redfox rate-limit, IP risk control, timeouts)
- **Headers / Cookies authentication** — Webhook calls can carry custom
  request headers
- **Configuration cache** — Redis / Memcached / in-memory three-tier cache
- **Database** — SQLite (default) / MySQL / PostgreSQL
- **Cache backend** — Redis (redfox logs / multi-worker sessions)

---

## Quick Start (Docker)

The image is published to the Aliyun personal registry:

```bash
docker run -d --name we-mp-rss \
  -p 8001:8001 \
  -v ./data:/app/data \
  --env-file ./.env \
  crpi-qp8hiqijfnilf93t.cn-hangzhou.personal.cr.aliyuncs.com/bulexu/we-mp-rss:latest
```

Then visit `http://<your-ip>:8001/`. Default credentials: `admin` /
`admin@123` — **change them on first login** (top-right user menu →
Change Password).

The image does **not** bundle a `REDFOX_API_KEY`. Pass it via `.env`:

```bash
# .env (one line per key, no quotes)
REDFOX_API_KEY=ak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LARK_APP_ID=cli_xxxxxxxxxxxx                # Optional, required for Feishu Bitable
LARK_APP_SECRET=xxxxxxxxxxxxxxxxxxxx        # Optional, required for Feishu Bitable
LARK_ENABLED=True                            # Optional, default False
```

### Upgrade

```bash
docker stop we-mp-rss && docker rm we-mp-rss
docker pull crpi-qp8hiqijfnilf93t.cn-hangzhou.personal.cr.aliyuncs.com/bulexu/we-mp-rss:latest
# re-run the docker run command above (data/ is on a host volume — preserved)
```

---

## Article Scraping Strategy

The project applies a layered strategy for two distinct data types —
**article list** and **article body** — keeping the main pipeline
unattended while reserving human-in-the-loop fallback for the long tail.

### Article list: redfox REST

Account search, account metadata, and the article list (title /
publish time / summary / cover / URL) all come from
[redfox.hk](https://redfox.hk) stateless REST. No login session, no
cookies. **`GATHER.MODEL` no longer affects the list phase.**

| Concern | Endpoint |
| --- | --- |
| Search an account by keyword | `/story/api/gzh/data/searchUser` |
| Get an account by ID | `/story/api/gzh/data/accountInfo` |
| Get article list for an account | `/story/api/gzh/data/queryWorkList` |

Full module map: [docs/redfox/INTEGRATION.md](docs/redfox/INTEGRATION.md).

### Article body: Playwright + (optional Redfox) + Bazhuayu RPA (out-of-band)

Body extraction is much harder than list fetching (anti-bot / IP rate
limit / CAPTCHA / JS rendering). The strategy splits into two
**independent** layers: **in-system auto-degrade** (Playwright + optional
Redfox) and **out-of-band manual fallback** (Bazhuayu RPA, configured
and run separately in the Bazhuayu client). The two layers are fully
decoupled — the RPA does **not** participate in the auto-degrade
decision.

#### In-system auto-degrade (order depends on `GATHER.CONTENT_REDFOX_FALLBACK`)

```
                       ┌──────────────────────────────────────┐
                       │  Body fetch — in-system auto-degrade  │
                       └──────────────────────────────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────────────┐
   Tier 1 ──►  Playwright browser              │  driver/wxarticle.py
              (default preferred, best compat) │  + driver/playwright_driver.py
                       │                       │
                       ▼                       │
              fetched OK? ──── no ────►        │
                       │                       │
                       ▼                       │
              ┌────────┴────────────┐          │
              │                     │          │
   GATHER.CONTENT_     True (default)│ False    │
   REDFOX_FALLBACK=    ─► enable Tier 2 ──► skip Tier 2 ──► mark failed
              │                     │          │
              ▼                     │          │
                       ┌──────────────────────────┐
   Tier 2 ──►  redfox API for body   │  redfox.hk REST (optional, default on)
              (fallback, no browser) │  triggered after N Playwright failures
                       │              │
                       ▼              │
                  fetched OK?         │
                       │              │
                       ▼              │
                  mark complete       │
```

**Decision logic**:

| `GATHER.CONTENT_REDFOX_FALLBACK` | Call order | When to use |
| --- | --- | --- |
| `True` (**default**) | Playwright → redfox → complete / failed | Want maximum coverage; willing to spend redfox quota |
| `False` | Playwright → complete / failed | Skip redfox quota usage; accept some articles with no body |

#### Out-of-band manual fallback: Bazhuayu RPA (independent of auto-degrade)

> Bazhuayu RPA does **not** participate in the auto-degrade decision. It
> is configured and run **separately** inside the Bazhuayu client. It
> uses Access Key to **retroactively** fill in `has_content=0` articles
> that the system-internal chain could not get.

**RPA application link**:
**[Bazhuayu RPA application](https://rpa.bazhuayu.com/shareableLink/6aa1062894a41f8dcd647ff3)**

| Tier | Trigger | Strengths | Limits |
| --- | --- | --- | --- |
| **Tier 1 · Playwright** | In-system, default preferred | Real browser rendering; handles JS, CAPTCHA, attention walls | Browser process overhead; high-frequency scraping triggers anti-bot |
| **Tier 2 · redfox API** *(optional)* | In-system, after N Playwright failures | Stateless HTTP, low resource cost | Some heavily protected accounts return incomplete HTML; skipped when `CONTENT_REDFOX_FALLBACK=False` |
| **Out-of-band · Bazhuayu RPA** | **Manually started**; retroactively writes `has_content=0` articles | Human-in-the-loop, can bypass any anti-bot | Must be configured and run inside the Bazhuayu client; fully decoupled from auto-degrade |

#### AK endpoints for RPA write-back

The Bazhuayu RPA uses Access Key to call two endpoints, **fully decoupled
from the system scraping loop** — you can start/stop it independently:

```bash
# 1. Pull articles that need body content (has_content=0, not deleted)
GET  /api/v1/wx/articles/pending-content?limit=10&mp_id=MP_WXS_xxx
Authorization: AK-SK {ak}:{sk}

# 2. Write the body content (or mark deleted)
POST /api/v1/wx/articles/{article_id}/content
Authorization: AK-SK {ak}:{sk}
Content-Type: application/json
{
  "content": "<p>Body HTML / Markdown ...</p>",
  "content_html": "<p>...</p>",      # Optional; auto-generated by fix_html if omitted
  "title": "...",                     # Optional, overrides current title
  "description": "...",               # Optional
  "pic_url": "...",                   # Optional
  "publish_time": 1735689600,         # Optional
  "deleted": false                    # true marks the article as removed by its author
}
```

> Steps: open the link above in the Bazhuayu client → fill in your
> service's `BASE_URL` and Access Key → the RPA polls
> `/pending-content` and POSTs results back to `/content`.

#### Auto-retry mechanism (in-system, unrelated to RPA)

With `GATHER.CONTENT_AUTO_CHECK=True`, the backend periodically re-feeds
`has_content=0` articles into Tier 1 (Playwright). When the failure
counter reaches the threshold (default 3), `web_fetch_fail_count` is
incremented and the system **stops retrying Playwright** for that
article, freeing the browser pool for others.

---

## Feishu Bitable Archiving

A core capability of this branch. Once configured, every newly scraped /
amended WeChat Official Account article is automatically pushed to the
designated Bitable, achieving a "WeChat → database" zero-ops pipeline.

### Prerequisites

1. Create a **Custom App** at [Feishu Open Platform](https://open.feishu.cn/app)
   and obtain the **App ID** and **App Secret**
2. Grant the app **editable** permission on the target Bitable
3. Set `LARK_APP_ID` / `LARK_APP_SECRET` / `LARK_ENABLED=True` in `.env`

### Add a push target

1. Login → left menu → **Feishu Bitable**
2. Click **New** and fill in:
   - Name: human-readable identifier, e.g. "News Archive"
   - App Token / Table ID: copy from the Bitable URL
     (`https://feishu.cn/base/{APP_TOKEN}?table={TABLE_ID}`)
   - **Associated accounts**: multi-select dropdown, pick the accounts
     you want to archive
   - **Field mapping**: left dropdown selects article fields (`title` /
     `url` / `content` / `publish_time` / `mp_name` etc.), right side
     enters the corresponding Bitable field name
3. Save and ensure the row is `enabled=True`

### Behavior

- Push triggers on **first ingestion with body present**; pure-title or
  DELETED articles are skipped
- **Idempotent**: `article_lark_pushes` has a composite primary key on
  `(article_id, bitable_id)` so each article is pushed to each Bitable
  at most once
- **Failure is recoverable**: each Bitable row keeps `last_error` /
  `last_error_at` for the most recent failure; fix the config and the
  next article ingestion will retry

### Diagnosis

The **System Info** page shows the redfox status block; per-row failures
also surface in the Bitable row's "Last Error" field with the Feishu
return code (e.g. `99991663` token expired).

---

## System Architecture

Front-end / back-end separation, with the backend serving the prebuilt
frontend as static files:

- Backend: Python 3.13 + FastAPI + Uvicorn
- Frontend: Vue 3 + Vite 8 + rolldown
- Database: SQLite (default) / MySQL / PostgreSQL
- Cache: Redis (optional, required for redfox logs / multi-worker
  sessions / cascade queue)

```
┌──────────────┐    ┌────────────────────────────────────┐
│  Vue 3 SPA   │    │  FastAPI (uvicorn, port 8001)      │
│  (static/)   │◄──►│  ├─ /api/v1/wx  (article/feed/...) │
└──────────────┘    │  ├─ /api/v1/wx/redfox  (stats/logs)│
                    │  ├─ /api/v1/wx/lark   (bitables)   │
                    │  └─ /story/api/gzh/data/... (redfox)│
                    └────────────┬───────────────────────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
           SQLite/MySQL     Redis (logs,    redfox.hk
                            cache, queue)
                                 │
                                 ▼
                          Feishu OpenAPI
                          (Bitable archive)
```

---

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
cp .env.example .env       # then fill in REDFOX_API_KEY (required)
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
  -t crpi-qp8hiqijfnilf93t.cn-hangzhou.personal.cr.aliyuncs.com/bulexu/we-mp-rss:latest \
  .
```

> The image does **not** carry `.env` — `.dockerignore` excludes it.
> Inject the `REDFOX_API_KEY` / `LARK_*` at runtime via `env_file:` or `-e`.

---

## Environment Variables

All variables are read by `core/config.py` and can be set in `config.yaml`
(via the `${VAR:-default}` syntax) or as OS env vars.

### Core

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `we-mp-rss` | Application name |
| `SERVER_NAME` | `we-mp-rss` | Server name |
| `WEB_NAME` | `WeRSS微信公众号订阅助手` | Frontend display name |
| `ENABLE_JOB` | `True` | Whether to enable scheduled tasks |
| `AUTO_RELOAD` | `False` | uvicorn `--reload` for dev |
| `THREADS` | `2` | uvicorn worker count |
| `PORT` | `8001` | API port |
| `DB` | `sqlite:///data/db.db` | Database URL |
| `SECRET_KEY` | `we-mp-rss` | JWT signing key — **change in production** |
| `USER_AGENT` | `Mozilla/...` | User-Agent for outbound requests |
| `DEBUG` | `False` | Debug mode |
| `LOG_LEVEL` | `INFO` | Log level |
| `LOG_FILE` | empty | Log file path (stdout if empty) |
| `SAFE_HIDE_CONFIG` | `db,secret,token,notice.*` | Keys hidden in the System Info page |

### Redfox (required)

| Variable | Default | Description |
| --- | --- | --- |
| `REDFOX_API_KEY` | — | **Required**. redfox.hk API key |
| `REDFOX_BASE_URL` | `https://redfox.hk` | redfox API base URL |

### Feishu Bitable (new in this branch)

| Variable | Default | Description |
| --- | --- | --- |
| `LARK_ENABLED` | `False` | Global switch for Feishu push |
| `LARK_APP_ID` | — | Feishu App ID (`cli_...`) |
| `LARK_APP_SECRET` | — | Feishu App Secret |
| `LARK_TIMEOUT` | `15` | Feishu API request timeout (seconds) |

### Webhook notifications

| Variable | Default | Description |
| --- | --- | --- |
| `DINGDING_WEBHOOK` | empty | DingTalk notification webhook |
| `WECHAT_WEBHOOK` | empty | WeChat work-bot webhook |
| `FEISHU_WEBHOOK` | empty | Feishu webhook (instant notification — distinct from Bitable archive) |
| `CUSTOM_WEBHOOK` | empty | Custom webhook |
| `WEBHOOK.CONTENT_FORMAT` | `html` | Article body format for webhooks |

### Content collection

| Variable | Default | Description |
| --- | --- | --- |
| `GATHER.CONTENT` | `True` | Fetch full article body |
| `GATHER.MODEL` | `app` | Collection model (`app` / `web` / `api`) |
| `GATHER.CONTENT_AUTO_CHECK` | `False` | Periodically backfill missing bodies |
| `GATHER.CONTENT_AUTO_INTERVAL` | `59` | Backfill interval (minutes) |
| `GATHER.CONTENT_MODE` | `web` | Content correction mode |
| `GATHER.CONTENT_REDFOX_FALLBACK` | `True` | After Playwright fails, fall back to redfox API (`False` skips Tier 2) |
| `MAX_PAGE` | `5` | Max pages per scraping run |
| `SPAN_INTERVAL` | `10` | Scheduler tick interval (seconds) |
| `ARTICLE.TRUE_DELETE` | `False` | Hard-delete vs. soft-delete articles |

### RSS feed

| Variable | Default | Description |
| --- | --- | --- |
| `RSS_BASE_URL` | empty | Public RSS domain |
| `RSS_LOCAL` | `False` | Use local RSS links instead of `RSS_BASE_URL` |
| `RSS_TITLE` | empty | Override feed title |
| `RSS_DESCRIPTION` | empty | Override feed description |
| `RSS_COVER` | empty | Override feed cover image |
| `RSS_FULL_CONTEXT` | `True` | Include full article body in feed |
| `RSS_ADD_COVER` | `True` | Include cover image in feed items |
| `RSS_CDATA` | `False` | Wrap content in `<![CDATA[]]>` |
| `RSS_PAGE_SIZE` | `30` | Feed item count per page |

### Cache / export / session

| Variable | Default | Description |
| --- | --- | --- |
| `CACHE.DIR` | `./data/cache` | Cache directory |
| `CACHE.ENABLED` | `True` | Enable cache |
| `EXPORT_PDF` | `False` | Enable PDF export |
| `EXPORT_PDF_DIR` | `./data/pdf` | PDF output directory |
| `EXPORT_MARKDOWN` | `False` | Enable markdown export |
| `EXPORT_MARKDOWN_DIR` | `./data/markdown` | Markdown output directory |
| `TOKEN_EXPIRE_MINUTES` | `4320` | Login session validity (minutes) |

---

## Access Key Authentication

For programmatic API access without exposing the admin password. Full
guide: [docs/AK_Authentication_Guide.md](docs/AK_Authentication_Guide.md).

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

---

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

---

## Screenshots

- Login Interface  
  <img src="docs/登录.png" alt="Login" width="80%"/><br/>
- Main Interface  
  <img src="docs/主界面.png" alt="Main Interface" width="80%"/><br/>
- Add Subscription (now powered by redfox search)  
  <img src="docs/添加订阅.png" alt="Add Subscription" width="80%"/><br/>
- Frontend Architecture  
  <img src="docs/前端架构.png" alt="Frontend Architecture" width="80%"/><br/>

---

## FAQ

**Default credentials?** `admin` / `admin@123` — change on first login.

**`/mps/search` returns empty?** The redfox.hk public library only indexes
"hot" accounts. For unindexed accounts, paste the `fakeid` (Base64
`bizInfo`) or `wxId` directly when adding a subscription.

**Where do I get a `REDFOX_API_KEY`?** Register at
[redfox.hk](https://redfox.hk?source=redfox_api_md) and create one in
[API Keys](https://redfox.hk/settings/api-keys?source=redfox_api_md).

**Why doesn't the admin UI show my changes after pulling a new image?**
The backend serves the prebuilt frontend from `static/`. If you only
pulled a new image but did not rebuild + sync `web_ui/dist/ → static/`,
the UI will be stale. Re-run the build sequence in **Production build**
above.

**The /mps/search logs are empty even when search returns nothing?** A
`REDFOX_API_KEY 未配置` error is raised in `_headers()` *before*
`_post()`, so the call is not recorded. Check the uvicorn stdout log or
the **System Info** page for the redfox status block.

**Feishu push is not working?** Check three things:
1. `.env` has `LARK_ENABLED=True` and `LARK_APP_ID` / `LARK_APP_SECRET`
   are non-empty
2. The Bitable row is `enabled=True` and the **Associated accounts**
   dropdown includes the WeChat account this article belongs to
3. Check uvicorn stdout for `[lark] worker start article_id=...` and
   follow-up lines (`skip` / `dispatch` / `push ok` / `push failed`) to
   pinpoint where it short-circuits

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

---

## Related Documents

- Upgrade to v2 (redfox migration): [docs/redfox/INTEGRATION.md](docs/redfox/INTEGRATION.md)
- Access Key auth: [docs/AK_Authentication_Guide.md](docs/AK_Authentication_Guide.md)
- Cascade system (distributed collection):
  [docs/CASCADE_QUICKSTART.md](docs/CASCADE_QUICKSTART.md) /
  [docs/CASCADE_GUIDE.md](docs/CASCADE_GUIDE.md)
- Configuration cache: [docs/cache-config.md](docs/cache-config.md)
- Webhook custom headers: [docs/headers_cookies_feature.md](docs/headers_cookies_feature.md)
- Web UI quickstart: [docs/webui-quickstart.md](docs/webui-quickstart.md)
- Environment exception stats:
  [docs/webui-env-exception-stats.md](docs/webui-env-exception-stats.md)
- Contributing guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Cascade troubleshooting:
  [TROUBLESHOOTING_CASCADE.md](TROUBLESHOOTING_CASCADE.md)
- Cascade config fix: [FIX_CASCADE_CONFIG.md](FIX_CASCADE_CONFIG.md)

---

## License

MIT — see [LICENSE](LICENSE). New modules in this branch (`/lark/*`
Feishu Bitable archive, redfox data-layer adapter) share the same license
as the upstream project.