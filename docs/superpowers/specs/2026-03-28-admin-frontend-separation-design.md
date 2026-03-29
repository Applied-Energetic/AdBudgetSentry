# Admin Frontend Separation Design

**Date:** 2026-03-28

## Goal

将后台监控系统从 Python 直接拼接 HTML 的模式，增量迁移为 `FastAPI + React + shadcn/ui` 的前后端分离结构。第一版只接管后台监控系统，不改油猴脚本，不重写分析和告警业务逻辑。

## Scope

本轮只覆盖：
- `/admin` 监控总览页
- `/admin/alerts` 告警页
- `/admin/instances/{instance_id}` 实例详情页
- 与上述页面配套的前端组件、样式系统、数据获取和路由接入

本轮不覆盖：
- 油猴脚本 UI 重构
- AI 分析逻辑与告警规则重写
- 鉴权系统
- 全站设计系统扩张到非后台页面

## Current Constraints

- 当前后台 UI 主要集中在 `code/analysis_gateway/admin_ui.py`，通过 Python 长字符串拼接 HTML/CSS，设计迭代成本高，组件复用能力弱。
- `code/analysis_gateway/app.py` 同时承担 API、HTML 页面返回和业务流程编排，页面层和接口层边界不够清晰。
- 现有后端已经具备后台所需的核心 JSON 接口，适合作为第一版前端的直接数据源。
- 当前机器已经补齐 Node.js 工具链，可支持 Vite、React、Tailwind 和 shadcn/ui。

## Recommended Approach

采用增量式前后端分离：
- 保留 `FastAPI + SQLite + 现有采集/分析/告警逻辑`
- 新建独立前端工程，使用 `React + TypeScript + Vite + Tailwind CSS + shadcn/ui`
- 由 FastAPI 继续提供 `/admin/api/*` 数据接口
- 生产构建后由 FastAPI 直接托管前端静态资源，并将 `/admin`、`/admin/alerts`、`/admin/instances/{instance_id}` 路由切到 SPA 入口

这是最低风险且最能提升 UI 上限的路径。

## Architecture

### Backend

FastAPI 保持业务中心，新增职责：
- 提供前端静态文件目录
- 为后台三个页面提供统一 SPA 入口
- 保持现有 JSON API 可用
- 根据需要补充聚合接口，但第一版优先复用现有接口

### Frontend

新增 `admin_frontend` 工程：
- `AppShell` 负责侧边栏、顶栏和页面外壳
- `DashboardPage` 负责总览页三段式布局
- `AlertsPage` 负责筛选、列表、汇总卡片
- `InstanceDetailPage` 负责顶部指标、基础信息、趋势与记录列表
- 共享 UI primitives 优先采用 `shadcn/ui` 组件，并在其基础上收敛视觉变量

### Routing

前端采用客户端路由：
- `/admin`
- `/admin/alerts`
- `/admin/instances/:instanceId`

FastAPI 对以上路径统一返回构建后的 `index.html`。

## Data Flow

### Dashboard

页面加载后并行请求：
- `GET /admin/summary`
- `GET /admin/instances`
- `GET /admin/api/alerts`

前端负责：
- KPI 汇总展示
- 健康分布与告警发送分布图表转换
- 实例列表与告警列表裁剪显示

### Alerts

页面通过查询参数驱动：
- `GET /admin/api/alerts?...`
- `GET /admin/alerts/export.csv?...` 继续保留为导出入口

### Instance Detail

页面请求：
- `GET /admin/api/instances/{instance_id}`
- `POST /admin/api/instances/{instance_id}/meta`
- `DELETE /admin/api/instances/{instance_id}`

## Visual Direction

采用现代 B2B SaaS 后台风格：
- 浅中性色页面背景
- 白色内容卡片，细边框，极轻阴影
- 使用 shadcn/ui 的 `Card`、`Button`、`Badge`、`Table`、`Input`、`Textarea`、`Dialog`、`DropdownMenu` 等组件
- 不使用重渐变 hero，不使用 cyberpunk 风格，不使用炫目动效
- 强调层级、留白、一致性和可读性

## Migration Strategy

### Phase 1

建立前端骨架并接管 `/admin`：
- 搭建前端工程
- 接入 Tailwind 与 shadcn/ui
- 落地基础布局和 tokens
- 完成 dashboard 第一版

### Phase 2

接管详情页和告警页：
- 实例详情页迁移
- 告警页迁移
- 删除或保留旧模板作为回退参考，但新路由默认走前端 SPA

### Phase 3

统一收尾：
- 校验移动端表现
- 梳理中文文案和术语
- 评估后续是否扩展到更多后台页面

## Risks

- 当前 `app.py` 存在一部分历史编码污染，迁移时要避免继续扩散到新前端。
- `shadcn/ui` 依赖 Node 构建链，本地和部署环境都要保证前端 build 可执行。
- 现有 API 结构偏原始，前端第一版要在客户端做部分映射与整形。

## Success Criteria

第一版完成后应满足：
- `/admin`、`/admin/alerts`、`/admin/instances/{instance_id}` 均由新前端渲染
- 后台视觉质量明显优于当前字符串模板版本
- 现有业务接口与数据写入逻辑不受影响
- 能完成本地前端构建与 Python 端运行验证
