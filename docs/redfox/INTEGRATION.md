# Redfox 数据接口接入说明

本文档介绍 WeRSS 自 1.6 起接入 **redfox 数据接口** 的方式，
用于替代原先依赖微信公众号公众平台（扫码授权 + cgi-bin/*）
获取公众号信息和作品列表的链路。

## 为什么切换

* 微信公众号公众平台要求长期在线的扫码会话，并频繁触发风控
  （`base_resp.ret = 200013` / `200003`），导致整个采集链路不稳定。
* redfox 数据接口是无状态的 REST API，只需一个 API Key 即可调用，
  适合云端 / 容器化部署。
* 文章正文仍由 `driver.wxarticle`（Playwright）抓取，迁移成本可控。

## 接入步骤

### 1. 申请 API Key

前往 [https://redfox.hk/settings/api-keys](https://redfox.hk/settings/api-keys)
注册账号并创建 API Key。

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并填入：

```dotenv
REDFOX_API_KEY=ak_xxxxxxxxxxxxxxxx
```

或在 `config.yaml` 中显式配置：

```yaml
redfox:
  api_key: ak_xxxxxxxxxxxxxxxx
  base_url: https://redfox.hk   # 可选
  timeout: 15                   # 可选，单位秒
```

> 安全提示：禁止在代码、日志或前端请求中暴露 API Key。
> 推荐通过环境变量注入；本项目会优先读取环境变量 `REDFOX_API_KEY`。

### 3. 重启服务

```bash
python main.py -job True -init True
```

启动后日志中应出现：

```
Redfox数据接口模式,是否采集[...]内容:...
```

如未配置 `REDFOX_API_KEY`，采集任务会打印明确错误并停止，不会影响
其它公众号的正常采集。

## 接口调用关系

| 功能              | 旧实现                                       | 新实现（redfox）                                                     |
| ----------------- | -------------------------------------------- | -------------------------------------------------------------------- |
| 公众号账号信息    | `mp.weixin.qq.com/cgi-bin/searchbiz`         | `POST /story/api/gzh/data/accountInfo`（KUQYSQNX）                  |
| 公众号作品列表    | `mp.weixin.qq.com/cgi-bin/appmsgpublish`     | `POST /story/api/gzh/data/queryWorkList`（8IQD0BJC）                 |
| 公众号文章正文    | `driver.wxarticle.Web.get_article_content`   | **保留**，未做改动                                                  |

请求头：

```
REDFOX_API_KEY: <your-key>
Content-Type: application/json
```

请求体（`accountInfo`）：

```json
{
  "account": "duhaoshu",      // 微信号、wxId（gh_ 开头）、bizInfo（Base64）三选一
  "wxId": "gh_xxxxxxxxxxxx",
  "bizInfo": "MjM5MDMyMzg2MA=="
}
```

请求体（`queryWorkList`）：

```json
{
  "account": "duhaoshu",
  "wxId": "gh_xxxxxxxxxxxx",
  "bizInfo": "MjM5MDMyMzg2MA==",
  "offset": 0,
  "sortType": "2"            // 0=默认 / 2=最新 / 4=最热
}
```

## 数据字段映射

旧 searchbiz 字段在保留兼容语义的同时，按以下规则映射到 redfox
字段；前端 `AddSubscription.vue` 等模块无需修改。

| 旧字段（searchbiz）  | redfox 字段          | 说明                                 |
| -------------------- | -------------------- | ------------------------------------ |
| `fakeid`             | `bizInfo`            | Base64 编码的账号唯一 ID             |
| `nickname`           | `accountName`        | 账号名                               |
| `round_head_img`     | `avatarUrl`          | 头像                                 |
| `signature`          | `description`        | 账号简介                             |
| —                    | `account`            | 微信号                               |
| —                    | `wxId`               | 公众号原始 ID（gh_ 开头）            |
| —                    | `qrcodeUrl`          | 公众号二维码                         |
| —                    | `verifyInfo`         | 认证信息                             |

## 代码位置

* `core/redfox/client.py` — redfox 客户端封装
* `core/wx/base.py` — `WxGather.search_Biz` 已切换到 redfox
* `core/wx/model/web.py` — `MpsWeb.get_Articles` 已切换到 redfox
* `core/wx/model/app.py`、`core/wx/model/api.py` — 历史兼容 shim
* `apis/redfox.py` — `/api/v1/wx/redfox/{logs,stats,logs/clear}` 新接口

## 已下线的旧入口

> 已彻底删除，不再保留任何 shim 或 410 占位接口。

| 原入口                                          | 替代实现                          |
| ----------------------------------------------- | --------------------------------- |
| `apis/auth.py::/qr/code`、`/qr/image` 等       | 由 redfox 客户端直接抓取          |
| `driver/wx_api.py`、`driver/wx.py`              | `core.redfox.client.RedfoxClient` |
| `driver/token.py`、`driver/base.py`            | 同上                              |
| `driver/success.py`、`driver/auth.py`          | 同上                              |
| `core/wx/wx.py::search_Biz` / `get_Articles`   | `core.redfox` / `core.wx`         |
| `core/wx/cfg.py::wx_cfg`                        | `core.config.cfg`                 |
| `jobs/failauth.py::send_wx_code`                | 无需重试，redfox 由调用方按需重试 |
| `views/WechatStatus.vue`、`WechatAuthQrcode.vue` | 已无对应页面                     |

## 常见问题

### Q: 配置了 REDFOX_API_KEY 但仍报「未配置」？

检查：
1. 是否使用了 `dotenv` 之类的工具加载 `.env`？本项目直接读 OS 环境变量。
2. 容器化部署时是否把 `REDFOX_API_KEY` 注入到容器环境变量？
3. 是否设置了 `safe.hide_config` 把 `redfox` 也隐藏了？这只会影响
   API 回显，不会影响实际读取。

### Q: 接口返回 401/403？

通常是 API Key 无效或已过期。重新到
[https://redfox.hk/settings/api-keys](https://redfox.hk/settings/api-keys)
生成即可。

### Q: 单次只返回 1 条？

`accountInfo` 接口每次只能返回单个公众号账号信息；搜索体验与微信原
生搜索基本一致。如需遍历多个公众号，建议先在前端做输入联想，再让用
户选择具体公众号。

### Q: 历史 `faker_id` 还能继续用吗？

可以。数据库里 `Feed.faker_id` 字段直接保存的是 redfox 的 `bizInfo`
（Base64 字符串），采集时按 `bizInfo` 直接查询，无需额外转换。
