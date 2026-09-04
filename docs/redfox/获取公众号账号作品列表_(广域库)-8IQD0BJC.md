# 获取公众号账号作品列表 (广域库)

通过微信号、公众号原始ID或业务密钥查询公众号文章列表。account、wxId、bizInfo 三者选其一，同时传入时优先级为 wxId > bizInfo > account。查询流程：先根据账号信息查到uid，再根据uid查询文章列表。

**`POST`** `https://redfox.hk/story/api/gzh/data/queryWorkList`

---

## API 说明

**Method**: `POST`
**Host**: `https://redfox.hk`
**Path**: `/story/api/gzh/data/queryWorkList`

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
| bizInfo | String | 否 | 账号采集用ID，非必填，与 account、wxId 三者选其一 | MjM5MDMyMzg2MA== |
| offset | Integer | 否 | 偏移量，从0开始，每页+20 | 0 |
| sortType | String | 否 | 排序方式，0: 默认，2: 最新，4: 最热 | 2 |

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
| list | Array | 文章列表 | — |
| author | String | 账号昵称 | 十点读书 |
| authorAvatarUrl | String | 作者头像链接 | http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png |
| bizInfo | String | 公众号采集用ID | MjM5MDMyMzg2MA== |
| collectCount | Integer | 收藏数 | 23 |
| commentCount | Integer | 评论数 | 3 |
| coverUrl | String | 作品封面链接 | https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLSHsicnzbGXLJUAWibbMo7oVDzOrj5Z1daDBl08cxaeS2v6rF3m0YK0oIZA32hb8uUOPiaBPiaJPgZaF6hzxT6Zy1QymxW3Cs5VSVk/0?wx_fmt=jpeg |
| isOriginal | Integer | 原创标识，1 为原创 | 0 |
| likeCount | Integer | 点赞数 | 93 |
| orderNum | Integer | 发文位置，0 为头条 | 1 |
| originalAuthor | String | 原创作者 | null |
| publishTime | String | 发布时间 | 2026-07-21 18:30:00 |
| readCount | Integer | 阅读数 | 29115 |
| shareCount | Integer | 分享数 | 93 |
| sourceUrl | String | 阅读原文链接 | null |
| summary | String | 作品简介 | 深夜十点，陪你读书。 |
| title | String | 作品标题 | 救命！我可能再也穿不回普通内裤了... |
| watchCount | Integer | 在看数 | 35 |
| workUrl | String | 作品链接 | https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217840&idx=2&sn=d4ea85ca42bcc609633c2d6c485c01fe#rd |
| workUuid | String | 作品ID | 361A2B123A064DDA8D842E892D3ABF33 |
| total | Integer | 搜索结果总数 | 3755 |

---

## 请求示例

```bash
请求参数：
{
  "account": "duhaoshu",
  "wxId": "gh_5c7e8b7f586b",
  "bizInfo": "MjM5MDMyMzg2MA==",
  "offset": 0,
  "sortType": "2"
}
```

---

## 响应示例

```json
{
  "code": 2000,
  "data": {
    "list": [
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 23,
        "commentCount": 3,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLSHsicnzbGXLJUAWibbMo7oVDzOrj5Z1daDBl08cxaeS2v6rF3m0YK0oIZA32hb8uUOPiaBPiaJPgZaF6hzxT6Zy1QymxW3Cs5VSVk/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 93,
        "orderNum": 1,
        "originalAuthor": null,
        "publishTime": "2026-07-21 18:30:00",
        "readCount": 29115,
        "shareCount": 93,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 07:13:16",
        "title": "救命！我可能再也穿不回普通内裤了...",
        "watchCount": 35,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217840&idx=2&sn=d4ea85ca42bcc609633c2d6c485c01fe#rd",
        "workUuid": "361A2B123A064DDA8D842E892D3ABF33"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 113,
        "commentCount": 10,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLRzrVkzOzFzCIuvKb8mupCtTib6icHNxekHgrskWp4GYibVaoPF31WpYNib9vpPlCqU2YwqkhTkdic3ZUCOw8AQRbCC5RocPibtCnf8k/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 156,
        "orderNum": 2,
        "originalAuthor": null,
        "publishTime": "2026-07-21 18:30:00",
        "readCount": 14125,
        "shareCount": 350,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 07:13:16",
        "title": "真正的强大，是破心障、见真章、定乾坤",
        "watchCount": 104,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217840&idx=3&sn=4086620fbfa24b31e1210356863eae2d#rd",
        "workUuid": "1765C36212F1FC1D1A190D2F0586DDF7"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 81,
        "commentCount": 6,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLSCg93iaVxSPY9EQjbibvia8sXRBd9wXpib6ib0KLEoerItFibDgET5rIYPu3Niaur4KWeW4WVRRCDHZmpRh7hsNAVPRObfzXyeACCWiao/0?wx_fmt=jpeg",
        "isOriginal": 1,
        "likeCount": 73,
        "orderNum": 4,
        "originalAuthor": "十点签约作者",
        "publishTime": "2026-07-21 18:30:00",
        "readCount": 7241,
        "shareCount": 246,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 07:13:17",
        "title": "家里谁对孩子最好，他就欺负谁",
        "watchCount": 53,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217840&idx=5&sn=af0714683dc78cabecaa646c675af241#rd",
        "workUuid": "5291953F45DF5B3CB8A3B7F38D347A78"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 1853,
        "commentCount": 100,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLTl4jFictwmUzuTkmkicZGIKV8XlDsmoqglDPQO1osgpVyuPBy5vd6iaH8Pq7a0eR6AKGg7aCZ0xZxvMahO3U0ficAVB4q2gicP5d38/0?wx_fmt=jpeg",
        "isOriginal": 1,
        "likeCount": 2118,
        "orderNum": 0,
        "originalAuthor": "十点微微",
        "publishTime": "2026-07-21 18:30:00",
        "readCount": 100001,
        "shareCount": 6800,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 07:13:18",
        "title": "中年夫妻，已经懒得出轨了",
        "watchCount": 1151,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217840&idx=1&sn=4b85b7b21ca52c05aea8ca4f535cd90d#rd",
        "workUuid": "1E2B3E7ABF0F40E016B9EE73FA943D49"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 124,
        "commentCount": 15,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLQOuibKhjGoMcxlf0SEeZxPmDkiabPuiaQ3ibKJFJTHjuXMPx9RicTicEoWY3UR5QAWSic4EeR86wsYaFUDSAxFa34CVwsFY7gHmX87Uc/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 157,
        "orderNum": 3,
        "originalAuthor": null,
        "publishTime": "2026-07-21 18:30:00",
        "readCount": 13528,
        "shareCount": 526,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 07:13:16",
        "title": "认知高的人都有一个特点：身体好",
        "watchCount": 115,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217840&idx=4&sn=51b90132967dba1d6d80eab89e5d941f#rd",
        "workUuid": "78D6A724062A9C695DAB93C44430ABA3"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 174,
        "commentCount": 19,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLQoic9apiaiaj3a6CTYaC0DfaW2QicFibQLCKY7IjFKh5srbuFNfMJLiazj62j7ovOuqydBxiaibPicsXefUSEXmFyujsMaKv0VEMC8xhiaY/0?wx_fmt=jpeg",
        "isOriginal": 1,
        "likeCount": 267,
        "orderNum": 3,
        "originalAuthor": "十点签约作者",
        "publishTime": "2026-07-20 18:50:00",
        "readCount": 31463,
        "shareCount": 701,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 01:36:32",
        "title": "普通人存钱最快的方法：禁欲",
        "watchCount": 157,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217756&idx=4&sn=436b90da545e21fe32e5da181048bc70#rd",
        "workUuid": "A638C0DC0D57EDCCF1D31D6EDF901235"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 1028,
        "commentCount": 76,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLTvmTRKq9dTh4WCI6QuCPeTuHiaySLibaRwicqXyWhicWZX3Iy9SaUEz39bniaibLaRGvQSoalBQiaHW13rsSrYhfrKbdtH4Wic6l226d8/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 1014,
        "orderNum": 0,
        "originalAuthor": null,
        "publishTime": "2026-07-20 18:50:00",
        "readCount": 100001,
        "shareCount": 4993,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 01:50:33",
        "title": "上了中学回头看：凡是用补习班排满假期的家庭，子女多半成绩平平；凡是留足自由时间的家庭，子女学习效率更高！",
        "watchCount": 508,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217756&idx=1&sn=20702f63136e99373b931a373178c7d5#rd",
        "workUuid": "4FE66F725C78E762CA56A1AAEF50E3E8"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 118,
        "commentCount": 12,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLRchR73HcsxteibGKxbwXxSJFo1ibbJaXPl8D9noSStroQzIqkb8swLGU7M2nYcb7j7ImhqD1rqbShl2lLQbagMJAV5NicZW6HX08/0?wx_fmt=jpeg",
        "isOriginal": 1,
        "likeCount": 236,
        "orderNum": 2,
        "originalAuthor": "十点签约作者",
        "publishTime": "2026-07-20 18:50:00",
        "readCount": 23779,
        "shareCount": 450,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 04:46:54",
        "title": "守住内心的秩序感，才能拥有生活的自在",
        "watchCount": 166,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217756&idx=3&sn=7c9b88b5372979258a5457fdaf561c2e#rd",
        "workUuid": "575AC9E1847F765EFEE543F38EDF7539"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 41,
        "commentCount": 11,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/mmbiz_jpg/iaJ8t5teDHLRAVial9KCA371zdmtm2gfYUmffShkGJLpJkCpgIcZsMrJiaMEolO5w41tq6uS8tup3vMcMBhXE9GFug00hwplfWDjSMULDun15w/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 101,
        "orderNum": 4,
        "originalAuthor": null,
        "publishTime": "2026-07-20 18:50:00",
        "readCount": 8388,
        "shareCount": 132,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 01:39:44",
        "title": "周星驰，这一次可以不赢",
        "watchCount": 65,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217756&idx=5&sn=ad07ed1a12d63c96263fd2db678dc1ce#rd",
        "workUuid": "640020C3422230E3AB4924B082C7EA19"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 428,
        "commentCount": 20,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/mmbiz_jpg/iaJ8t5teDHLRBicRWB7icMJZ9f6H2ks0TUFEOseYmicRHSjmlnLUb8RX1ia4bw1uIMo2ckmWgmCeMqxWN2sXeicX0CMAKlEc0Y0w8QtQibZIGYCsLI/0?wx_fmt=jpeg",
        "isOriginal": 1,
        "likeCount": 585,
        "orderNum": 1,
        "originalAuthor": "十点签约作者",
        "publishTime": "2026-07-20 18:50:00",
        "readCount": 100001,
        "shareCount": 2207,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 01:52:22",
        "title": "越来越多女性，确诊PMOS",
        "watchCount": 300,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217756&idx=2&sn=faa5a90fc93ee7659139a9837dafca73#rd",
        "workUuid": "747DD9A6D12386A158476B10CA0175A5"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 730,
        "commentCount": 106,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLRicBANRzicSvB4ciauuP8AUQZqDerl5TJgSRuVooLbCSOJXYk8N7FewBaVzLicNFfTULgNd4kyjoThnQ403gdF9NNnJOIgK9t9oeM/0?wx_fmt=jpeg",
        "isOriginal": 1,
        "likeCount": 1430,
        "orderNum": 0,
        "originalAuthor": "十点明冬",
        "publishTime": "2026-07-19 18:30:00",
        "readCount": 100001,
        "shareCount": 3969,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 06:06:26",
        "title": "新型伴侣悄悄流行：两情相悦，明码标价",
        "watchCount": 555,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217587&idx=1&sn=86ca6a435d03c8a226df037ee2311c24#rd",
        "workUuid": "D276CFFB723994ADCF378D171AC3D035"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 155,
        "commentCount": 13,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/mmbiz_jpg/iaJ8t5teDHLSgiaw9DPgkgv3XqfRPkugsXrsZGJ7ymIX4K3icsgspY2ic5V2uekkcIgfvu8qjEW9ofK4sew8TtB8JdYejibxjicQR2QgibyCjOFswc/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 235,
        "orderNum": 3,
        "originalAuthor": null,
        "publishTime": "2026-07-19 18:30:00",
        "readCount": 20488,
        "shareCount": 755,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 02:11:37",
        "title": "一个家庭最危险的习惯：对吃饭不上心",
        "watchCount": 154,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217587&idx=4&sn=3289741fc04320d578f07ca941abf3a0#rd",
        "workUuid": "348C63FA2DB389C855AF0A7C81C8BA48"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 289,
        "commentCount": 25,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLTjziciaIFI2JN2ecslX3RfIsUCia2xXauNupGFUEibgSUDcn6Bibg3zSJe6ACv8b09svrbVBPAC025W8sv7Y0LCibsrMCIX5TbADRYc/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 609,
        "orderNum": 1,
        "originalAuthor": null,
        "publishTime": "2026-07-19 18:30:00",
        "readCount": 100001,
        "shareCount": 1123,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 10:55:23",
        "title": "大S，卡里仅剩42万",
        "watchCount": 254,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217587&idx=2&sn=191bdaf9729887206b48504f913e4f8b#rd",
        "workUuid": "EC098BE30569225A4FEFF381973BD908"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 174,
        "commentCount": 11,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLRsuTxTEUibjgz7ktHxX1fibV4rcx1jLRr2WxicWq0IOFbnGoicIuFZ9tnOPBO5zxiakrFE78ezzcPoQrdEyyempT70vAVvogel2Xn0/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 343,
        "orderNum": 2,
        "originalAuthor": null,
        "publishTime": "2026-07-19 18:30:00",
        "readCount": 36158,
        "shareCount": 644,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 04:03:49",
        "title": "人到中年，一定不能碰的事",
        "watchCount": 205,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217587&idx=3&sn=afa68a0b8060e08eb0ed4cecf4401301#rd",
        "workUuid": "C537103F1B28E1C7E8645524AC5385B1"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 14,
        "commentCount": null,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/mmbiz_jpg/iaJ8t5teDHLSDarIFAnNxTEpv9cVD0DJSPGSOX8CF2r80gdjxVRKBbyfice7jdFwB9NORk6ePeJk0FBNYlyhicvFU2EPlNpNb0AypN7JkzoEB0/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 20,
        "orderNum": 4,
        "originalAuthor": null,
        "publishTime": "2026-07-19 18:30:00",
        "readCount": 5004,
        "shareCount": 20,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 04:00:34",
        "title": "比口红更润！5秒提气色，素颜好看到爆",
        "watchCount": 18,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217587&idx=5&sn=eee1feaad833aa57d2a82ea70c5840ba#rd",
        "workUuid": "88582CC7652C73E5FE60EE43AE17D295"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 8,
        "commentCount": null,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/mmbiz_jpg/iaJ8t5teDHLT4Zlmbc4iauldhE3a3UtOXgjWA4QJvrkfV1QTfeGUibCkTR2PKJPq5AHHVmMomddKwxOfXQibZ2OWEqNQ6ElBnP7IDecAk9U2Wy0/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 21,
        "orderNum": 4,
        "originalAuthor": null,
        "publishTime": "2026-07-18 18:30:00",
        "readCount": 6783,
        "shareCount": 37,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 02:08:45",
        "title": "“亚麻天丝裤”火了，显瘦藏肉清凉，夏天穿美翻",
        "watchCount": 14,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217582&idx=5&sn=54efddbf843f03ea91aef2cb30f40d9b#rd",
        "workUuid": "F408F837A9664890F00BF5D4B11BF857"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 202,
        "commentCount": 13,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/mmbiz_jpg/iaJ8t5teDHLREKTBcqTs7VlRRBHrV79zlmJLXSlpLlicriawSSjOwibj0otX9wXicPEsX2V6oUvtWJZiaIibpiam5EI16LibkmvzUNBTO6aZBgM9WH2w/0?wx_fmt=jpeg",
        "isOriginal": 1,
        "likeCount": 462,
        "orderNum": 1,
        "originalAuthor": "十点签约作者",
        "publishTime": "2026-07-18 18:30:00",
        "readCount": 60812,
        "shareCount": 938,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 04:48:46",
        "title": "退休后恋爱的女人：拿着养老金，被坑惨了",
        "watchCount": 277,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217582&idx=2&sn=abd5e9056c2778eb4d07ea77f91230c6#rd",
        "workUuid": "47925F1E423677A699A9A5CC58116746"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 112,
        "commentCount": 7,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/mmbiz_jpg/iaJ8t5teDHLRwC4MWlVXUtucOw6zibovEARgZ6OfmXITIydTPs3U60fJOV48vT5yBPzvicPdWBSO4Z7cUqM7TxKC0SRqdJTngrtModcqB3Uohg/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 179,
        "orderNum": 2,
        "originalAuthor": null,
        "publishTime": "2026-07-18 18:30:00",
        "readCount": 16565,
        "shareCount": 400,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 03:29:40",
        "title": "早日屏蔽掉网上这三种消息",
        "watchCount": 121,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217582&idx=3&sn=fae17c4a484fe5552b55f0a33445ebf7#rd",
        "workUuid": "32F6BEF1C0A1DCE360E61739DA97FDB7"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 185,
        "commentCount": 13,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLTZjLJJA1BFoicmic4FfMQ0tCKm6aOlPqdPUTVJJYo86sLicXW1x7qMmugppameJRhPIrP3MQJ1PWCXQ9XsUpNFtUrzYjQOFECRJ8/0?wx_fmt=jpeg",
        "isOriginal": 0,
        "likeCount": 235,
        "orderNum": 3,
        "originalAuthor": null,
        "publishTime": "2026-07-18 18:30:00",
        "readCount": 20446,
        "shareCount": 561,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 02:25:20",
        "title": "尽量不要和为你服务的人走得太近",
        "watchCount": 152,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217582&idx=4&sn=abc3e4657707e1a2a092b978b9901781#rd",
        "workUuid": "ABFE0B006063E9B27ECB674E2F7634EF"
      },
      {
        "author": "十点读书",
        "authorAvatarUrl": "http://mmbiz.qpic.cn/mmbiz_png/icB0yCLh6LJv46iardk496LKEUIJmurHoibTKZspMSWkGkwFDXG7abmII5yspeiaL2Fc96zu9zjTCRIdyJwyrzH2rw/0?wx_fmt=png",
        "bizInfo": "MjM5MDMyMzg2MA==",
        "collectCount": 1179,
        "commentCount": 48,
        "content": null,
        "coverUrl": "https://mmbiz.qpic.cn/sz_mmbiz_jpg/iaJ8t5teDHLRByFeLUwVn0oQibeW0v5ia6LwXsiadHPicUtyyqKPYmNLUVVkdIV9vLcATpYdibdFwIiaOkLGR1hPFsTiaoBVHgHLHPc4VazAs8t0o9k/0?wx_fmt=jpeg",
        "isOriginal": 1,
        "likeCount": 2063,
        "orderNum": 0,
        "originalAuthor": "十点肖肖",
        "publishTime": "2026-07-18 18:30:00",
        "readCount": 100001,
        "shareCount": 4025,
        "sourceUrl": null,
        "summary": "深夜十点，陪你读书。",
        "syncTime": "2026-07-22 03:47:41",
        "title": "长寿有福之人，脸上往往有这3个特征，占一个便是福气",
        "watchCount": 1311,
        "workUrl": "https://mp.weixin.qq.com/s?__biz=MjM5MDMyMzg2MA==&mid=2656217582&idx=1&sn=b681de0fa58419272ebaf79cdd1d6b31#rd",
        "workUuid": "FC5FB5AE54581FDFB1CD4061BE2705AD"
      }
    ],
    "total": 3755
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
