# Nanobanana 架构图提示词

## 主提示词

请绘制一张“AdBudgetSentry 广告消耗监控系统架构图”，风格为企业内部技术汇报图，不要画成宣传海报，不要加入 3D、插画人物、卡通元素。

### 画面目标

- 输出一张 16:9 横向架构图。
- 主题是“浏览器端监控脚本 + 本地分析网关 + 本地管理后台 + 外部 AI/告警服务 + Cloudflare Tunnel 公网接入”。
- 要体现这是一个当前阶段的单体式本地系统，而不是大规模微服务集群。

### 布局要求

从左到右分成 3 个区域：

1. 浏览器侧
2. 本机 / Windows 主机
3. 外部服务

在最上方加标题：

- 标题：`AdBudgetSentry 架构图`
- 副标题：`Tampermonkey 采集、FastAPI 分析网关、SQLite、管理后台、PushPlus、DeepSeek、Cloudflare Tunnel`

### 节点要求

左侧“浏览器侧”区域包含：

- `运营 / 管理员`
- `快手磁力金牛页面`
- `Tampermonkey 用户脚本`
  - DOM 采集
  - 本地配置与历史缓存
  - GM_xmlhttpRequest

中间“本机 / Windows 主机”区域包含：

- `FastAPI Analysis Gateway`
  - 采集接入 API
  - 管理 API
  - 页面入口
  - AI 调用
  - 告警发送
- `SQLite / data/app.db`
  - script_instances
  - capture_events
  - alert_records
  - analysis_summaries
- `规则异常检测模块`
  - surge
  - threshold_breach
  - stalled
- `后端渲染管理页 admin_ui.py`
- `React Admin Frontend dist`
- `后台健康巡检 / 告警任务`

右侧“外部服务”区域包含：

- `PushPlus`
- `DeepSeek API`
- `本地 OpenAI 兼容模型`
- `Cloudflare Tunnel`
- `公网管理域名`

### 连线要求

必须画出并标注这些箭头：

- `Tampermonkey 用户脚本 -> FastAPI Analysis Gateway`
  - 标签：`/ingest /heartbeat /error /alerts/test /analyze`
- `FastAPI Analysis Gateway -> SQLite`
  - 标签：`实例、采集、告警、分析入库`
- `FastAPI Analysis Gateway -> 规则异常检测模块`
  - 标签：`规则判定`
- `FastAPI Analysis Gateway -> PushPlus`
  - 标签：`告警推送`
- `FastAPI Analysis Gateway -> DeepSeek API`
  - 标签：`AI 分析 / 实例聊天`
- `FastAPI Analysis Gateway -> 本地 OpenAI 兼容模型`
  - 标签：`本地模型接入`
- `Cloudflare Tunnel -> FastAPI Analysis Gateway`
  - 标签：`安全暴露本地后台`
- `公网管理域名 -> Cloudflare Tunnel`
  - 标签：`HTTPS 访问`
- `FastAPI Analysis Gateway -> React Admin Frontend dist`
  - 标签：`静态资源 / SPA 入口`
- `FastAPI Analysis Gateway -> 后端渲染管理页`
  - 标签：`SSR 回退页面`

### 视觉风格

- 风格：专业、干净、简洁、适合技术评审 PPT。
- 背景：浅灰或白底。
- 配色：
  - 浏览器侧用浅蓝
  - 本地业务系统用浅绿
  - 数据库用浅黄或浅橙
  - 外部服务与公网入口用浅紫
- 连接线清晰，主链路略粗。
- 使用圆角矩形，不要使用数据库圆柱以外的花哨形状。
- 图中中文文字要清晰、规整、避免过密。

### 关键语义

请明确表现这些事实：

- 这是单个 FastAPI 网关承载多项职责的现状架构。
- 管理后台并非独立后端，而是由 FastAPI 提供页面和 API。
- React 管理端是静态构建产物，由 FastAPI 托管。
- Cloudflare Tunnel 只是公网入口，不参与业务处理。
- AI 服务和 PushPlus 都是外部依赖，不在本机内部。

### 严禁出现

- 不要画 Kafka、Redis、MQ、Kubernetes、Docker Swarm、Service Mesh。
- 不要画多副本部署、负载均衡集群、网关集群。
- 不要把 React 前端画成独立部署在公网服务器上。
- 不要把 Cloudflare Tunnel 画成数据库或业务服务。
- 不要加入和仓库无关的支付、用户系统、认证中心、BI 平台。

## 精简版提示词

绘制一张 16:9 企业级软件架构图，标题为“AdBudgetSentry 架构图”。左侧是“浏览器侧”：运营/管理员、快手磁力金牛页面、Tampermonkey 用户脚本；中间是“本机 / Windows 主机”：FastAPI Analysis Gateway、SQLite 数据库、规则异常检测模块、后端渲染管理页、React Admin Frontend dist、后台健康巡检/告警任务；右侧是“外部服务”：PushPlus、DeepSeek API、本地 OpenAI 兼容模型、Cloudflare Tunnel、公网管理域名。用箭头标注主要链路：Tampermonkey 通过 `/ingest /heartbeat /error /alerts/test /analyze` 调用 FastAPI，FastAPI 读写 SQLite，调用规则检测、PushPlus 和 AI 服务，托管 React 静态资源和 SSR 回退页面，并通过 Cloudflare Tunnel 被公网域名安全访问。整体风格简洁、专业、汇报级，浅色背景，蓝绿橙紫分区，圆角矩形，禁止微服务集群、Kafka、Redis、K8s 等无关元素。
