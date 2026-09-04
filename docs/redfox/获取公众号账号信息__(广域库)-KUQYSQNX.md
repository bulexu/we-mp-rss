# 获取公众号账号信息  (广域库)

通过微信号、公众号原始ID或业务密钥查询公众号账号详细信息。account、wxId、bizInfo 三者选其一，同时传入时优先级为 wxId > bizInfo > account。

**`POST`** `https://redfox.hk/story/api/gzh/data/accountInfo`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/gzh/data/accountInfo`

---

## 请求头

| 名称 | 类型 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| REDFOX_API_KEY | string | 是 | 平台鉴权令牌，每次请求必填 | ak_xxxxxx |
| Content-Type | string | 是 | 请求体数据类型 | application/json |

---

## 请求参数

| 参数 | 类型 | 必填 | 说明 | 示例 |
| --- | --- | --- | --- | --- |
| account | String | 否 | 公众号微信号，非必填，与 wxId、bizInfo 三者选其一 | duhaoshu |
| wxId | String | 否 | 公众号原始ID，非必填，与 account、bizInfo 三者选其一 | gh_5c7e8b7f586b |
| bizInfo | String | 否 | 账号唯一ID，非必填，与 account、wxId 三者选其一 | MjM5MDMyMzg2MA== |

---

## 返回值与结构

统一包装一般为 `code`、`message`/`msg`、`data`（以实际服务为准）。

---

## 响应字段

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| code | Integer | 接口响应状态码，例如 2000 表示成功 | 2000 |
| msg | String | 接口响应的提示或错误信息 | 成功 |
| data | Object | 接口返回的主要数据内容 | — |
| account | String | 账号平台展示ID | duhaoshu |
| accountName | String | 账号名 | 十点读书 |
| avatarUrl | String | 头像链接 | http://wx.qlogo.cn/mmhead/Q3auHgzwzM7BmxMfFQA3ic4p0H3Syd79W0p8Z6RnA9WnHcTTNrfPxSw/ |
| bizInfo | String | 账号唯一ID | MjM5MDMyMzg2MA== |
| description | String | 账号简介 | 深夜十点，陪你读书，美好的生活。好书/故事/美文/电台/美学。 |
| qrcodeUrl | String | 账号二维码 | http://mp.weixin.qq.com/mp/qrcode?scene=10000005&size=102&__biz=MjM5MDMyMzg2MA==&mid=2655500434&idx=1&sn=745d84e2213248177f0ca4bfa8892708 |
| verifyInfo | String | 认证信息 | 微信认证：厦门十点文化传播有限公司 |
| wxId | String | 公众号原始ID | gh_5c7e8b7f586b |

---

## 请求示例

```bash
请求参数：
{
  "account": "duhaoshu",
  "wxId": "gh_5c7e8b7f586b",
  "bizInfo": "MjM5MDMyMzg2MA=="
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "data": {
    "account": "duhaoshu",
    "accountName": "十点读书",
    "avatarUrl": "http://wx.qlogo.cn/mmhead/Q3auHgzwzM7BmxMfFQA3ic4p0H3Syd79W0p8Z6RnA9WnHcTTNrfPxSw/",
    "bizInfo": "MjM5MDMyMzg2MA==",
    "description": "深夜十点，陪你读书，美好的生活。好书/故事/美文/电台/美学。",
    "qrcodeUrl": "http://mp.weixin.qq.com/mp/qrcode?scene=10000005&size=102&__biz=MjM5MDMyMzg2MA==&mid=2655500434&idx=1&sn=745d84e2213248177f0ca4bfa8892708",
    "verifyInfo": "微信认证：厦门十点文化传播有限公司",
    "wxId": "gh_5c7e8b7f586b"
  },
  "msg": "成功"
}
```

---

## 密钥获取与安全说明

- 本API需要使用API密钥 `REDFOX_API_KEY`。
- API密钥由 [红狐 hub](https://redfox.hk/settings/api-keys?source=redfox_api_md) (`https://redfox.hk`)提供。
- 请前往 [红狐 hub](https://redfox.hk?source=redfox_api_md) 注册并登录账号，在密钥管理模块创建 API密钥。
- 复制并仅在请求头中使用API密钥。
- 在提供密钥前，请先确认密钥来源、可用范围、有效期及是否支持重置/撤销。
- 禁止在代码、提示词、日志或输出文件中硬编码/明文暴露密钥。
