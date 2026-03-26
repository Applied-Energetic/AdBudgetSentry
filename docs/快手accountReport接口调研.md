# 快手 `accountReport` 接口调研

## 1. 调研对象

- 本地参考文档：
  - `D:\File\Dev\AdBudgetSentry\references\pages\快手磁力引擎开放平台-获取广告账户数据API.html`
- 在线文档入口：
  - `https://developers.e.kuaishou.com/docs?docType=ESP&documentId=3144&menuId=3901`
- 目标接口：
  - `https://ad.e.kuaishou.com/rest/openapi/gw/esp/report/accountReport`
- 请求方式：
  - `POST`
- 数据格式：
  - `JSON`
- 文档更新时间：
  - `2025-12-02 19:56`

用户提供的信息：

- 广告主 ID：`2673682603`
- 快手 ID：`2673682603`
- 当前广告账户 ID：`13566563`

## 2. 文档确认到的关键事实

从本地保存的官方 HTML 中，已经能明确读到接口说明：

- 接口名称：`获取广告账户数据`
- 接口用途：`此接口用于获取广告主账户数据`
- 请求接口：`https://ad.e.kuaishou.com/rest/openapi/gw/esp/report/accountReport`
- 请求方式：`POST`
- 数据格式：`JSON`

## 3. 请求参数

### 3.1 顶层必填字段

文档中明确标记为必填的顶层字段有：

- `advertiser_id`: `Long`，广告主 ID
- `start_time`: `Long`，开始时间，示例 `1728403200000`
- `end_time`: `Long`，结束时间，示例 `1728403200000`
- `select_columns`: `String[]`，查询列
- `group_type`: `Integer`，时间维度
- `query_version`: `Integer`，查询版本
- `page_info`: `PageInfo`，分页信息

### 3.2 文档中展示的取值说明

- `group_type`
  - `1`: 按天聚合数据
  - `2`: 按小时聚合数据
  - `3`: 按全部聚合数据
- `query_version`
  - `1`: PC 标准推广
  - `2`: 移动标准推广
  - `3`: PC 标准推广 + 移动标准推广

### 3.3 `select_param` 下的常见筛选字段

文档里还列出了 `select_param` 结构，常见字段包括：

- `ad_type_str`
- `author_id`
- `marketing_objective`
- `delivery_scenario`
- `delivery_method`
- `support_type`
- `ocpc_action_type`
- `speed_type`
- `item_type`
- `creative_build_type`
- `ad_scene`

其中 `marketing_objective` 在文档表格中标记为必填，说明如果传 `select_param`，这个字段要重点注意。

### 3.4 `page_info`

文档显示 `page_info` 下至少包括：

- `current_page`
- `page_size`

文档表中还出现了 `total_count`，但更像返回字段或展示字段，实际请求时不一定需要主动传。

## 4. 返回字段

返回顶层结构至少包括：

- `code`
- `message`
- `data`

文档中的 `data` 下列出了大量指标字段，说明这个接口确实是结构化报表接口，不是页面专用接口。已确认的典型返回列包括：

- `cost_total`: 花费
- `ad_show`: 曝光数
- `click`: 素材曝光数
- `conversion_num`: 转化数
- `conversion_cost_esp`: 转化成本
- `roi`: 直接 ROI
- `gmv`: 直接 GMV
- `t0_gmv`: 当日累计 GMV
- `t0_roi`: 当日累计 ROI
- `t0_order_cnt`: 当日累计订单数
- `net_t0_order_cnt`: 当日累计净成交订单数
- `net_t0_roi`: 净成交 ROI
- `author_id`: 直播用户快手 ID
- `live_name`: 直播间名称

这也说明后端 API 路线一旦打通，数据完备度会明显强于单纯 DOM 抓取。

## 5. 本次实测

### 5.1 只传 `advertiser_id` 时

实测返回：

```json
{
  "code": 401001,
  "data": {},
  "message": "advertiser_id或agent_id格式错误",
  "status": 200
}
```

这一步说明：

- 接口是可达的
- 但未按文档传完整必填字段时，报错会停留在最外层参数校验

### 5.2 按文档补齐最小必填集后

实测请求体示例：

```json
{
  "advertiser_id": 13566563,
  "start_time": 1742342400000,
  "end_time": 1742428799000,
  "select_columns": ["charge"],
  "group_type": 1,
  "query_version": 3,
  "page_info": {
    "current_page": 1,
    "page_size": 20
  }
}
```

接口返回：

```json
{
  "code": 402003,
  "data": {},
  "message": "access token为空",
  "status": 200
}
```

这个结果非常关键，说明：

1. 请求结构已经基本进入业务校验阶段。
2. 当前阻塞点不是字段名猜错，而是**缺少 access token**。
3. 这条链路属于**开放平台鉴权接口**，不能只靠裸 POST 就拿到数据。

## 6. 结论

### 6.1 能不能用后端 `POST` 拿数据

能，但前提是：

- 你要拿到开放平台要求的 `access token`
- 还要确认广告主主体 ID、授权关系、查询列名是否完全匹配

当前已经确认：

- 不是纯 Cookie 页面接口
- 不是只传广告主 ID 就能直接拿
- 必须进入正式开放平台鉴权链路

### 6.2 你给的两个 ID 怎么理解

从文档和实测推断：

- `advertiser_id` 更可能对应广告主主体 ID，而不是快手个人 ID
- 你提供的 `13566563` 更像广告账户 ID
- `2673682603` 是快手 ID / 用户标识，不一定能直接作为 `advertiser_id`

也就是说，后续还需要把“广告主主体 ID”和“账户 ID”区分开。

## 7. 两条采数路线的判断

### 7.1 同时考虑易用性、稳定性、项目展示

如果你要做一个既能落地、又能讲清楚技术栈的项目，我建议：

- **短期 MVP 用油猴脚本前端抓取**
- **中长期主链路转向后端 API 拉数**

原因：

- 油猴：
  - 上手最快
  - 依赖当前登录态
  - 不需要先打通开放平台鉴权
- 后端 API：
  - 一旦打通，结构更稳
  - 指标更完整
  - 更适合做时序存储、异常检测、AI 分析和项目展示

如果必须只选一个“更合适”的主方案，我会选：

- **项目主方案：后端 `POST`**
- **实际起步方案：油猴抓取**

### 7.2 如果不考虑易用性，只考虑展示性

结论更明确：

- **后端 `POST` 请求更合适**

因为它更能展示：

- 对开放平台接口的理解
- 鉴权流程处理能力
- 后端采集服务能力
- 结构化数据建模能力
- 定时任务、存储、分析、告警完整链路

## 8. 当前最实际的下一步

1. 确认开放平台应用是否已开通，以及是否能拿到 `access token`
2. 明确真正的 `advertiser_id` 是哪个主体 ID
3. 在浏览器 Network 里抓一次官方 SDK / 页面发起的真实成功请求
4. 确认 `select_columns` 的合法字段名集合
5. 再决定是否在仓库里落地后端采集器

## 9. 当前可直接用于汇报的判断

一句话版本：

- **油猴抓取适合快速落地，后端 API 更适合做成完整项目作品；如果只看展示性，后端 API 明显更优。**
